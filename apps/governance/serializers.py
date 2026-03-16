"""
Governance Serializers
======================

DRF serializers for system feature toggles, privacy preferences,
break-glass sessions, audit logs, secret vault, permission matrix,
and user security actions.

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
    NotificationPreference,
    PlatformIntegration,
    PrivacyPreferences,
    RolePermissionMatrix,
    SecretVault,
    SystemFeatureToggle,
    UserSecurityAction,
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PlatformIntegration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PlatformIntegrationSerializer(serializers.ModelSerializer):
    """Full serializer for Platform Admin CRUD on integrations."""

    toggled_by_email = serializers.EmailField(
        source="toggled_by.email", read_only=True, default="",
    )

    class Meta:
        model = PlatformIntegration
        fields = (
            "id", "slug", "name", "description",
            "category", "icon",
            "is_enabled", "config",
            "toggled_by", "toggled_by_email", "toggled_at",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "slug", "name", "description", "category", "icon",
            "toggled_by", "toggled_by_email", "toggled_at",
            "created_at", "updated_at",
        )

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if "is_enabled" in validated_data:
            instance.is_enabled = validated_data["is_enabled"]
            instance.toggled_by = request.user if request else None
            instance.toggled_at = timezone.now()
        if "config" in validated_data:
            instance.config = validated_data["config"]
        instance.save()
        return instance


class PlatformIntegrationListSerializer(serializers.ModelSerializer):
    """Lightweight list serializer."""

    class Meta:
        model = PlatformIntegration
        fields = (
            "id", "slug", "name", "category", "icon",
            "is_enabled", "toggled_at",
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  NotificationPreference
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Per-user notification matrix entry."""

    event_label = serializers.SerializerMethodField()
    event_category = serializers.SerializerMethodField()

    class Meta:
        model = NotificationPreference
        fields = (
            "id", "event_slug", "event_label", "event_category",
            "in_app", "sms", "email",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "event_slug", "event_label", "event_category",
            "created_at", "updated_at",
        )

    def get_event_label(self, obj):
        return dict(NotificationPreference.EVENT_CHOICES).get(
            obj.event_slug, obj.event_slug,
        )

    def get_event_category(self, obj):
        return NotificationPreference.EVENT_CATEGORY_MAP.get(
            obj.event_slug, "Other",
        )


class NotificationPreferenceBulkUpdateSerializer(serializers.Serializer):
    """
    Accepts a list of {event_slug, in_app, sms, email} dicts
    to bulk-update the user's notification matrix in one request.
    """

    preferences = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of {event_slug, in_app, sms, email} dicts.",
    )

    def validate_preferences(self, value):
        valid_slugs = {s for s, _ in NotificationPreference.EVENT_CHOICES}
        for item in value:
            if "event_slug" not in item:
                raise serializers.ValidationError(
                    "Each preference must include 'event_slug'."
                )
            if item["event_slug"] not in valid_slugs:
                raise serializers.ValidationError(
                    f"Unknown event slug: {item['event_slug']}"
                )
            for channel in ("in_app", "sms", "email"):
                if channel in item and not isinstance(item[channel], bool):
                    raise serializers.ValidationError(
                        f"'{channel}' must be a boolean."
                    )
        return value


class LifecycleEventSerializer(serializers.Serializer):
    """Read-only representation of a lifecycle event definition."""

    slug = serializers.CharField()
    label = serializers.CharField()
    category = serializers.CharField()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SecretVault
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SecretVaultSerializer(serializers.ModelSerializer):
    """
    Full serializer for vault entries.  NEVER exposes encrypted_value.
    Uses masked_value for display.
    """

    masked_value = serializers.CharField(read_only=True)
    is_due_for_rotation = serializers.BooleanField(read_only=True)
    created_by_email = serializers.EmailField(
        source="created_by.email", read_only=True, default="",
    )
    revoked_by_email = serializers.EmailField(
        source="revoked_by.email", read_only=True, default="",
    )

    class Meta:
        model = SecretVault
        fields = (
            "id", "label", "provider", "scope", "environment", "status",
            "masked_value", "key_prefix", "key_hint",
            "auto_rotate", "rotation_interval_days",
            "last_rotated_at", "next_rotation_at", "rotation_count",
            "created_by", "created_by_email",
            "revoked_by", "revoked_by_email", "revoked_at", "revoke_reason",
            "notes",
            "is_due_for_rotation",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "masked_value", "key_prefix", "key_hint",
            "last_rotated_at", "next_rotation_at", "rotation_count",
            "created_by", "created_by_email",
            "revoked_by", "revoked_by_email", "revoked_at", "revoke_reason",
            "is_due_for_rotation",
            "created_at", "updated_at",
        )


class SecretVaultCreateSerializer(serializers.ModelSerializer):
    """Create serializer — accepts the raw key value."""

    class Meta:
        model = SecretVault
        fields = (
            "label", "provider", "scope", "environment",
            "encrypted_value",
            "auto_rotate", "rotation_interval_days",
            "notes",
        )

    def create(self, validated_data):
        request = self.context.get("request")
        if request:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


class SecretVaultRotateSerializer(serializers.Serializer):
    """Payload for rotating a secret to a new value."""

    new_value = serializers.CharField(
        min_length=8,
        help_text="The new API key or secret value.",
    )


class SecretVaultRevokeSerializer(serializers.Serializer):
    """Payload for revoking a secret."""

    reason = serializers.CharField(
        required=False, default="",
        help_text="Reason for revocation.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RolePermissionMatrix
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RolePermissionMatrixSerializer(serializers.ModelSerializer):
    """Single entry in the role × permission grid."""

    role_display = serializers.SerializerMethodField()
    permission_display = serializers.SerializerMethodField()

    class Meta:
        model = RolePermissionMatrix
        fields = (
            "id", "role", "role_display",
            "permission", "permission_display",
            "is_granted",
            "updated_by",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "role_display", "permission_display",
            "updated_by", "created_at", "updated_at",
        )

    def get_role_display(self, obj):
        role_map = dict(User.ROLES)
        return role_map.get(obj.role, f"Role {obj.role}")

    def get_permission_display(self, obj):
        perm_map = dict(RolePermissionMatrix.PERMISSION_CHOICES)
        return perm_map.get(obj.permission, obj.permission)


class RolePermissionMatrixBulkUpdateSerializer(serializers.Serializer):
    """Bulk update the permission matrix."""

    entries = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of {role, permission, is_granted} dicts.",
    )

    def validate_entries(self, value):
        valid_roles = {r for r, _ in User.ROLES}
        valid_perms = {p for p, _ in RolePermissionMatrix.PERMISSION_CHOICES}

        for item in value:
            if "role" not in item or "permission" not in item:
                raise serializers.ValidationError(
                    "Each entry must include 'role' and 'permission'."
                )
            if item["role"] not in valid_roles:
                raise serializers.ValidationError(
                    f"Unknown role: {item['role']}"
                )
            if item["permission"] not in valid_perms:
                raise serializers.ValidationError(
                    f"Unknown permission: {item['permission']}"
                )
            if "is_granted" in item and not isinstance(item["is_granted"], bool):
                raise serializers.ValidationError(
                    "'is_granted' must be a boolean."
                )
        return value


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  UserSecurityAction
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class UserSecurityActionSerializer(serializers.ModelSerializer):
    """Read serializer for security action history."""

    admin_email = serializers.EmailField(
        source="admin.email", read_only=True, default="",
    )
    target_user_email = serializers.EmailField(
        source="target_user.email", read_only=True,
    )
    target_user_name = serializers.SerializerMethodField()

    class Meta:
        model = UserSecurityAction
        fields = (
            "id", "admin", "admin_email",
            "target_user", "target_user_email", "target_user_name",
            "action", "status", "reason", "metadata",
            "created_at",
        )
        read_only_fields = fields

    def get_target_user_name(self, obj):
        return obj.target_user.get_full_name() or obj.target_user.email


class UserSecurityActionCreateSerializer(serializers.Serializer):
    """Create a security action (password reset, MFA manage, etc.)."""

    target_user_id = serializers.IntegerField()
    action = serializers.ChoiceField(
        choices=UserSecurityAction.ACTION_CHOICES,
    )
    reason = serializers.CharField(required=False, default="")

    def validate_target_user_id(self, value):
        try:
            User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        return value


class AdminUserListSerializer(serializers.ModelSerializer):
    """Lightweight user serializer for admin user management."""

    role_display = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    mfa_enabled = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "email", "first_name", "last_name", "full_name",
            "role", "role_display",
            "is_active", "is_verified", "is_superuser",
            "mfa_enabled",
            "date_joined", "last_login",
        )
        read_only_fields = fields

    def get_role_display(self, obj):
        return dict(User.ROLES).get(obj.role, f"Role {obj.role}")

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email

    def get_mfa_enabled(self, obj):
        # MFA state — currently a placeholder; in production this would
        # check django-otp or similar
        return False
