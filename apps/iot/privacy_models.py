"""
Location Privacy & Fleet Management Models
============================================

Models for Service Pro location privacy controls and Agency Owner
fleet management enforcement:

  GhostModeState      — Tracks whether a Service Pro has Ghost Mode active
  StrictTrackingRule   — Agency Owner per-pro enforcement (disables Ghost Mode)
  GPSHistoryLog        — Immutable GPS breadcrumb trail for dispute resolution
  GhostModeAlert       — Records alerts sent when Ghost Mode conflicts with a job

Design decisions:
  • ``GhostModeState`` is a per-user singleton (one record per Service Pro).
    This avoids scanning large tables; Ghost Mode is either ON or OFF globally
    for that pro.  The WebSocket consumer and HTTP views consult this before
    broadcasting coordinates.

  • ``StrictTrackingRule`` is a per-(agency_owner, service_pro) pair.
    When ``is_enforced=True``, the Service Pro's Ghost Mode toggle is locked off
    during active shifts — even if they attempt to enable it, the backend refuses.

  • ``GPSHistoryLog`` stores individual GPS pings for audit.  Platform Admins
    can query these for dispute resolution.  A Celery periodic task purges
    rows older than 30 days for GDPR / data-minimization compliance.

  • ``GhostModeAlert`` is append-only — records every instance where a
    Service Pro had Ghost Mode active during a scheduled booking window,
    triggering automatic notification to the Agency Owner.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Ghost Mode State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GhostModeState(models.Model):
    """
    Singleton per Service Pro — tracks whether Ghost Mode is currently active.

    When ``is_active=True``, the platform pauses live GPS broadcasting for
    this Service Pro.  If Ghost Mode activates during a scheduled booking
    window, the system alerts the Agency Owner and requires a manual check-in.
    """

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    service_pro = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ghost_mode_state",
        help_text="The Service Pro this Ghost Mode state belongs to.",
    )

    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True when the Service Pro has paused live GPS broadcasting.",
    )
    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when Ghost Mode was last activated.",
    )
    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when Ghost Mode was last deactivated.",
    )

    # Manual check-in tracking
    last_manual_checkin_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last manual geographic check-in during Ghost Mode.",
    )
    last_manual_checkin_lat = models.FloatField(null=True, blank=True)
    last_manual_checkin_lng = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ghost Mode State"
        verbose_name_plural = "Ghost Mode States"

    def __str__(self):
        status = "ACTIVE" if self.is_active else "OFF"
        return f"GhostMode({self.service_pro.email}) = {status}"

    def activate(self):
        """Turn Ghost Mode on."""
        self.is_active = True
        self.activated_at = timezone.now()
        self.save(update_fields=["is_active", "activated_at", "updated_at"])

    def deactivate(self):
        """Turn Ghost Mode off."""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=["is_active", "deactivated_at", "updated_at"])

    def record_manual_checkin(self, lat: float, lng: float):
        """Record a manual geographic check-in during Ghost Mode."""
        self.last_manual_checkin_at = timezone.now()
        self.last_manual_checkin_lat = lat
        self.last_manual_checkin_lng = lng
        self.save(update_fields=[
            "last_manual_checkin_at",
            "last_manual_checkin_lat",
            "last_manual_checkin_lng",
            "updated_at",
        ])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Strict Tracking Rule (Agency Owner Enforcement)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class StrictTrackingRule(models.Model):
    """
    Per-Service Pro enforcement rule set by an Agency Owner.

    When ``is_enforced=True``, the Service Pro cannot enable Ghost Mode
    during any active shift (booking window).  The backend will reject
    the toggle request and return a 403.

    The Agency Owner can override this on their fleet management dashboard.
    """

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    agency_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="strict_tracking_rules",
        help_text="The Agency Owner who created this rule.",
    )
    service_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="strict_tracking_rules_received",
        help_text="The Service Pro this rule applies to.",
    )

    is_enforced = models.BooleanField(
        default=True,
        db_index=True,
        help_text="If True, the Service Pro cannot activate Ghost Mode during shifts.",
    )
    reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional reason for enforcing or relaxing strict tracking.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("agency_owner", "service_pro")
        verbose_name = "Strict Tracking Rule"
        verbose_name_plural = "Strict Tracking Rules"

    def __str__(self):
        status = "ENFORCED" if self.is_enforced else "RELAXED"
        return (
            f"StrictTracking({self.service_pro.email}) "
            f"by {self.agency_owner.email} = {status}"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GPS History Log (for Platform Admin dispute resolution)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GPSHistoryLog(models.Model):
    """
    Immutable GPS breadcrumb trail.

    Every GPS update (WebSocket or HTTP) appends a row here.  Platform Admins
    can query these logs for dispute resolution.

    A Celery periodic task (``scrub_old_gps_history``) auto-deletes rows
    older than 30 days for data-minimization compliance.
    """

    id = models.BigAutoField(primary_key=True)

    service_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gps_history_logs",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="gps_history_logs",
        null=True,
        blank=True,
    )

    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy_meters = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    speed_mps = models.FloatField(null=True, blank=True)

    # Whether Ghost Mode was active at the time of this log entry
    ghost_mode_active = models.BooleanField(
        default=False,
        help_text="Was Ghost Mode active when this coordinate was recorded?",
    )

    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(
                fields=["service_pro", "recorded_at"],
                name="idx_gps_hist_pro_time",
            ),
            models.Index(
                fields=["booking", "recorded_at"],
                name="idx_gps_hist_booking_time",
            ),
        ]

    def __str__(self):
        return (
            f"GPSLog: {self.service_pro.email} @ "
            f"({self.latitude:.6f}, {self.longitude:.6f}) "
            f"[{self.recorded_at.isoformat()}]"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Ghost Mode Alert
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GhostModeAlert(models.Model):
    """
    Append-only record of Ghost Mode conflict alerts.

    Created when a Service Pro activates Ghost Mode during a scheduled
    booking window.  The Agency Owner is notified, and the Pro must
    perform a manual geographic check-in to resolve the conflict.
    """

    ALERT_GHOST_DURING_JOB = "ghost_during_job"
    ALERT_MANUAL_CHECKIN = "manual_checkin"
    ALERT_TYPE_CHOICES = [
        (ALERT_GHOST_DURING_JOB, "Ghost Mode Active During Scheduled Job"),
        (ALERT_MANUAL_CHECKIN, "Manual Check-In Completed"),
    ]

    RESOLUTION_PENDING = "pending"
    RESOLUTION_CHECKED_IN = "checked_in"
    RESOLUTION_DISMISSED = "dismissed"
    RESOLUTION_ESCALATED = "escalated"
    RESOLUTION_CHOICES = [
        (RESOLUTION_PENDING, "Pending"),
        (RESOLUTION_CHECKED_IN, "Checked In"),
        (RESOLUTION_DISMISSED, "Dismissed"),
        (RESOLUTION_ESCALATED, "Escalated"),
    ]

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    service_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ghost_mode_alerts",
    )
    agency_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ghost_mode_alerts_received",
        null=True,
        blank=True,
        help_text="The Agency Owner who was notified.",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="ghost_mode_alerts",
        null=True,
        blank=True,
    )

    alert_type = models.CharField(
        max_length=30,
        choices=ALERT_TYPE_CHOICES,
        default=ALERT_GHOST_DURING_JOB,
        db_index=True,
    )
    resolution = models.CharField(
        max_length=20,
        choices=RESOLUTION_CHOICES,
        default=RESOLUTION_PENDING,
        db_index=True,
    )

    message = models.TextField(
        blank=True,
        default="",
        help_text="Human-readable alert message.",
    )
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["agency_owner", "resolution"],
                name="idx_ghost_alert_owner_res",
            ),
        ]

    def __str__(self):
        return (
            f"GhostAlert: {self.service_pro.email} — "
            f"{self.get_alert_type_display()} [{self.resolution}]"
        )
