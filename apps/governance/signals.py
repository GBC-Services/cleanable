"""
Governance Audit Signals
========================

Django signal handlers that automatically create immutable audit log
entries whenever governance-critical models are saved.

Signal flow::

    SystemFeatureToggle.save()  →  post_save  →  GovernanceAuditLog.log()
    PrivacyPreferences.save()   →  post_save  →  GovernanceAuditLog.log()
    BreakGlassSession.save()    →  post_save  →  GovernanceAuditLog.log()

The ``_get_changes()`` helper diffs the pre-save snapshot against the
current state to produce a structured change record.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import (
    BreakGlassSession,
    GovernanceAuditLog,
    PrivacyPreferences,
    SystemFeatureToggle,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Pre-save: Snapshot previous state for diff
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _snapshot_fields(instance, fields: list[str]) -> dict:
    """Read current DB values before the save overwrites them."""
    if not instance.pk:
        return {}
    try:
        db_instance = type(instance).objects.get(pk=instance.pk)
        return {f: getattr(db_instance, f) for f in fields}
    except type(instance).DoesNotExist:
        return {}


TOGGLE_TRACKED_FIELDS = ["is_enabled"]

PRIVACY_TRACKED_FIELDS = [
    "allow_email_notifications", "allow_push_notifications",
    "allow_sms_notifications", "allow_analytics_tracking",
    "profile_visibility",
    # Resident
    "resident_share_address_with_pro", "resident_allow_gps_tracking",
    "resident_allow_iot_access", "resident_allow_spatial_video",
    "resident_allow_ai_scoring", "resident_share_booking_history",
    # Service Pro
    "pro_allow_live_gps_tracking", "pro_allow_route_recording",
    "pro_allow_availability_broadcast", "pro_allow_performance_analytics",
    "pro_allow_client_reviews_public", "pro_allow_photo_verification",
    # Override state
    "is_overridden",
]


@receiver(pre_save, sender=SystemFeatureToggle)
def snapshot_feature_toggle(sender, instance, **kwargs):
    instance._pre_save_snapshot = _snapshot_fields(instance, TOGGLE_TRACKED_FIELDS)


@receiver(pre_save, sender=PrivacyPreferences)
def snapshot_privacy_prefs(sender, instance, **kwargs):
    instance._pre_save_snapshot = _snapshot_fields(instance, PRIVACY_TRACKED_FIELDS)


@receiver(pre_save, sender=BreakGlassSession)
def snapshot_break_glass(sender, instance, **kwargs):
    instance._pre_save_snapshot = _snapshot_fields(instance, ["status"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Post-save: Produce audit log entries
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _compute_changes(instance, tracked_fields: list[str]) -> dict:
    """Compare pre-save snapshot with current values."""
    snapshot = getattr(instance, "_pre_save_snapshot", {})
    if not snapshot:
        return {}

    changes = {}
    for field in tracked_fields:
        old_val = snapshot.get(field)
        new_val = getattr(instance, field, None)
        if old_val != new_val:
            changes[field] = {"old": old_val, "new": new_val}
    return changes


@receiver(post_save, sender=SystemFeatureToggle)
def audit_feature_toggle(sender, instance, created, **kwargs):
    """Log every feature toggle creation or mutation."""
    if created:
        GovernanceAuditLog.log(
            action=GovernanceAuditLog.ACTION_FEATURE_TOGGLED,
            description=f"System feature '{instance.name}' created (enabled={instance.is_enabled}).",
            actor=instance.toggled_by,
            changes={"is_enabled": {"old": None, "new": instance.is_enabled}},
            severity=GovernanceAuditLog.SEVERITY_INFO,
            related_feature_toggle=instance,
        )
        return

    changes = _compute_changes(instance, TOGGLE_TRACKED_FIELDS)
    if not changes:
        return

    severity = GovernanceAuditLog.SEVERITY_WARNING
    if instance.severity in ("high", "critical"):
        severity = GovernanceAuditLog.SEVERITY_CRITICAL

    state = "ENABLED" if instance.is_enabled else "DISABLED"
    GovernanceAuditLog.log(
        action=GovernanceAuditLog.ACTION_FEATURE_TOGGLED,
        description=f"System feature '{instance.name}' {state} by {getattr(instance.toggled_by, 'email', 'system')}.",
        actor=instance.toggled_by,
        changes=changes,
        severity=severity,
        related_feature_toggle=instance,
    )


@receiver(post_save, sender=PrivacyPreferences)
def audit_privacy_update(sender, instance, created, **kwargs):
    """Log privacy preference changes."""
    if created:
        GovernanceAuditLog.log(
            action=GovernanceAuditLog.ACTION_PRIVACY_UPDATED,
            description=f"Privacy preferences created for {instance.user.email}.",
            target_user=instance.user,
            severity=GovernanceAuditLog.SEVERITY_INFO,
        )
        return

    changes = _compute_changes(instance, PRIVACY_TRACKED_FIELDS)
    if not changes:
        return

    # Detect override application vs. normal update
    if "is_overridden" in changes and changes["is_overridden"]["new"] is True:
        GovernanceAuditLog.log(
            action=GovernanceAuditLog.ACTION_OVERRIDE_APPLIED,
            description=(
                f"Privacy override applied to {instance.user.email} "
                f"by {getattr(instance.overridden_by, 'email', 'unknown')}. "
                f"Reason: {instance.override_reason}"
            ),
            actor=instance.overridden_by,
            target_user=instance.user,
            changes=changes,
            severity=GovernanceAuditLog.SEVERITY_CRITICAL,
        )
    elif "is_overridden" in changes and changes["is_overridden"]["new"] is False:
        GovernanceAuditLog.log(
            action=GovernanceAuditLog.ACTION_OVERRIDE_REVERTED,
            description=f"Privacy override reverted for {instance.user.email}.",
            target_user=instance.user,
            changes=changes,
            severity=GovernanceAuditLog.SEVERITY_WARNING,
        )
    else:
        # Determine who made the change
        actor = getattr(instance, "_changed_by", None)
        GovernanceAuditLog.log(
            action=GovernanceAuditLog.ACTION_PRIVACY_UPDATED,
            description=f"Privacy preferences updated for {instance.user.email}.",
            actor=actor,
            target_user=instance.user,
            changes=changes,
            severity=GovernanceAuditLog.SEVERITY_INFO,
        )


@receiver(post_save, sender=BreakGlassSession)
def audit_break_glass(sender, instance, created, **kwargs):
    """Log break-glass session lifecycle events."""
    if created:
        GovernanceAuditLog.log(
            action=GovernanceAuditLog.ACTION_BREAK_GLASS_REQUESTED,
            description=(
                f"Break-glass session requested by {instance.initiated_by.email} "
                f"targeting {instance.target_user.email}. Reason: {instance.reason}"
            ),
            actor=instance.initiated_by,
            target_user=instance.target_user,
            changes={
                "requested_duration_minutes": instance.requested_duration_minutes,
                "escalation_reference": instance.escalation_reference,
            },
            severity=GovernanceAuditLog.SEVERITY_CRITICAL,
            related_break_glass=instance,
        )
        return

    snapshot = getattr(instance, "_pre_save_snapshot", {})
    old_status = snapshot.get("status")
    new_status = instance.status

    if old_status == new_status:
        return

    action_map = {
        BreakGlassSession.STATUS_ACTIVE: GovernanceAuditLog.ACTION_BREAK_GLASS_ACTIVATED,
        BreakGlassSession.STATUS_REVOKED: GovernanceAuditLog.ACTION_BREAK_GLASS_REVOKED,
        BreakGlassSession.STATUS_EXPIRED: GovernanceAuditLog.ACTION_BREAK_GLASS_EXPIRED,
    }

    action = action_map.get(new_status)
    if not action:
        return

    actor = instance.revoked_by if new_status == BreakGlassSession.STATUS_REVOKED else instance.initiated_by

    GovernanceAuditLog.log(
        action=action,
        description=(
            f"Break-glass session {str(instance.id)[:8]} transitioned "
            f"from '{old_status}' to '{new_status}'."
        ),
        actor=actor,
        target_user=instance.target_user,
        changes={"status": {"old": old_status, "new": new_status}},
        severity=GovernanceAuditLog.SEVERITY_CRITICAL,
        related_break_glass=instance,
    )
