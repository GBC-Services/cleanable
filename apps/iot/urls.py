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

GPS Tracking & Geofencing
--------------------------
  POST   /iot/gps/update/                     — HTTP fallback for GPS updates
  GET    /iot/gps/location/{booking_id}/      — current Service Pro location
  POST   /iot/geofence/setup/                 — create/update property geofence
  GET    /iot/geofence/{place_id}/            — get geofence config

Predictive Recommendations
---------------------------
  POST   /iot/recommendations/                — AI-powered booking suggestions
"""

from django.urls import path

from . import views
from . import gps_views
from . import privacy_views

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

    # ── GPS Tracking & Geofencing ─────────────────────────────────────
    path(
        "gps/update/",
        gps_views.GPSUpdateView.as_view(),
        name="iot-gps-update",
    ),
    path(
        "gps/location/<int:booking_id>/",
        gps_views.ServiceProLocationView.as_view(),
        name="iot-gps-location",
    ),
    path(
        "geofence/setup/",
        gps_views.GeofenceSetupView.as_view(),
        name="iot-geofence-setup",
    ),
    path(
        "geofence/<int:place_id>/",
        gps_views.GeofenceDetailView.as_view(),
        name="iot-geofence-detail",
    ),

    # ── Predictive Recommendations ────────────────────────────────────
    path(
        "recommendations/",
        gps_views.PredictiveRecommendationsView.as_view(),
        name="iot-recommendations",
    ),

    # ── Location Privacy (Ghost Mode) ─────────────────────────────────
    path(
        "ghost-mode/",
        privacy_views.GhostModeView.as_view(),
        name="iot-ghost-mode",
    ),
    path(
        "ghost-mode/checkin/",
        privacy_views.GhostModeCheckinView.as_view(),
        name="iot-ghost-mode-checkin",
    ),

    # ── Fleet Management (Agency Owner) ───────────────────────────────
    path(
        "fleet/pros/",
        privacy_views.FleetProsView.as_view(),
        name="iot-fleet-pros",
    ),
    path(
        "fleet/strict-tracking/",
        privacy_views.StrictTrackingView.as_view(),
        name="iot-fleet-strict-tracking",
    ),
    path(
        "fleet/alerts/",
        privacy_views.FleetAlertsView.as_view(),
        name="iot-fleet-alerts",
    ),

    # ── GPS History (Platform Admin) ──────────────────────────────────
    path(
        "gps-history/",
        privacy_views.GPSHistoryView.as_view(),
        name="iot-gps-history",
    ),
    path(
        "gps-history/scrub/",
        privacy_views.GPSScrubView.as_view(),
        name="iot-gps-history-scrub",
    ),
]
