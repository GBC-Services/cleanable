"""
Support & QA Models
====================

Ticket lifecycle with AI-driven triage, plus spatial verification
for post-job quality assurance via Cloudflare Workers AI vision.

Legacy models (SupportTicket, SupportTicketStatusChange,
SupportTicketMessage) are preserved and extended with AI fields.
New model: JobVerification — post-job video/photo QA pipeline.
"""

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bookings.models import Booking
from apps.utils.models import BaseModel, BaseDictModel

UserModel = settings.AUTH_USER_MODEL


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Support Ticket Category (legacy, unchanged)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class Category(BaseDictModel):
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Support Ticket — enhanced with AI triage fields
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SupportTicket(BaseModel):
    # ── Status constants ──────────────────────────────────────────────
    STATUS_NEW = 10
    STATUS_IN_WORK = 20
    STATUS_RESOLVED = 30
    STATUS_CANCELLED_BY_USER = 40
    STATUS_ESCALATED = 50

    STATUSES = (
        (STATUS_NEW, "New"),
        (STATUS_IN_WORK, "In work"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CANCELLED_BY_USER, "Cancelled by user"),
        (STATUS_ESCALATED, "Escalated"),
    )

    # ── Priority constants (AI-assigned or manual) ────────────────────
    PRIORITY_LOW = 10
    PRIORITY_MEDIUM = 20
    PRIORITY_HIGH = 30
    PRIORITY_URGENT = 40

    PRIORITIES = (
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_URGENT, "Urgent"),
    )

    # ── Sentiment constants ───────────────────────────────────────────
    SENTIMENT_POSITIVE = "positive"
    SENTIMENT_NEGATIVE = "negative"
    SENTIMENT_NEUTRAL = "neutral"

    SENTIMENT_CHOICES = (
        (SENTIMENT_POSITIVE, "Positive"),
        (SENTIMENT_NEGATIVE, "Negative"),
        (SENTIMENT_NEUTRAL, "Neutral"),
    )

    # ── Core fields (legacy, preserved) ───────────────────────────────
    booking = models.ForeignKey(
        Booking, blank=True, null=True, default=None,
        on_delete=models.CASCADE, related_name="support_tickets",
    )
    subject = models.CharField(max_length=256, blank=True, null=True, default=None)
    category = models.ForeignKey(
        Category, null=True, default=None, on_delete=models.CASCADE,
    )
    text = models.TextField()
    user = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="support_tickets_created",
    )
    assigned_to = models.ForeignKey(
        UserModel, blank=True, null=True, default=None,
        on_delete=models.SET_NULL, related_name="support_tickets_assigned",
    )
    status = models.PositiveIntegerField(choices=STATUSES, default=STATUS_NEW)
    comments = models.TextField(blank=True, null=True, default=None)

    # ── AI Triage fields ──────────────────────────────────────────────
    priority = models.PositiveIntegerField(
        choices=PRIORITIES, default=PRIORITY_MEDIUM,
    )
    sentiment = models.CharField(
        max_length=10, choices=SENTIMENT_CHOICES,
        blank=True, null=True, default=None,
    )
    sentiment_score = models.FloatField(
        blank=True, null=True, default=None,
        help_text="0.0–1.0 confidence from DistilBERT SST-2",
    )
    ai_summary = models.TextField(
        blank=True, null=True, default=None,
        help_text="Llama 3.2 generated ticket summary",
    )
    ai_suggested_response = models.TextField(
        blank=True, null=True, default=None,
        help_text="Llama 3.2 generated suggested response",
    )
    ai_category = models.CharField(
        max_length=64, blank=True, null=True, default=None,
        help_text="AI-inferred category slug (billing, scheduling, quality, etc.)",
    )
    ai_triaged_at = models.DateTimeField(
        blank=True, null=True, default=None,
        help_text="When the CF Worker last triaged this ticket",
    )
    resolution_notes = models.TextField(
        blank=True, null=True, default=None,
    )
    resolved_at = models.DateTimeField(blank=True, null=True, default=None)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"#{self.pk} — {self.subject or 'No subject'}"

    def get_absolute_url(self):
        return reverse("support_ticket", kwargs=dict(uuid=self.uuid))

    def get_messages(self):
        return self.messages.filter(is_active=True).order_by("-id")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Support Ticket Status Change (legacy, unchanged)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SupportTicketStatusChange(BaseModel):
    support_ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="status_changes",
    )
    status = models.PositiveIntegerField(choices=SupportTicket.STATUSES)
    user = models.ForeignKey(
        UserModel, null=True, default=None, on_delete=models.SET_NULL,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Support Ticket Message (legacy, updated related_name)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SupportTicketMessage(BaseModel):
    support_ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="messages",
    )
    text = models.TextField()
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Job Verification — Post-Job QA via CF Workers AI Vision
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class JobVerification(BaseModel):
    """
    A Service Pro uploads a post-job photo/video. The backend sends
    the image to Cloudflare Workers AI (LLaVA vision model) for
    cleanliness analysis. Auto-approved if score >= threshold.
    """

    # ── Verification status ───────────────────────────────────────────
    STATUS_PENDING = 10
    STATUS_ANALYZING = 20
    STATUS_APPROVED = 30
    STATUS_FLAGGED = 40
    STATUS_REJECTED = 50
    STATUS_MANUAL_REVIEW = 60

    VERIFICATION_STATUSES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_ANALYZING, "Analyzing"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_FLAGGED, "Flagged for Review"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_MANUAL_REVIEW, "Manual Review"),
    )

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="verifications",
    )
    service_pro = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="job_verifications",
    )

    # ── Media ─────────────────────────────────────────────────────────
    media_file = models.FileField(
        upload_to="verifications/%Y/%m/%d/",
        help_text="Post-job photo or video frame",
    )
    media_type = models.CharField(
        max_length=10, default="image",
        choices=(("image", "Image"), ("video", "Video")),
    )

    # ── AI Analysis Results ───────────────────────────────────────────
    status = models.PositiveIntegerField(
        choices=VERIFICATION_STATUSES, default=STATUS_PENDING,
    )
    cleanliness_score = models.FloatField(
        blank=True, null=True, default=None,
        help_text="0.0–1.0 cleanliness confidence from Workers AI vision",
    )
    ai_analysis = models.JSONField(
        blank=True, null=True, default=None,
        help_text="Full JSON response from CF Workers AI vision model",
    )
    ai_summary = models.TextField(
        blank=True, null=True, default=None,
        help_text="Human-readable summary of AI findings",
    )
    issues_detected = models.JSONField(
        blank=True, null=True, default=None,
        help_text="List of detected issues: stains, clutter, etc.",
    )
    analyzed_at = models.DateTimeField(blank=True, null=True, default=None)

    # ── Privacy Detection ─────────────────────────────────────────────
    privacy_metadata = models.JSONField(
        blank=True, null=True, default=None,
        help_text=(
            "Privacy detection results from CF Worker: detected faces, "
            "family photos, sensitive documents, blur regions."
        ),
    )
    r2_key = models.CharField(
        max_length=512, blank=True, null=True, default=None,
        help_text="Cloudflare R2 object key for stored verification media.",
    )
    privacy_scrubbed = models.BooleanField(
        default=False,
        help_text="True if privacy-sensitive content was detected and blur metadata was applied.",
    )
    ai_opt_out = models.BooleanField(
        default=False,
        help_text="True if the Resident opted out of AI processing for this verification.",
    )

    # ── Manual Review (QA Inspector override) ─────────────────────────
    reviewed_by = models.ForeignKey(
        UserModel, blank=True, null=True, default=None,
        on_delete=models.SET_NULL, related_name="verifications_reviewed",
    )
    reviewer_notes = models.TextField(blank=True, null=True, default=None)
    reviewed_at = models.DateTimeField(blank=True, null=True, default=None)

    # ── Thresholds ────────────────────────────────────────────────────
    AUTO_APPROVE_THRESHOLD = 0.85
    FLAG_THRESHOLD = 0.60

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Verification #{self.pk} — Booking {self.booking_id}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Resolution Pipeline (imported from resolution_models.py)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from apps.support.resolution_models import (  # noqa: E402, F401
    AgencyBlacklist,
    Complaint,
    ComplaintNotification,
    ResolutionAction,
)
