"""
Platform Governance Models
===========================

Phase 2 security architecture: global feature toggles, polymorphic
privacy preferences, break-glass escalation sessions, and an
immutable audit log.

Architecture Overview::

    ┌───────────────────────────────────────────────────────────┐
    │                  SystemFeatureToggle                       │
    │  Global kill-switches managed by Platform Admins only.     │
    │  Controls: GPS, IoT access, spatial video, AI features.    │
    └────────────────────────┬──────────────────────────────────┘
                             │ gates
    ┌────────────────────────▼──────────────────────────────────┐
    │               PrivacyPreferences (OneToOne → User)        │
    │  Per-user privacy controls with polymorphic toggles.       │
    │  Resident toggles ≠ Service Pro toggles.                  │
    │  All writes go through the audit log.                      │
    └────────────────────────┬──────────────────────────────────┘
                             │ can be overridden by
    ┌────────────────────────▼──────────────────────────────────┐
    │              BreakGlassSession                             │
    │  Time-limited escalation granting Support Architects       │
    │  temporary access to override privacy settings during      │
    │  active job emergencies.                                   │
    └────────────────────────┬──────────────────────────────────┘
                             │ every mutation recorded in
    ┌────────────────────────▼──────────────────────────────────┐
    │              GovernanceAuditLog                            │
    │  Immutable, append-only ledger.  No delete allowed         │
    │  at the ORM level.  Only Platform Admins can read.         │
    └───────────────────────────────────────────────────────────┘
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. SystemFeatureToggle — Global Kill-Switches
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SystemFeatureToggle(models.Model):
    """
    A single-row-per-feature global switch that a Platform Admin can
    flip to instantly enable or disable invasive platform capabilities.

    When ``is_enabled=False``, the corresponding feature is completely
    inaccessible system-wide regardless of per-user preferences.

    Seeded features (created via data migration or management command):
      - ``global_gps_enabled``        — Real-time GPS tracking
      - ``global_iot_access_enabled``  — Smart-home device integration
      - ``spatial_video_enabled``      — Spatial / 360° video capture
      - ``ai_quality_scoring_enabled`` — Cloudflare Workers AI scoring
      - ``push_notifications_enabled`` — Push notification delivery
      - ``break_glass_enabled``        — Break-glass escalation system
    """

    # ── Category grouping for UI ──────────────────────────────────────
    CATEGORY_LOCATION = "location"
    CATEGORY_IOT = "iot"
    CATEGORY_MEDIA = "media"
    CATEGORY_AI = "ai"
    CATEGORY_COMMS = "communications"
    CATEGORY_SECURITY = "security"
    CATEGORY_CHOICES = (
        (CATEGORY_LOCATION, "Location Services"),
        (CATEGORY_IOT, "IoT & Smart Home"),
        (CATEGORY_MEDIA, "Media & Recording"),
        (CATEGORY_AI, "AI & Machine Learning"),
        (CATEGORY_COMMS, "Communications"),
        (CATEGORY_SECURITY, "Security & Escalation"),
    )

    # ── Severity / risk classification ────────────────────────────────
    SEVERITY_LOW = "low"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CRITICAL = "critical"
    SEVERITY_CHOICES = (
        (SEVERITY_LOW, "Low"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
        (SEVERITY_CRITICAL, "Critical"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(
        blank=True, default="",
        help_text="Plain-language explanation shown to the Platform Admin.",
    )
    category = models.CharField(
        max_length=24, choices=CATEGORY_CHOICES, default=CATEGORY_SECURITY,
    )
    severity = models.CharField(
        max_length=12, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM,
        help_text="Risk level when this feature is enabled.",
    )

    is_enabled = models.BooleanField(
        default=False,
        help_text="Master switch. False = feature completely disabled system-wide.",
    )

    # ── Metadata ──────────────────────────────────────────────────────
    toggled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="toggled_features",
        help_text="Last admin who flipped this toggle.",
    )
    toggled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "System Feature Toggle"
        verbose_name_plural = "System Feature Toggles"

    def __str__(self):
        state = "ON" if self.is_enabled else "OFF"
        return f"[{state}] {self.name}"

    @classmethod
    def is_feature_active(cls, slug: str) -> bool:
        """Fast lookup: is a global feature currently enabled?"""
        try:
            return cls.objects.values_list("is_enabled", flat=True).get(slug=slug)
        except cls.DoesNotExist:
            return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. PrivacyPreferences — Per-User Polymorphic Privacy Controls
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PrivacyPreferences(models.Model):
    """
    One-to-one with User.  Stores privacy toggles with role-aware
    polymorphism — Residents and Service Pros each have their own
    subset of applicable fields.

    Polymorphic design:
      - Shared fields apply to ALL roles.
      - ``resident_*`` fields are only meaningful when user.role == 10.
      - ``pro_*`` fields are only meaningful when user.role == 40.
      - The serializer / API layer enforces which fields each role
        can read and write.

    Every field defaults to the privacy-protective state (``False``
    for data sharing, ``True`` for opt-outs).

    Important: A toggle here is only effective if the corresponding
    ``SystemFeatureToggle`` is globally enabled.  The permission layer
    checks both levels::

        system_toggle.is_enabled AND user_prefs.field == True
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="privacy_preferences",
    )

    # ── Shared Privacy Controls (all roles) ───────────────────────────
    allow_email_notifications = models.BooleanField(
        default=True,
        help_text="Receive transactional and marketing emails.",
    )
    allow_push_notifications = models.BooleanField(
        default=True,
        help_text="Receive push notifications on mobile/web.",
    )
    allow_sms_notifications = models.BooleanField(
        default=False,
        help_text="Receive SMS messages for booking updates.",
    )
    allow_analytics_tracking = models.BooleanField(
        default=False,
        help_text="Allow anonymized usage analytics collection.",
    )
    profile_visibility = models.CharField(
        max_length=16,
        choices=(
            ("private", "Private"),
            ("company", "Company Only"),
            ("public", "Public"),
        ),
        default="private",
        help_text="Who can see this user's profile details.",
    )

    # ── Resident-Specific Toggles ─────────────────────────────────────
    # (Only enforced when user.role == ROLE_RESIDENT)
    resident_share_address_with_pro = models.BooleanField(
        default=False,
        help_text="Share exact address with assigned Service Pro before job start.",
    )
    resident_allow_gps_tracking = models.BooleanField(
        default=False,
        help_text="Allow GPS-based ETA tracking for incoming Service Pros.",
    )
    resident_allow_iot_access = models.BooleanField(
        default=False,
        help_text="Grant smart-home device access (locks, cameras) to Service Pros.",
    )
    resident_allow_spatial_video = models.BooleanField(
        default=False,
        help_text="Allow spatial/360° video walkthrough for QA verification.",
    )
    resident_allow_ai_scoring = models.BooleanField(
        default=False,
        help_text="Allow AI-based cleanliness scoring of property images.",
    )
    resident_share_booking_history = models.BooleanField(
        default=False,
        help_text="Share booking history with assigned agency for personalization.",
    )

    # ── Service Pro-Specific Toggles ──────────────────────────────────
    # (Only enforced when user.role == ROLE_SERVICE_PRO)
    pro_allow_live_gps_tracking = models.BooleanField(
        default=False,
        help_text="Share real-time GPS location during active jobs.",
    )
    pro_allow_route_recording = models.BooleanField(
        default=False,
        help_text="Record travel routes for mileage tracking and optimization.",
    )
    pro_allow_availability_broadcast = models.BooleanField(
        default=True,
        help_text="Broadcast availability status to agency dispatchers.",
    )
    pro_allow_performance_analytics = models.BooleanField(
        default=False,
        help_text="Allow AI-generated performance scoring and ranking.",
    )
    pro_allow_client_reviews_public = models.BooleanField(
        default=True,
        help_text="Make client reviews of this Service Pro publicly visible.",
    )
    pro_allow_photo_verification = models.BooleanField(
        default=True,
        help_text="Allow photo-based job verification (before/after).",
    )

    # ── Override Tracking ─────────────────────────────────────────────
    is_overridden = models.BooleanField(
        default=False,
        help_text="True when a Break-Glass session has overridden these preferences.",
    )
    overridden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="privacy_overrides_applied",
    )
    overridden_at = models.DateTimeField(null=True, blank=True)
    override_reason = models.TextField(
        blank=True, default="",
        help_text="Justification recorded during break-glass override.",
    )
    override_expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the override auto-reverts.",
    )

    # ── Timestamps ────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Privacy Preferences"
        verbose_name_plural = "Privacy Preferences"
        indexes = [
            models.Index(fields=["user"], name="idx_privacy_user"),
            models.Index(fields=["is_overridden"], name="idx_privacy_overridden"),
        ]

    def __str__(self):
        return f"Privacy prefs for {self.user.email}"

    @property
    def is_override_active(self) -> bool:
        """Check if a break-glass override is currently in effect."""
        if not self.is_overridden:
            return False
        if self.override_expires_at and timezone.now() >= self.override_expires_at:
            return False
        return True

    def revert_override(self):
        """Clear the override state (called when BG session expires)."""
        self.is_overridden = False
        self.overridden_by = None
        self.overridden_at = None
        self.override_reason = ""
        self.override_expires_at = None
        self.save(update_fields=[
            "is_overridden", "overridden_by", "overridden_at",
            "override_reason", "override_expires_at", "updated_at",
        ])

    def get_effective_toggles(self, user_role: int) -> dict:
        """
        Return the effective privacy state as a flat dict, filtered
        by role.  Checks global system toggles as the outer gate.
        """
        from apps.users.models import User

        shared = {
            "allow_email_notifications": self.allow_email_notifications,
            "allow_push_notifications": (
                self.allow_push_notifications
                and SystemFeatureToggle.is_feature_active("push_notifications_enabled")
            ),
            "allow_sms_notifications": self.allow_sms_notifications,
            "allow_analytics_tracking": self.allow_analytics_tracking,
            "profile_visibility": self.profile_visibility,
        }

        if user_role == User.ROLE_RESIDENT:
            gps_global = SystemFeatureToggle.is_feature_active("global_gps_enabled")
            iot_global = SystemFeatureToggle.is_feature_active("global_iot_access_enabled")
            spatial_global = SystemFeatureToggle.is_feature_active("spatial_video_enabled")
            ai_global = SystemFeatureToggle.is_feature_active("ai_quality_scoring_enabled")

            shared.update({
                "resident_share_address_with_pro": self.resident_share_address_with_pro,
                "resident_allow_gps_tracking": self.resident_allow_gps_tracking and gps_global,
                "resident_allow_iot_access": self.resident_allow_iot_access and iot_global,
                "resident_allow_spatial_video": self.resident_allow_spatial_video and spatial_global,
                "resident_allow_ai_scoring": self.resident_allow_ai_scoring and ai_global,
                "resident_share_booking_history": self.resident_share_booking_history,
            })

        elif user_role == User.ROLE_SERVICE_PRO:
            gps_global = SystemFeatureToggle.is_feature_active("global_gps_enabled")
            ai_global = SystemFeatureToggle.is_feature_active("ai_quality_scoring_enabled")

            shared.update({
                "pro_allow_live_gps_tracking": self.pro_allow_live_gps_tracking and gps_global,
                "pro_allow_route_recording": self.pro_allow_route_recording and gps_global,
                "pro_allow_availability_broadcast": self.pro_allow_availability_broadcast,
                "pro_allow_performance_analytics": self.pro_allow_performance_analytics and ai_global,
                "pro_allow_client_reviews_public": self.pro_allow_client_reviews_public,
                "pro_allow_photo_verification": self.pro_allow_photo_verification,
            })

        return shared


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. BreakGlassSession — Time-Limited Escalation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class BreakGlassSession(models.Model):
    """
    A time-boxed escalation session that grants a Support Architect
    temporary override capability over a target user's privacy prefs.

    Lifecycle::

        PENDING → ACTIVE → (EXPIRED | REVOKED)
                       ↘ REVOKED (manual early termination)

    Security constraints:
      - Max duration: 4 hours (configurable via BREAK_GLASS_MAX_HOURS)
      - Only Support Architects (role=50) can initiate
      - Only Platform Admins (role=20) can revoke early
      - The global ``break_glass_enabled`` toggle must be ON
      - A reason and linked escalation/job ID is mandatory
      - All actions produce GovernanceAuditLog entries
    """

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending Activation"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_REVOKED, "Revoked"),
    )

    # Maximum override duration in hours
    MAX_DURATION_HOURS = getattr(settings, "BREAK_GLASS_MAX_HOURS", 4)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who is requesting the override
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="break_glass_initiated",
        help_text="The Support Architect who initiated this session.",
    )
    # Whose privacy is being overridden
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="break_glass_targeted",
        help_text="The user whose privacy preferences are overridden.",
    )

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )

    # Justification
    reason = models.TextField(
        help_text="Mandatory justification (e.g., 'Service Pro unresponsive, "
                  "need GPS ping for safety check').",
    )
    escalation_reference = models.CharField(
        max_length=128, blank=True, default="",
        help_text="Ticket ID, booking ID, or job reference that justifies this.",
    )

    # Which toggles were overridden
    overrides_applied = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Snapshot of which fields were overridden and their "
            "original values.  e.g. {'pro_allow_live_gps_tracking': "
            "{'original': False, 'overridden_to': True}}"
        ),
    )

    # Time boundaries
    requested_duration_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Requested duration in minutes (capped at MAX_DURATION_HOURS).",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="break_glass_revoked",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Break-Glass Session"
        verbose_name_plural = "Break-Glass Sessions"
        indexes = [
            models.Index(fields=["status", "expires_at"], name="idx_bg_status_expiry"),
            models.Index(fields=["target_user", "status"], name="idx_bg_target_status"),
            models.Index(fields=["initiated_by"], name="idx_bg_initiator"),
        ]

    def __str__(self):
        return (
            f"BG-{str(self.id)[:8]} | {self.initiated_by.email} → "
            f"{self.target_user.email} [{self.status}]"
        )

    def clean(self):
        from apps.users.models import User

        if self.initiated_by.role != User.ROLE_SUPPORT_ARCHITECT:
            raise ValidationError(
                "Only Support Architects can initiate break-glass sessions."
            )

        max_minutes = self.MAX_DURATION_HOURS * 60
        if self.requested_duration_minutes > max_minutes:
            raise ValidationError(
                f"Requested duration exceeds maximum of {max_minutes} minutes "
                f"({self.MAX_DURATION_HOURS} hours)."
            )

        if not self.reason or len(self.reason.strip()) < 20:
            raise ValidationError(
                "A detailed justification (minimum 20 characters) is required."
            )

    @property
    def is_active(self) -> bool:
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at and timezone.now() >= self.expires_at:
            return False
        return True

    def activate(self):
        """Transition from PENDING to ACTIVE and apply overrides."""
        if self.status != self.STATUS_PENDING:
            raise ValidationError(f"Cannot activate a session in '{self.status}' state.")

        if not SystemFeatureToggle.is_feature_active("break_glass_enabled"):
            raise ValidationError("The break-glass system is globally disabled.")

        now = timezone.now()
        max_minutes = self.MAX_DURATION_HOURS * 60
        duration = min(self.requested_duration_minutes, max_minutes)

        self.status = self.STATUS_ACTIVE
        self.activated_at = now
        self.expires_at = now + timedelta(minutes=duration)
        self.save(update_fields=[
            "status", "activated_at", "expires_at", "updated_at",
        ])

    def revoke(self, revoked_by_user):
        """Early termination of an active session."""
        if self.status != self.STATUS_ACTIVE:
            raise ValidationError("Can only revoke an active session.")

        self.status = self.STATUS_REVOKED
        self.revoked_at = timezone.now()
        self.revoked_by = revoked_by_user
        self.save(update_fields=[
            "status", "revoked_at", "revoked_by", "updated_at",
        ])

    def expire(self):
        """Called by a cron/celery task or checked lazily."""
        if self.status == self.STATUS_ACTIVE:
            self.status = self.STATUS_EXPIRED
            self.save(update_fields=["status", "updated_at"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. GovernanceAuditLog — Immutable Audit Trail
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GovernanceAuditLog(models.Model):
    """
    Append-only, immutable audit record for every governance action.

    Immutability enforced at the ORM level:
      - ``save()`` raises on update attempts
      - ``delete()`` always raises
      - Django admin is read-only
      - Only Platform Admins can query this via the API

    Every privacy toggle change, break-glass action, and system
    feature toggle mutation produces an entry here.
    """

    # ── Action taxonomy ───────────────────────────────────────────────
    ACTION_FEATURE_TOGGLED = "feature_toggled"
    ACTION_PRIVACY_UPDATED = "privacy_updated"
    ACTION_BREAK_GLASS_REQUESTED = "break_glass_requested"
    ACTION_BREAK_GLASS_ACTIVATED = "break_glass_activated"
    ACTION_BREAK_GLASS_REVOKED = "break_glass_revoked"
    ACTION_BREAK_GLASS_EXPIRED = "break_glass_expired"
    ACTION_OVERRIDE_APPLIED = "override_applied"
    ACTION_OVERRIDE_REVERTED = "override_reverted"
    ACTION_EMERGENCY_REVOCATION = "emergency_access_revocation"
    ACTION_EMERGENCY_LOCKOUT = "emergency_lockout"
    ACTION_CHOICES = (
        (ACTION_FEATURE_TOGGLED, "System Feature Toggled"),
        (ACTION_PRIVACY_UPDATED, "Privacy Preferences Updated"),
        (ACTION_BREAK_GLASS_REQUESTED, "Break-Glass Requested"),
        (ACTION_BREAK_GLASS_ACTIVATED, "Break-Glass Activated"),
        (ACTION_BREAK_GLASS_REVOKED, "Break-Glass Revoked"),
        (ACTION_BREAK_GLASS_EXPIRED, "Break-Glass Expired"),
        (ACTION_OVERRIDE_APPLIED, "Privacy Override Applied"),
        (ACTION_OVERRIDE_REVERTED, "Privacy Override Reverted"),
        (ACTION_EMERGENCY_REVOCATION, "Emergency Access Revocation"),
        (ACTION_EMERGENCY_LOCKOUT, "Emergency Lockout"),
    )

    # ── Severity ──────────────────────────────────────────────────────
    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_CRITICAL = "critical"
    SEVERITY_CHOICES = (
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_CRITICAL, "Critical"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who performed the action
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="governance_audit_logs",
        help_text="The user who performed this action (null for system actions).",
    )
    actor_email = models.EmailField(
        blank=True, default="",
        help_text="Snapshot of actor email at time of action (survives user deletion).",
    )
    actor_role = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Actor's role at time of action.",
    )

    # What happened
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, db_index=True)
    severity = models.CharField(
        max_length=12, choices=SEVERITY_CHOICES, default=SEVERITY_INFO,
    )
    description = models.TextField(
        help_text="Human-readable description of what happened.",
    )

    # Who/what was affected
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="governance_audit_targeted",
        help_text="The user whose data was affected (if applicable).",
    )
    target_user_email = models.EmailField(
        blank=True, default="",
        help_text="Snapshot of target email at time of action.",
    )

    # Structured change data
    changes = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Machine-readable change record.  For toggles: "
            "{'field': 'is_enabled', 'old': False, 'new': True}.  "
            "For privacy: {'field': 'resident_allow_gps', 'old': False, 'new': True}."
        ),
    )

    # Reference to related objects
    related_feature_toggle = models.ForeignKey(
        SystemFeatureToggle,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    related_break_glass = models.ForeignKey(
        BreakGlassSession,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )

    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    # Timestamp (not auto_now — we set it explicitly and it never changes)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Governance Audit Log"
        verbose_name_plural = "Governance Audit Logs"
        indexes = [
            models.Index(fields=["action", "timestamp"], name="idx_audit_action_ts"),
            models.Index(fields=["actor", "timestamp"], name="idx_audit_actor_ts"),
            models.Index(fields=["target_user", "timestamp"], name="idx_audit_target_ts"),
            models.Index(fields=["severity"], name="idx_audit_severity"),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.action} by {self.actor_email} @ {self.timestamp}"

    def save(self, *args, **kwargs):
        """Enforce append-only: block updates to existing records."""
        if self.pk and GovernanceAuditLog.objects.filter(pk=self.pk).exists():
            raise ValidationError(
                "Audit log entries are immutable and cannot be modified."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Block all deletions at the ORM level."""
        raise ValidationError(
            "Audit log entries are immutable and cannot be deleted."
        )

    @classmethod
    def log(
        cls,
        action: str,
        description: str,
        actor=None,
        target_user=None,
        changes: dict | None = None,
        severity: str = SEVERITY_INFO,
        related_feature_toggle=None,
        related_break_glass=None,
        ip_address: str | None = None,
        user_agent: str = "",
    ):
        """
        Factory method for creating audit entries.  Snapshots actor/target
        email at creation time so the record survives user deletion.
        """
        return cls.objects.create(
            actor=actor,
            actor_email=getattr(actor, "email", "") if actor else "",
            actor_role=getattr(actor, "role", None) if actor else None,
            action=action,
            severity=severity,
            description=description,
            target_user=target_user,
            target_user_email=getattr(target_user, "email", "") if target_user else "",
            changes=changes or {},
            related_feature_toggle=related_feature_toggle,
            related_break_glass=related_break_glass,
            ip_address=ip_address,
            user_agent=user_agent,
        )
