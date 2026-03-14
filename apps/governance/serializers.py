"""
Governance Serializers
======================

DRF serializers for system feature toggles, privacy preferences,
break-glass sessions, and audit logs.

The privacy serializer uses role-aware field filtering — Residents
see only ``resident_*`` fields, Service Pros see only ``pro_*``
fields, and Platform Admins see everything.
"""

from django.utils import timezone
from rest_framework import serializers

from apps.users.models import User
from .models import (
    BreakGlassSession,
    GovernanceAuditLog,
    PrivacyPreferences,
    SystemFeatureToggle,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SystemFeatureToggle
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SystemFeatureToggleSerializer(serializers.ModelSerializer):
    toggled_by_email = serializers.EmailField(
        source="toggled_by.email", read_only=True, default="",
    )

    class Meta:
        model = SystemFeatureToggle
        fields = (
            "id", "slug", "name", "description",
            "category", "severity",
            "is_enabled",
            "toggled_by", "toggled_by_email", "toggled_at",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "slug", "name", "description", "category", "severity",
            "toggled_by", "toggled_by_email", "toggled_at",
            "created_at", "updated_at",
        )

    def update(self, instance, validated_data):
        """Only ``is_enabled`` can be toggled by the admin."""
        request = self.context.get("request")
        if "is_enabled" in validated_data:
            instance.is_enabled = validated_data["is_enabled"]
            instance.toggled_by = request.user if request else None
            instance.toggled_at = timezone.now()
            instance.save(update_fields=[
                "is_enabled", "toggled_by", "toggled_at", "updated_at",
            ])
        return instance


class SystemFeatureToggleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing all toggles."""

    class Meta:
        model = SystemFeatureToggle
        fields = (
            "id", "slug", "name", "category", "severity",
            "is_enabled", "toggled_at",
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PrivacyPreferences — Role-Polymorphic
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Define which fields each role can see and edit
SHARED_PRIVACY_FIELDS = (
    "allow_email_notifications", "allow_push_notifications",
    "allow_sms_notifications", "allow_analytics_tracking",
    "profile_visibility",
)

RESIDENT_PRIVACY_FIELDS = (
    "resident_share_address_with_pro", "resident_allow_gps_tracking",
    "resident_allow_iot_access", "resident_allow_spatial_video",
    "resident_allow_ai_scoring", "resident_share_booking_history",
)

PRO_PRIVACY_FIELDS = (
    "pro_allow_live_gps_tracking", "pro_allow_route_recording",
    "pro_allow_availability_broadcast", "pro_allow_performance_analytics",
    "pro_allow_client_reviews_public", "pro_allow_photo_verification",
)

OVERRIDE_READ_FIELDS = (
    "is_overridden", "overridden_at", "override_reason",
    "override_expires_at",
)

BASE_READ_FIELDS = ("id", "user", "created_at", "updated_at")


class PrivacyPreferencesSerializer(serializers.ModelSerializer):
    """
    Dynamically adjusts visible fields based on the requesting
    user's role.  Uses ``get_fields()`` to strip inapplicable fields.
    """

    user_email = serializers.EmailField(source="user.email", read_only=True)
    effective_toggles = serializers.SerializerMethodField()
    is_override_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = PrivacyPreferences
        fields = (
            *BASE_READ_FIELDS,
            "user_email",
            *SHARED_PRIVACY_FIELDS,
            *RESIDENT_PRIVACY_FIELDS,
            *PRO_PRIVACY_FIELDS,
            *OVERRIDE_READ_FIELDS,
            "effective_toggles",
            "is_override_active",
        )
        read_only_fields = (
            *BASE_READ_FIELDS,
            "user_email",
            *OVERRIDE_READ_FIELDS,
            "effective_toggles",
            "is_override_active",
        )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return fields

        user_role = request.user.role

        # Platform Admin sees everything
        if user_role == User.ROLE_PLATFORM_ADMIN and request.user.is_superuser:
            return fields

        # Support Architect sees everything (read-only in normal mode)
        if user_role == User.ROLE_SUPPORT_ARCHITECT:
            return fields

        # Resident: strip pro fields
        if user_role == User.ROLE_RESIDENT:
            for f in PRO_PRIVACY_FIELDS:
                fields.pop(f, None)

        # Service Pro: strip resident fields
        elif user_role == User.ROLE_SERVICE_PRO:
            for f in RESIDENT_PRIVACY_FIELDS:
                fields.pop(f, None)

        # Other roles: strip both role-specific sets
        else:
            for f in (*RESIDENT_PRIVACY_FIELDS, *PRO_PRIVACY_FIELDS):
                fields.pop(f, None)

        return fields

    def get_effective_toggles(self, obj):
        """Compute the effective state considering global toggles."""
        return obj.get_effective_toggles(obj.user.role)

    def update(self, instance, validated_data):
        """Tag the actor for audit logging."""
        request = self.context.get("request")
        if request:
            instance._changed_by = request.user
        return super().update(instance, validated_data)


class PrivacyPreferencesAdminSerializer(serializers.ModelSerializer):
    """Full read-write for Platform Admin privacy management."""

    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = PrivacyPreferences
        fields = "__all__"
        read_only_fields = ("id", "user", "created_at", "updated_at")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BreakGlassSession
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class BreakGlassRequestSerializer(serializers.ModelSerializer):
    """Used by Support Architects to request a new break-glass session."""

    class Meta:
        model = BreakGlassSession
        fields = (
            "target_user", "reason", "escalation_reference",
            "requested_duration_minutes",
        )

    def validate_target_user(self, value):
        if value.role not in (User.ROLE_RESIDENT, User.ROLE_SERVICE_PRO):
            raise serializers.ValidationError(
                "Break-glass can only target Residents or Service Pros."
            )
        return value

    def validate_reason(self, value):
        if len(value.strip()) < 20:
            raise serializers.ValidationError(
                "Justification must be at least 20 characters."
            )
        return value

    def validate_requested_duration_minutes(self, value):
        max_min = BreakGlassSession.MAX_DURATION_HOURS * 60
        if value > max_min:
            raise serializers.ValidationError(
                f"Maximum duration is {max_min} minutes ({BreakGlassSession.MAX_DURATION_HOURS} hours)."
            )
        if value < 5:
            raise serializers.ValidationError("Minimum duration is 5 minutes.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["initiated_by"] = request.user
        return super().create(validated_data)


class BreakGlassSessionSerializer(serializers.ModelSerializer):
    """Full read serializer for break-glass sessions."""

    initiated_by_email = serializers.EmailField(
        source="initiated_by.email", read_only=True,
    )
    target_user_email = serializers.EmailField(
        source="target_user.email", read_only=True,
    )
    revoked_by_email = serializers.EmailField(
        source="revoked_by.email", read_only=True, default="",
    )
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = BreakGlassSession
        fields = (
            "id", "initiated_by", "initiated_by_email",
            "target_user", "target_user_email",
            "status", "reason", "escalation_reference",
            "overrides_applied",
            "requested_duration_minutes",
            "activated_at", "expires_at",
            "revoked_at", "revoked_by", "revoked_by_email",
            "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = fields


class BreakGlassOverrideSerializer(serializers.Serializer):
    """
    Payload for applying a privacy override during an active BG session.
    The caller specifies which fields to force-enable.
    """

    session_id = serializers.UUIDField()
    overrides = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=(
            "Map of privacy field names to their override values.  "
            "e.g. {'pro_allow_live_gps_tracking': true}"
        ),
    )

    def validate_session_id(self, value):
        try:
            session = BreakGlassSession.objects.get(pk=value)
        except BreakGlassSession.DoesNotExist:
            raise serializers.ValidationError("Break-glass session not found.")

        if not session.is_active:
            raise serializers.ValidationError(
                "This break-glass session is no longer active."
            )
        return value

    def validate_overrides(self, value):
        all_overridable = set(RESIDENT_PRIVACY_FIELDS + PRO_PRIVACY_FIELDS)
        invalid = set(value.keys()) - all_overridable
        if invalid:
            raise serializers.ValidationError(
                f"Cannot override fields: {', '.join(invalid)}"
            )
        return value


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GovernanceAuditLog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GovernanceAuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for the immutable audit trail."""

    class Meta:
        model = GovernanceAuditLog
        fields = (
            "id", "actor", "actor_email", "actor_role",
            "action", "severity", "description",
            "target_user", "target_user_email",
            "changes",
            "related_feature_toggle", "related_break_glass",
            "ip_address", "user_agent",
            "timestamp",
        )
        read_only_fields = fields
