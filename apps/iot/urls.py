"""
IoT URL Configuration
======================

All endpoints are mounted under ``/api/v1/iot/`` via the API root urlconf.

Devices
--------
  GET    /iot/devices/                        — list connected devices
  POST   /iot/devices/                        — link new device (OAuth code)
  GET    /iot/devices/{uuid}/                 — device detail
  PATCH  /iot/devices/{uuid}/                 — update device
  DELETE /iot/devices/{uuid}/                 — unlink device
  POST   /iot/devices/{uuid}/toggle-smart-access/ — toggle auto-unlock
  POST   /iot/devices/{uuid}/sync/            — force-sync device
  GET    /iot/devices/{uuid}/locks/           — list locks from provider
  POST   /iot/devices/oauth-url/              — get OAuth authorization URL

Access Tokens
--------------
  GET    /iot/access-tokens/                  — list access tokens
  GET    /iot/access-tokens/{uuid}/           — token detail
  POST   /iot/access-tokens/{uuid}/revoke/    — revoke a token

Voice Assistant Links
----------------------
  GET    /iot/voice-links/                    — list linked platforms
  POST   /iot/voice-links/                    — link a new platform
  DELETE /iot/voice-links/{uuid}/             — unlink a platform
"""

from django.urls import path

from . import views

# ── Device action URLs ────────────────────────────────────────────────

device_list_create = views.ConnectedDeviceViewSet.as_view(
    {"get": "list", "post": "create"}
)
device_detail = views.ConnectedDeviceViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)
device_toggle_smart_access = views.ConnectedDeviceViewSet.as_view(
    {"post": "toggle_smart_access"}
)
device_sync = views.ConnectedDeviceViewSet.as_view({"post": "sync"})
device_locks = views.ConnectedDeviceViewSet.as_view({"get": "locks"})
device_oauth_url = views.ConnectedDeviceViewSet.as_view({"post": "oauth_url"})

# ── Access Token action URLs ──────────────────────────────────────────

access_token_list = views.SmartLockAccessTokenViewSet.as_view({"get": "list"})
access_token_detail = views.SmartLockAccessTokenViewSet.as_view({"get": "retrieve"})
access_token_revoke = views.SmartLockAccessTokenViewSet.as_view({"post": "revoke"})

# ── Voice Link action URLs ────────────────────────────────────────────

voice_link_list_create = views.VoiceAssistantLinkViewSet.as_view(
    {"get": "list", "post": "create"}
)
voice_link_delete = views.VoiceAssistantLinkViewSet.as_view({"delete": "destroy"})


urlpatterns = [
    # ── Devices ───────────────────────────────────────────────────────
    path("devices/", device_list_create, name="iot-devices-list-create"),
    path("devices/oauth-url/", device_oauth_url, name="iot-devices-oauth-url"),
    path("devices/<uuid:pk>/", device_detail, name="iot-devices-detail"),
    path(
        "devices/<uuid:pk>/toggle-smart-access/",
        device_toggle_smart_access,
        name="iot-devices-toggle-smart-access",
    ),
    path("devices/<uuid:pk>/sync/", device_sync, name="iot-devices-sync"),
    path("devices/<uuid:pk>/locks/", device_locks, name="iot-devices-locks"),

    # ── Access Tokens ─────────────────────────────────────────────────
    path("access-tokens/", access_token_list, name="iot-access-tokens-list"),
    path(
        "access-tokens/<uuid:pk>/",
        access_token_detail,
        name="iot-access-tokens-detail",
    ),
    path(
        "access-tokens/<uuid:pk>/revoke/",
        access_token_revoke,
        name="iot-access-tokens-revoke",
    ),

    # ── Voice Links ───────────────────────────────────────────────────
    path("voice-links/", voice_link_list_create, name="iot-voice-links-list-create"),
    path(
        "voice-links/<uuid:pk>/",
        voice_link_delete,
        name="iot-voice-links-delete",
    ),

    # ── Emergency Security Endpoints ──────────────────────────────────
    path(
        "revoke-access/",
        views.EmergencyRevokeAccessView.as_view(),
        name="iot-revoke-access",
    ),
    path(
        "emergency-lockout/",
        views.EmergencyLockoutView.as_view(),
        name="iot-emergency-lockout",
    ),
]
