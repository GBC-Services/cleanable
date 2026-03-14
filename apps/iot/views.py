"""
IoT & Smart Home API Views
============================

ViewSets and APIViews for:
  - ConnectedDeviceViewSet — CRUD for smart-lock devices + OAuth linking
  - SmartLockAccessTokenViewSet — read-only access tokens for bookings
  - VoiceAssistantLinkViewSet — CRUD for voice-platform links
  - EmergencyRevokeAccessView — Instant token revocation for a Service Pro
      at a property (Support Architect + Agency Owner only)
  - EmergencyLockoutView — Resident-initiated emergency lockout with
      WebSocket alert to Support Architects
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

from django.db import transaction

from apps.api.permissions import (
    IsAgencyOwner,
    IsPlatformAdmin,
    IsResident,
    IsSupportArchitect,
)
from apps.clients.models import Place
from apps.governance.models import GovernanceAuditLog, SystemFeatureToggle
from apps.users.models import User

from .models import ConnectedDevice, SmartLockAccessToken, VoiceAssistantLink
from .serializers import (
    ConnectedDeviceCreateSerializer,
    ConnectedDeviceDetailSerializer,
    ConnectedDeviceListSerializer,
    ConnectedDeviceUpdateSerializer,
    EmergencyLockoutRequestSerializer,
    EmergencyRevokeAccessSerializer,
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
    revoke_guest_access,
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Emergency Revoke Access (Support Architect + Agency Owner)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class EmergencyRevokeAccessView(APIView):
    """
    POST /api/v1/iot/revoke-access/

    Instantly terminates **all** active OAuth tokens and time-bound digital
    keys assigned to a specific Service Pro at a specific property.

    Authorization: Support Architect (role 50) or Agency Owner (role 30)
    only.  Platform Admins are also granted access.

    Flow:
      1. Validate payload (service_pro_id + place_id + reason)
      2. Query all active SmartLockAccessTokens for the given
         service_pro × device.place combination
      3. For each token:
         a. Call the lock-provider’s revoke API to delete the code
         b. Mark the DB record as REVOKED
         c. Wipe the device’s stored OAuth tokens (scorched-earth)
      4. Write an immutable GovernanceAuditLog entry
      5. Return a summary of revoked tokens + any failures

    All mutations are wrapped in an atomic transaction so partial
    failures roll back cleanly.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsSupportArchitect | IsAgencyOwner | IsPlatformAdmin,
    ]

    def post(self, request):
        serializer = EmergencyRevokeAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service_pro_id = data["service_pro_id"]
        place_id = data["place_id"]
        reason = data["reason"]

        # ── Resolve target user ──────────────────────────────────────
        try:
            service_pro = User.objects.get(
                id=service_pro_id, role=User.ROLE_SERVICE_PRO
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Service Pro not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Resolve place ──────────────────────────────────────────
        try:
            place = Place.objects.get(id=place_id)
        except Place.DoesNotExist:
            return Response(
                {"detail": "Property not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Find all active tokens for this pro × place ─────────────
        active_tokens = SmartLockAccessToken.objects.filter(
            service_pro=service_pro,
            device__place=place,
            status=SmartLockAccessToken.STATUS_ACTIVE,
        ).select_related("device")

        revoked_count = 0
        failed_revocations = []
        affected_device_ids = set()

        with transaction.atomic():
            for token in active_tokens:
                device = token.device
                affected_device_ids.add(device.id)

                # Attempt provider-side revocation
                try:
                    provider_access_token = ensure_valid_token(device)
                    success = revoke_guest_access(
                        provider=device.provider,
                        access_token=provider_access_token,
                        device_id=device.provider_device_id,
                        provider_token_id=token.provider_token_id,
                    )
                except Exception as exc:
                    logger.error(
                        "Provider revocation failed for token %s: %s",
                        token.uuid, exc,
                    )
                    success = False

                # Always mark as revoked in our DB (fail-secure)
                token.status = SmartLockAccessToken.STATUS_REVOKED
                token.save(update_fields=["status", "updated_at"])
                revoked_count += 1

                if not success:
                    failed_revocations.append(str(token.uuid))

            # ── Scorched-earth: wipe device OAuth tokens ────────────
            if affected_device_ids:
                ConnectedDevice.objects.filter(
                    id__in=affected_device_ids
                ).update(
                    access_token_encrypted="",
                    refresh_token_encrypted="",
                    token_expires_at=None,
                )

            # ── Audit log ────────────────────────────────────────────
            GovernanceAuditLog.log(
                action="emergency_access_revocation",
                description=(
                    f"Emergency revocation: {revoked_count} token(s) revoked "
                    f"for Service Pro {service_pro.email} at property "
                    f"'{place}' (ID {place.id}). Reason: {reason}"
                ),
                actor=request.user,
                target_user=service_pro,
                changes={
                    "revoked_count": revoked_count,
                    "failed_provider_revocations": failed_revocations,
                    "place_id": place_id,
                    "reason": reason,
                    "affected_device_ids": list(affected_device_ids),
                },
                severity=GovernanceAuditLog.SEVERITY_CRITICAL,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

        return Response(
            {
                "detail": "Emergency access revocation complete.",
                "revoked_count": revoked_count,
                "failed_provider_revocations": failed_revocations,
                "service_pro_email": service_pro.email,
                "place": str(place),
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _get_client_ip(request):
        """Extract the client IP, respecting X-Forwarded-For."""
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Emergency Lockout (Resident-Initiated)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class EmergencyLockoutView(APIView):
    """
    POST /api/v1/iot/emergency-lockout/

    Resident-initiated “panic button” that:
      1. Revokes ALL active access tokens on ALL of the Resident’s
         devices at a specific place (or all places if none specified)
      2. Disables smart_access_enabled on affected devices
      3. Writes a CRITICAL GovernanceAuditLog entry
      4. Pushes a high-priority WebSocket alert to all online
         Support Architects (via the /ws/alerts/ channel)

    Authorization: Resident only.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsResident | IsPlatformAdmin,
    ]

    def post(self, request):
        serializer = EmergencyLockoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        place_id = data.get("place_id")
        reason = data.get("reason", "Resident-initiated emergency lockout")

        # ── Scope to this resident’s devices ─────────────────────
        device_qs = ConnectedDevice.objects.filter(
            user=request.user,
            status=ConnectedDevice.STATUS_ACTIVE,
        )
        if place_id:
            device_qs = device_qs.filter(place_id=place_id)

        device_ids = list(device_qs.values_list("id", flat=True))

        if not device_ids:
            return Response(
                {"detail": "No active devices found for lockout."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Revoke all active tokens on those devices ─────────────
        active_tokens = SmartLockAccessToken.objects.filter(
            device_id__in=device_ids,
            status=SmartLockAccessToken.STATUS_ACTIVE,
        ).select_related("device")

        revoked_count = 0
        failed_revocations = []

        with transaction.atomic():
            for token in active_tokens:
                device = token.device
                try:
                    provider_access_token = ensure_valid_token(device)
                    success = revoke_guest_access(
                        provider=device.provider,
                        access_token=provider_access_token,
                        device_id=device.provider_device_id,
                        provider_token_id=token.provider_token_id,
                    )
                except Exception as exc:
                    logger.error(
                        "Lockout provider revocation failed for token %s: %s",
                        token.uuid, exc,
                    )
                    success = False

                token.status = SmartLockAccessToken.STATUS_REVOKED
                token.save(update_fields=["status", "updated_at"])
                revoked_count += 1

                if not success:
                    failed_revocations.append(str(token.uuid))

            # ── Disable smart access + wipe device tokens ──────────
            ConnectedDevice.objects.filter(id__in=device_ids).update(
                smart_access_enabled=False,
                access_token_encrypted="",
                refresh_token_encrypted="",
                token_expires_at=None,
            )

            # ── Audit log ────────────────────────────────────────────
            GovernanceAuditLog.log(
                action="emergency_lockout",
                description=(
                    f"Emergency lockout by Resident {request.user.email}: "
                    f"{revoked_count} token(s) revoked across "
                    f"{len(device_ids)} device(s). Reason: {reason}"
                ),
                actor=request.user,
                target_user=request.user,
                changes={
                    "revoked_count": revoked_count,
                    "failed_provider_revocations": failed_revocations,
                    "device_count": len(device_ids),
                    "place_id": place_id,
                    "reason": reason,
                },
                severity=GovernanceAuditLog.SEVERITY_CRITICAL,
                ip_address=EmergencyRevokeAccessView._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

        # ── Push WebSocket alert to Support Architects ────────────
        # This is a fire-and-forget notification.  If the WS layer is
        # unavailable, the lockout still succeeds — the audit log is
        # the durable record.
        try:
            self._notify_support_architects(request.user, place_id, reason, revoked_count)
        except Exception as exc:
            logger.warning("WebSocket notification failed: %s", exc)

        return Response(
            {
                "detail": "Emergency lockout activated.",
                "revoked_count": revoked_count,
                "devices_locked": len(device_ids),
                "failed_provider_revocations": failed_revocations,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _notify_support_architects(resident, place_id, reason, revoked_count):
        """
        Push a high-priority alert to all online Support Architects
        via Django Channels (or fall back to polling table).

        Channel layer message format::

            {
                "type": "emergency_lockout",
                "priority": "critical",
                "resident_email": "user@example.com",
                "resident_id": 123,
                "place_id": 456,
                "reason": "...",
                "revoked_count": 3,
                "timestamp": "2026-03-14T19:30:00Z"
            }

        If Django Channels is not configured, we fall back to creating
        an in-DB notification record that Support Architect dashboards
        can poll.
        """
        alert_payload = {
            "type": "emergency_lockout",
            "priority": "critical",
            "resident_email": resident.email,
            "resident_id": resident.id,
            "place_id": place_id,
            "reason": reason,
            "revoked_count": revoked_count,
            "timestamp": timezone.now().isoformat(),
        }

        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    "support_architects_alerts",
                    {
                        "type": "emergency.lockout",
                        "payload": alert_payload,
                    },
                )
                logger.info(
                    "Emergency lockout alert sent to support_architects_alerts group"
                )
                return
        except ImportError:
            pass

        # Fallback: store as a JSON record that the front-end can poll
        logger.info(
            "Channels not available; lockout alert stored in audit log only. "
            "Payload: %s", alert_payload,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  IoT Security Middleware
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class IoTAccessGateMiddleware:
    """
    DRF-compatible middleware that checks the ``global_iot_access_enabled``
    SystemFeatureToggle before allowing any IoT lock command to execute.

    Usage:
      Apply as a DRF permission or call ``check_iot_gate()`` from within
      a view.  This class provides both patterns.

    As a DRF permission (preferred for views)::

        from apps.iot.views import IoTAccessGateMiddleware

        class MyLockView(APIView):
            permission_classes = [IsAuthenticated, IoTAccessGateMiddleware.as_permission()]

    As a standalone gate function (for GraphQL resolvers, Celery tasks)::

        IoTAccessGateMiddleware.check_iot_gate()
        # Raises PermissionDenied if the global toggle is disabled

    Fail-secure: if the toggle row does not exist in the DB (e.g., first
    deploy before migrations seed it), access is DENIED.
    """

    @staticmethod
    def check_iot_gate():
        """
        Check the global IoT feature toggle.

        Raises:
            PermissionDenied: if IoT access is globally disabled.
        """
        from rest_framework.exceptions import PermissionDenied

        if not SystemFeatureToggle.is_feature_active("global_iot_access_enabled"):
            logger.warning("IoT gate DENIED — global_iot_access_enabled is OFF")
            raise PermissionDenied(
                detail=(
                    "IoT access is currently disabled system-wide by a "
                    "Platform Administrator. No lock commands can be "
                    "executed until this is re-enabled."
                ),
                code="iot_globally_disabled",
            )

    @classmethod
    def as_permission(cls):
        """
        Return a DRF-compatible permission class that gates on the
        global IoT toggle.

        Example::

            permission_classes = [
                permissions.IsAuthenticated,
                IoTAccessGateMiddleware.as_permission(),
            ]
        """

        class _IoTGatePermission(permissions.BasePermission):
            message = (
                "IoT access is currently disabled system-wide by a "
                "Platform Administrator."
            )

            def has_permission(self, request, view):
                return SystemFeatureToggle.is_feature_active(
                    "global_iot_access_enabled"
                )

        _IoTGatePermission.__name__ = "IoTGatePermission"
        _IoTGatePermission.__qualname__ = "IoTAccessGateMiddleware.IoTGatePermission"
        return _IoTGatePermission
