"""
IoT & Smart Home API Views
============================

ViewSets and APIViews for:
  - ConnectedDeviceViewSet — CRUD for smart-lock devices + OAuth linking
  - SmartLockAccessTokenViewSet — read-only access tokens for bookings
  - VoiceAssistantLinkViewSet — CRUD for voice-platform links
  - AlexaWebhookView — Alexa Skill endpoint (unauthenticated, validated)
  - SiriWebhookView — Siri Shortcuts endpoint (JWT auth)
  - SmartLockOAuthCallbackView — OAuth callback for lock providers

All CRUD endpoints are Resident-only (with Platform Admin override).
Webhook endpoints are unauthenticated but validated via their
respective platform's security model.
"""

import logging
import secrets

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import IsPlatformAdmin, IsResident
from apps.clients.models import Place

from .models import ConnectedDevice, SmartLockAccessToken, VoiceAssistantLink
from .serializers import (
    ConnectedDeviceCreateSerializer,
    ConnectedDeviceDetailSerializer,
    ConnectedDeviceListSerializer,
    ConnectedDeviceUpdateSerializer,
    OAuthURLRequestSerializer,
    SmartAccessToggleSerializer,
    SmartLockAccessTokenSerializer,
    VoiceAssistantLinkCreateSerializer,
    VoiceAssistantLinkSerializer,
)
from .smart_lock_service import (
    build_oauth_authorize_url,
    ensure_valid_token,
    exchange_oauth_code,
    list_locks,
    store_encrypted_tokens,
)
from .voice_handlers import handle_alexa_webhook, handle_siri_webhook

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ConnectedDeviceViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ConnectedDeviceViewSet(viewsets.ViewSet):
    """
    CRUD for Resident's connected IoT devices.

    GET    /iot/devices/                — list devices
    POST   /iot/devices/               — link new device via OAuth code
    GET    /iot/devices/{uuid}/        — detail
    PATCH  /iot/devices/{uuid}/        — update name / smart_access / place
    DELETE /iot/devices/{uuid}/        — unlink device
    POST   /iot/devices/{uuid}/toggle-smart-access/ — toggle auto-unlock
    POST   /iot/devices/{uuid}/sync/   — force-sync device status
    GET    /iot/devices/{uuid}/locks/  — list locks from provider API
    POST   /iot/devices/oauth-url/     — get OAuth authorization URL
    """

    permission_classes = [permissions.IsAuthenticated, IsResident | IsPlatformAdmin]

    # ── list ─────────────────────────────────────────────────────────

    def list(self, request):
        qs = ConnectedDevice.objects.filter(user=request.user).order_by("-created_at")
        return Response(ConnectedDeviceListSerializer(qs, many=True).data)

    # ── retrieve ─────────────────────────────────────────────────────

    def retrieve(self, request, pk=None):
        device = self._get_device(request.user, pk)
        if not device:
            return Response(
                {"detail": "Device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ConnectedDeviceDetailSerializer(device).data)

    # ── create (OAuth code exchange) ─────────────────────────────────

    def create(self, request):
        """
        Link a new smart-lock device.

        The frontend completes the provider's OAuth flow and sends us the
        authorization code + redirect_uri.  We exchange it for tokens,
        enumerate the user's locks, and create a ConnectedDevice record.
        """
        serializer = ConnectedDeviceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        provider = data["provider"]
        code = data["code"]
        redirect_uri = data["redirect_uri"]

        # Exchange the OAuth code
        try:
            tokens = exchange_oauth_code(provider, code, redirect_uri)
        except Exception as exc:
            logger.error("OAuth code exchange failed for %s: %s", provider, exc)
            return Response(
                {"detail": f"Failed to authenticate with {provider}: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enumerate locks
        try:
            locks = list_locks(provider, tokens["access_token"])
        except Exception as exc:
            logger.warning("Could not enumerate locks for %s: %s", provider, exc)
            locks = []

        if not locks:
            # Still create the device with manual info
            locks = [
                {
                    "device_id": tokens.get("user_id", "manual"),
                    "name": data.get("device_name", "Smart Lock"),
                    "model": "",
                }
            ]

        # Validate place_id if provided
        place = None
        place_id = data.get("place_id")
        if place_id:
            try:
                place = Place.objects.get(
                    id=place_id, client=request.user, is_active=True
                )
            except Place.DoesNotExist:
                return Response(
                    {"detail": "Place not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Create device records (one per lock found)
        created_devices = []
        for lock_info in locks:
            device, created = ConnectedDevice.objects.get_or_create(
                user=request.user,
                provider=provider,
                provider_device_id=lock_info["device_id"],
                defaults={
                    "device_name": lock_info.get("name", data.get("device_name", "Smart Lock")),
                    "device_model": lock_info.get("model", ""),
                    "place": place,
                    "status": ConnectedDevice.STATUS_ACTIVE,
                },
            )

            store_encrypted_tokens(
                device,
                tokens["access_token"],
                tokens["refresh_token"],
                tokens.get("expires_in", 3600),
            )

            if not created:
                device.status = ConnectedDevice.STATUS_ACTIVE
                device.device_name = lock_info.get("name", device.device_name)
                if place:
                    device.place = place
                device.save(update_fields=["status", "device_name", "place", "updated_at"])

            device.last_synced_at = timezone.now()
            device.save(update_fields=["last_synced_at"])
            created_devices.append(device)

        return Response(
            ConnectedDeviceDetailSerializer(created_devices, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    # ── partial_update ───────────────────────────────────────────────

    def partial_update(self, request, pk=None):
        device = self._get_device(request.user, pk)
        if not device:
            return Response(
                {"detail": "Device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ConnectedDeviceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        update_fields = ["updated_at"]

        if "device_name" in data:
            device.device_name = data["device_name"]
            update_fields.append("device_name")

        if "smart_access_enabled" in data:
            device.smart_access_enabled = data["smart_access_enabled"]
            update_fields.append("smart_access_enabled")

        if "place_id" in data:
            if data["place_id"]:
                try:
                    place = Place.objects.get(
                        id=data["place_id"], client=request.user, is_active=True
                    )
                    device.place = place
                except Place.DoesNotExist:
                    return Response(
                        {"detail": "Place not found."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                device.place = None
            update_fields.append("place")

        device.save(update_fields=update_fields)
        return Response(ConnectedDeviceDetailSerializer(device).data)

    # ── destroy ──────────────────────────────────────────────────────

    def destroy(self, request, pk=None):
        device = self._get_device(request.user, pk)
        if not device:
            return Response(
                {"detail": "Device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        device.status = ConnectedDevice.STATUS_DISCONNECTED
        device.access_token_encrypted = ""
        device.refresh_token_encrypted = ""
        device.smart_access_enabled = False
        device.save(
            update_fields=[
                "status",
                "access_token_encrypted",
                "refresh_token_encrypted",
                "smart_access_enabled",
                "updated_at",
            ]
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Custom actions ───────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="toggle-smart-access")
    def toggle_smart_access(self, request, pk=None):
        """POST /iot/devices/{uuid}/toggle-smart-access/"""
        device = self._get_device(request.user, pk)
        if not device:
            return Response(
                {"detail": "Device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SmartAccessToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device.smart_access_enabled = serializer.validated_data["enabled"]
        device.save(update_fields=["smart_access_enabled", "updated_at"])

        return Response(ConnectedDeviceDetailSerializer(device).data)

    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request, pk=None):
        """POST /iot/devices/{uuid}/sync/ — Force-sync device status."""
        device = self._get_device(request.user, pk)
        if not device:
            return Response(
                {"detail": "Device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            access_token = ensure_valid_token(device)
            locks = list_locks(device.provider, access_token)
        except Exception as exc:
            logger.error("Device sync failed for %s: %s", device.uuid, exc)
            return Response(
                {"detail": f"Sync failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Update metadata with fresh lock info
        for lock_info in locks:
            if lock_info["device_id"] == device.provider_device_id:
                device.metadata = {
                    **device.metadata,
                    "last_status": lock_info.get("status"),
                    "synced_name": lock_info.get("name"),
                }
                break

        device.last_synced_at = timezone.now()
        device.save(update_fields=["metadata", "last_synced_at", "updated_at"])

        return Response(
            {
                "detail": "Sync complete.",
                "device": ConnectedDeviceDetailSerializer(device).data,
                "locks": locks,
            }
        )

    @action(detail=True, methods=["get"], url_path="locks")
    def locks(self, request, pk=None):
        """GET /iot/devices/{uuid}/locks/ — List locks from provider."""
        device = self._get_device(request.user, pk)
        if not device:
            return Response(
                {"detail": "Device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            access_token = ensure_valid_token(device)
            provider_locks = list_locks(device.provider, access_token)
        except Exception as exc:
            return Response(
                {"detail": f"Failed to list locks: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"locks": provider_locks})

    @action(detail=False, methods=["post"], url_path="oauth-url")
    def oauth_url(self, request):
        """POST /iot/devices/oauth-url/ — Get OAuth authorization URL."""
        serializer = OAuthURLRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = serializer.validated_data["provider"]
        redirect_uri = serializer.validated_data["redirect_uri"]
        state = secrets.token_urlsafe(32)

        url = build_oauth_authorize_url(provider, redirect_uri, state)

        return Response(
            {
                "authorize_url": url,
                "state": state,
                "provider": provider,
            }
        )

    # ── helpers ──────────────────────────────────────────────────────

    def _get_device(self, user, uuid_str):
        try:
            return ConnectedDevice.objects.get(
                uuid=uuid_str,
                user=user,
            )
        except (ConnectedDevice.DoesNotExist, ValueError):
            return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SmartLockAccessTokenViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SmartLockAccessTokenViewSet(viewsets.ViewSet):
    """
    Read-only access tokens for a Resident's bookings.

    GET /iot/access-tokens/                — list all tokens
    GET /iot/access-tokens/?booking=<id>   — filter by booking
    GET /iot/access-tokens/{uuid}/         — detail
    POST /iot/access-tokens/{uuid}/revoke/ — revoke a token
    """

    permission_classes = [permissions.IsAuthenticated, IsResident | IsPlatformAdmin]

    def list(self, request):
        qs = SmartLockAccessToken.objects.filter(
            device__user=request.user,
        ).select_related("device", "service_pro").order_by("-created_at")

        booking_id = request.query_params.get("booking")
        if booking_id:
            qs = qs.filter(booking_id=booking_id)

        return Response(SmartLockAccessTokenSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            token = SmartLockAccessToken.objects.select_related(
                "device", "service_pro"
            ).get(uuid=pk, device__user=request.user)
        except (SmartLockAccessToken.DoesNotExist, ValueError):
            return Response(
                {"detail": "Access token not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SmartLockAccessTokenSerializer(token).data)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        """POST /iot/access-tokens/{uuid}/revoke/"""
        from .smart_lock_service import revoke_booking_access_code

        try:
            token = SmartLockAccessToken.objects.select_related("device").get(
                uuid=pk, device__user=request.user
            )
        except (SmartLockAccessToken.DoesNotExist, ValueError):
            return Response(
                {"detail": "Access token not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if token.status != SmartLockAccessToken.STATUS_ACTIVE:
            return Response(
                {"detail": f"Token is already {token.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success = revoke_booking_access_code(token)
        if not success:
            return Response(
                {"detail": "Failed to revoke the access code on the lock. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(SmartLockAccessTokenSerializer(token).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VoiceAssistantLinkViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class VoiceAssistantLinkViewSet(viewsets.ViewSet):
    """
    CRUD for voice-assistant platform links.

    GET    /iot/voice-links/         — list linked platforms
    POST   /iot/voice-links/         — link a new platform
    DELETE /iot/voice-links/{uuid}/  — unlink a platform
    """

    permission_classes = [permissions.IsAuthenticated, IsResident | IsPlatformAdmin]

    def list(self, request):
        qs = VoiceAssistantLink.objects.filter(
            user=request.user, is_active=True
        ).order_by("-linked_at")
        return Response(VoiceAssistantLinkSerializer(qs, many=True).data)

    def create(self, request):
        serializer = VoiceAssistantLinkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        link, created = VoiceAssistantLink.objects.update_or_create(
            user=request.user,
            platform=data["platform"],
            defaults={
                "platform_user_id": data.get("platform_user_id", ""),
                "is_active": True,
            },
        )

        return Response(
            VoiceAssistantLinkSerializer(link).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def destroy(self, request, pk=None):
        try:
            link = VoiceAssistantLink.objects.get(
                uuid=pk, user=request.user
            )
        except (VoiceAssistantLink.DoesNotExist, ValueError):
            return Response(
                {"detail": "Voice link not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        link.is_active = False
        link.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Webhook Views
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AlexaWebhookView(APIView):
    """
    POST /webhooks/alexa/

    Alexa Skills Kit webhook endpoint.  No DRF authentication —
    validated via the Alexa-specific request signature (in production,
    verify ``SignatureCertChainUrl`` and ``Signature`` headers).
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            payload = request.data
            if not isinstance(payload, dict):
                return Response(
                    {"detail": "Invalid payload."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # TODO: In production, verify Alexa request signature
            # https://developer.amazon.com/docs/alexa/custom-skills/host-a-custom-skill-as-a-web-service.html

            result = handle_alexa_webhook(payload)
            return Response(result, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("Alexa webhook error: %s", exc)
            return Response(
                {
                    "version": "1.0",
                    "response": {
                        "outputSpeech": {
                            "type": "PlainText",
                            "text": "Sorry, something went wrong. Please try again.",
                        },
                        "shouldEndSession": True,
                    },
                },
                status=status.HTTP_200_OK,  # Alexa expects 200 even on errors
            )


class SiriWebhookView(APIView):
    """
    POST /webhooks/siri/

    Siri Shortcuts webhook endpoint.  Authenticated via Bearer JWT
    (the user's Cleanable access token stored in the Shortcut).
    """

    # We handle auth manually inside the handler
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            payload = request.data
            if not isinstance(payload, dict):
                return Response(
                    {"detail": "Invalid payload."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            result = handle_siri_webhook(payload, auth_header)

            http_status = (
                status.HTTP_200_OK if result.get("success") else status.HTTP_400_BAD_REQUEST
            )
            return Response(result, status=http_status)

        except Exception as exc:
            logger.exception("Siri webhook error: %s", exc)
            return Response(
                {
                    "success": False,
                    "message": "Something went wrong. Please try again.",
                    "data": None,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
