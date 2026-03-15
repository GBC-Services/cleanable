"""
Support Resolution Models
==========================

Proactive complaint-to-resolution pipeline with a predefined Decision
Array.  Lives alongside the existing ``SupportTicket`` and
``JobVerification`` models in ``apps.support``.

Complaint Scenarios:
  - Incomplete Clean
  - No-Show
  - Damage Reported
  - Late Arrival

Resolution Toolset (Decision Array):
  1. Refund — partial or full via Stripe API
  2. Schedule Re-do — auto-assign high-priority re-cleaning
  3. Cancel & Blacklist — terminate service + re-assign future bookings

Every resolution action is logged with full audit trail.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.bookings.models import Booking
from apps.cleanings.models import Cleaning
from apps.companies.models import Company
from apps.utils.models import BaseModel

UserModel = settings.AUTH_USER_MODEL


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. Complaint — Resident-submitted, auto-escalated
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class Complaint(BaseModel):
    """
    A Resident complaint tied to a specific Booking/Cleaning.
    Immediately escalated to the Support Architect dashboard.
    """

    # ── Scenario constants ────────────────────────────────────────────
    SCENARIO_INCOMPLETE_CLEAN = "incomplete_clean"
    SCENARIO_NO_SHOW = "no_show"
    SCENARIO_DAMAGE_REPORTED = "damage_reported"
    SCENARIO_LATE_ARRIVAL = "late_arrival"

    SCENARIO_CHOICES = (
        (SCENARIO_INCOMPLETE_CLEAN, "Incomplete Clean"),
        (SCENARIO_NO_SHOW, "No-Show"),
        (SCENARIO_DAMAGE_REPORTED, "Damage Reported"),
        (SCENARIO_LATE_ARRIVAL, "Late Arrival"),
    )

    # ── Status flow ───────────────────────────────────────────────────
    STATUS_OPEN = "open"
    STATUS_ACKNOWLEDGED = "acknowledged"
    STATUS_INVESTIGATING = "investigating"
    STATUS_RESOLVED = "resolved"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_ACKNOWLEDGED, "Acknowledged"),
        (STATUS_INVESTIGATING, "Investigating"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CLOSED, "Closed"),
    )

    # ── Urgency levels ────────────────────────────────────────────────
    URGENCY_LOW = 10
    URGENCY_MEDIUM = 20
    URGENCY_HIGH = 30
    URGENCY_CRITICAL = 40

    URGENCY_CHOICES = (
        (URGENCY_LOW, "Low"),
        (URGENCY_MEDIUM, "Medium"),
        (URGENCY_HIGH, "High"),
        (URGENCY_CRITICAL, "Critical"),
    )

    # ── Scenario → Default urgency mapping ────────────────────────────
    SCENARIO_URGENCY_MAP = {
        SCENARIO_INCOMPLETE_CLEAN: URGENCY_MEDIUM,
        SCENARIO_NO_SHOW: URGENCY_CRITICAL,
        SCENARIO_DAMAGE_REPORTED: URGENCY_HIGH,
        SCENARIO_LATE_ARRIVAL: URGENCY_LOW,
    }

    # ── Fields ────────────────────────────────────────────────────────
    resident = models.ForeignKey(
        UserModel, on_delete=models.CASCADE,
        related_name="complaints_filed",
        help_text="The Resident who filed the complaint.",
    )
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE,
        related_name="complaints",
    )
    cleaning = models.ForeignKey(
        Cleaning, on_delete=models.CASCADE,
        blank=True, null=True, default=None,
        related_name="complaints",
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE,
        blank=True, null=True, default=None,
        related_name="complaints_against",
        help_text="The Agency this complaint targets.",
    )

    scenario = models.CharField(
        max_length=32, choices=SCENARIO_CHOICES,
    )
    description = models.TextField(
        help_text="Resident's description of the issue.",
    )
    urgency = models.PositiveIntegerField(
        choices=URGENCY_CHOICES, default=URGENCY_MEDIUM,
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )

    # ── Assignment / escalation ───────────────────────────────────────
    assigned_to = models.ForeignKey(
        UserModel, blank=True, null=True, default=None,
        on_delete=models.SET_NULL,
        related_name="complaints_assigned",
        help_text="Support Architect handling this complaint.",
    )
    escalated_at = models.DateTimeField(
        blank=True, null=True, default=None,
        help_text="When this complaint was escalated to the dashboard.",
    )
    acknowledged_at = models.DateTimeField(blank=True, null=True, default=None)
    resolved_at = models.DateTimeField(blank=True, null=True, default=None)

    # ── Evidence ──────────────────────────────────────────────────────
    evidence_photos = models.JSONField(
        blank=True, null=True, default=None,
        help_text="List of uploaded photo URLs as evidence.",
    )

    # ── Related support ticket (auto-created) ─────────────────────────
    support_ticket = models.OneToOneField(
        "support.SupportTicket", blank=True, null=True, default=None,
        on_delete=models.SET_NULL,
        related_name="complaint",
    )

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Complaint #{self.pk} — {self.get_scenario_display()} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        # Auto-set urgency from scenario if not explicitly set
        if is_new and self.urgency == self.URGENCY_MEDIUM:
            self.urgency = self.SCENARIO_URGENCY_MAP.get(
                self.scenario, self.URGENCY_MEDIUM
            )
        # Auto-derive company from cleaning/booking
        if not self.company_id:
            if self.cleaning and self.cleaning.company:
                self.company = self.cleaning.company
        # Auto-escalate on creation
        if is_new and not self.escalated_at:
            self.escalated_at = timezone.now()
        super().save(*args, **kwargs)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. Resolution Action — Decision Array execution log
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ResolutionAction(BaseModel):
    """
    An auditable record of every resolution step taken on a Complaint.
    Each complaint can have multiple actions (e.g., partial refund +
    schedule re-do).
    """

    # ── Action types ──────────────────────────────────────────────────
    ACTION_REFUND_PARTIAL = "refund_partial"
    ACTION_REFUND_FULL = "refund_full"
    ACTION_SCHEDULE_REDO = "schedule_redo"
    ACTION_CANCEL_BLACKLIST = "cancel_blacklist"
    ACTION_NOTE = "note"

    ACTION_CHOICES = (
        (ACTION_REFUND_PARTIAL, "Partial Refund"),
        (ACTION_REFUND_FULL, "Full Refund"),
        (ACTION_SCHEDULE_REDO, "Schedule Re-do"),
        (ACTION_CANCEL_BLACKLIST, "Cancel & Blacklist"),
        (ACTION_NOTE, "Internal Note"),
    )

    # ── Execution status ──────────────────────────────────────────────
    EXEC_PENDING = "pending"
    EXEC_PROCESSING = "processing"
    EXEC_COMPLETED = "completed"
    EXEC_FAILED = "failed"

    EXEC_CHOICES = (
        (EXEC_PENDING, "Pending"),
        (EXEC_PROCESSING, "Processing"),
        (EXEC_COMPLETED, "Completed"),
        (EXEC_FAILED, "Failed"),
    )

    complaint = models.ForeignKey(
        Complaint, on_delete=models.CASCADE,
        related_name="resolution_actions",
    )
    performed_by = models.ForeignKey(
        UserModel, on_delete=models.CASCADE,
        related_name="resolution_actions_taken",
    )
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    execution_status = models.CharField(
        max_length=12, choices=EXEC_CHOICES, default=EXEC_PENDING,
    )
    notes = models.TextField(blank=True, default="")

    # ── Refund fields ─────────────────────────────────────────────────
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        blank=True, null=True, default=None,
        help_text="USD amount refunded via Stripe.",
    )
    stripe_refund_id = models.CharField(
        max_length=128, blank=True, null=True, default=None,
    )

    # ── Re-do fields ──────────────────────────────────────────────────
    redo_cleaning = models.ForeignKey(
        Cleaning, blank=True, null=True, default=None,
        on_delete=models.SET_NULL,
        related_name="redo_resolution",
        help_text="The newly created re-cleaning task.",
    )
    redo_assigned_company = models.ForeignKey(
        Company, blank=True, null=True, default=None,
        on_delete=models.SET_NULL,
        related_name="redo_assignments",
        help_text="Agency assigned for the re-do (same or different).",
    )

    # ── Blacklist fields ──────────────────────────────────────────────
    blacklisted_company = models.ForeignKey(
        Company, blank=True, null=True, default=None,
        on_delete=models.SET_NULL,
        related_name="blacklist_actions",
    )
    reassigned_bookings_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of future recurring bookings re-assigned.",
    )

    # ── Notification tracking ─────────────────────────────────────────
    notifications_sent = models.JSONField(
        blank=True, null=True, default=None,
        help_text="Log of notification channels dispatched: [{channel, recipient, sent_at}]",
    )

    executed_at = models.DateTimeField(blank=True, null=True, default=None)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return (
            f"Resolution #{self.pk} — "
            f"{self.get_action_type_display()} on Complaint #{self.complaint_id}"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. Agency Blacklist — Per-Resident agency block
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgencyBlacklist(BaseModel):
    """
    When a Cancel & Blacklist resolution is applied, the agency is
    blocked from being assigned to this Resident's future bookings.
    The resolution engine uses this table to skip blacklisted agencies
    during automatic re-assignment.
    """

    resident = models.ForeignKey(
        UserModel, on_delete=models.CASCADE,
        related_name="agency_blacklist",
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE,
        related_name="blacklisted_by_residents",
    )
    complaint = models.ForeignKey(
        Complaint, on_delete=models.CASCADE,
        related_name="blacklist_entries",
    )
    reason = models.TextField(blank=True, default="")
    blacklisted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-blacklisted_at"]
        unique_together = [("resident", "company")]

    def __str__(self):
        return f"Blacklist: Resident {self.resident_id} ✕ Agency {self.company_id}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. Complaint Notification Log — Multi-channel dispatch record
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplaintNotification(BaseModel):
    """
    Tracks every notification sent as part of the complaint resolution
    lifecycle: SMS, Push, Email dispatched to Residents, Service Pros,
    Agency Owners, and Support Architects.
    """

    CHANNEL_SMS = "sms"
    CHANNEL_PUSH = "push"
    CHANNEL_EMAIL = "email"
    CHANNEL_IN_APP = "in_app"

    CHANNEL_CHOICES = (
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_PUSH, "Push Notification"),
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_IN_APP, "In-App"),
    )

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    )

    complaint = models.ForeignKey(
        Complaint, on_delete=models.CASCADE,
        related_name="notifications",
    )
    resolution_action = models.ForeignKey(
        ResolutionAction, blank=True, null=True, default=None,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    recipient = models.ForeignKey(
        UserModel, on_delete=models.CASCADE,
        related_name="complaint_notifications_received",
    )
    channel = models.CharField(max_length=8, choices=CHANNEL_CHOICES)
    status = models.CharField(
        max_length=8, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    message_body = models.TextField(
        help_text="The content of the notification sent.",
    )
    sent_at = models.DateTimeField(blank=True, null=True, default=None)
    error_detail = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return (
            f"Notification #{self.pk} — {self.get_channel_display()} → "
            f"User {self.recipient_id}"
        )
