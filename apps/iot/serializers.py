"""
IoT Serializers
================

DRF serializers for the IoT & Smart Home models.
"""

from rest_framework import serializers

from .models import ConnectedDevice, SmartLockAccessToken, VoiceAssistantLink


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Connected Device
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ConnectedDeviceListSerializer(serializers.ModelSerializer):
    """Read-only list representation — no tokens exposed."""

    place_name = serializers.SerializerMethodField()

    class Meta:
        model = ConnectedDevice
        fields = (
            "id",
            "uuid",
            "provider",
            "device_name",
            "device_model",
            "status",
            "smart_access_enabled",
            "last_synced_at",
            "place",
            "place_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_place_name(self, obj):
        if obj.place:
            return str(obj.place)
        return None


class ConnectedDeviceDetailSerializer(serializers.ModelSerializer):
    """Detailed view with metadata but still no raw tokens."""

    place_name = serializers.SerializerMethodField()
    is_token_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = ConnectedDevice
        fields = (
            "id",
            "uuid",
            "provider",
            "provider_device_id",
            "device_name",
            "device_model",
            "status",
            "smart_access_enabled",
            "last_synced_at",
            "token_expires_at",
            "is_token_expired",
            "metadata",
            "place",
            "place_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_place_name(self, obj):
        if obj.place:
            return str(obj.place)
        return None


class ConnectedDeviceCreateSerializer(serializers.Serializer):
    """
    Input serializer for the OAuth callback that links a new device.

    The frontend sends the OAuth ``code`` and ``redirect_uri`` after the
    user completes the provider's consent flow.
    """

    provider = serializers.ChoiceField(
        choices=["august", "yale", "smartthings"],
    )
    code = serializers.CharField(
        max_length=2048,
        help_text="OAuth authorization code from the provider.",
    )
    redirect_uri = serializers.URLField(
        help_text="The redirect URI used in the OAuth flow.",
    )
    device_name = serializers.CharField(
        max_length=255,
        required=False,
        default="Smart Lock",
    )
    place_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Optional Place ID to associate the device with.",
    )


class ConnectedDeviceUpdateSerializer(serializers.Serializer):
    """Update mutable fields on a connected device."""

    device_name = serializers.CharField(max_length=255, required=False)
    smart_access_enabled = serializers.BooleanField(required=False)
    place_id = serializers.IntegerField(required=False, allow_null=True)


class SmartAccessToggleSerializer(serializers.Serializer):
    """Toggle smart-access auto-unlocking for a device."""

    enabled = serializers.BooleanField()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Smart Lock Access Token
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SmartLockAccessTokenSerializer(serializers.ModelSerializer):
    """Read-only serializer for access tokens."""

    device_name = serializers.CharField(source="device.device_name", read_only=True)
    device_provider = serializers.CharField(source="device.provider", read_only=True)
    service_pro_name = serializers.SerializerMethodField()
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = SmartLockAccessToken
        fields = (
            "id",
            "uuid",
            "device",
            "device_name",
            "device_provider",
            "booking",
            "service_pro",
            "service_pro_name",
            "valid_from",
            "valid_until",
            "status",
            "is_valid",
            "created_at",
        )
        read_only_fields = fields

    def get_service_pro_name(self, obj):
        name = obj.service_pro.get_full_name()
        return name if name.strip() else obj.service_pro.email


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Voice Assistant Link
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class VoiceAssistantLinkSerializer(serializers.ModelSerializer):
    """Read-only serializer for voice-assistant links."""

    platform_display = serializers.CharField(
        source="get_platform_display", read_only=True
    )

    class Meta:
        model = VoiceAssistantLink
        fields = (
            "id",
            "uuid",
            "platform",
            "platform_display",
            "is_active",
            "linked_at",
            "updated_at",
        )
        read_only_fields = fields


class VoiceAssistantLinkCreateSerializer(serializers.Serializer):
    """Input for linking a voice assistant."""

    platform = serializers.ChoiceField(
        choices=[
            VoiceAssistantLink.PLATFORM_ALEXA,
            VoiceAssistantLink.PLATFORM_SIRI,
            VoiceAssistantLink.PLATFORM_GOOGLE,
        ],
    )
    platform_user_id = serializers.CharField(
        max_length=255,
        required=False,
        default="",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  OAuth URL Request
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class OAuthURLRequestSerializer(serializers.Serializer):
    """Request an OAuth URL for a smart-lock provider."""

    provider = serializers.ChoiceField(choices=["august", "yale", "smartthings"])
    redirect_uri = serializers.URLField()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Emergency Security Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class EmergencyRevokeAccessSerializer(serializers.Serializer):
    """
    Input for the /iot/revoke-access/ endpoint.

    Required by Support Architects and Agency Owners to immediately
    revoke all active access tokens for a specific Service Pro at
    a specific property.
    """

    service_pro_id = serializers.IntegerField(
        help_text="The ID of the Service Pro whose access should be revoked.",
    )
    place_id = serializers.IntegerField(
        help_text="The ID of the property (Place) to revoke access for.",
    )
    reason = serializers.CharField(
        max_length=1000,
        help_text=(
            "Mandatory justification for the emergency revocation. "
            "Minimum 10 characters."
        ),
    )

    def validate_reason(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Reason must be at least 10 characters."
            )
        return value.strip()


class EmergencyLockoutRequestSerializer(serializers.Serializer):
    """
    Input for the Resident's Emergency Lockout button.

    place_id is optional — if omitted, ALL of the Resident's
    active devices are locked out.
    """

    place_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text=(
            "Optional property ID.  If provided, only devices at "
            "that property are locked out.  Omit to lock all."
        ),
    )
    reason = serializers.CharField(
        max_length=1000,
        required=False,
        default="Resident-initiated emergency lockout",
        help_text="Optional reason for the lockout.",
    )
