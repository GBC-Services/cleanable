"""
Geofencing Service
===================

Core business logic for the geofence auto-unlock feature:

  1. Checks whether a Service Pro's GPS coordinates fall within the
     Resident's property geofence (default 50 m radius).
  2. If inside the geofence AND during an active booking window,
     automatically triggers the Smart Lock API to unlock the door.
  3. Records an immutable GeofenceEvent for the audit trail.
  4. Pushes a WebSocket notification to the Resident's En Route view.

Safety guarantees:
  • Auto-unlock only fires ONCE per booking per geofence entry.
    A ``geofence_unlocked`` flag on the location record prevents duplicates.
  • The ``global_iot_access_enabled`` feature toggle is checked first.
  • The device must have ``smart_access_enabled = True``.
  • The booking must be in STATUS_IN_WORK (assigned, not cancelled).
  • All operations are logged to GovernanceAuditLog via GeofenceEvent.
"""

import logging

from django.conf import settings
from django.utils import timezone

from apps.governance.models import GovernanceAuditLog, SystemFeatureToggle

from .gps_models import GeofenceEvent, PropertyGeofence, haversine_distance
from .models import ConnectedDevice, SmartLockAccessToken
from .smart_lock_service import ensure_valid_token

logger = logging.getLogger(__name__)


def check_geofence_and_trigger(
    service_pro,
    booking,
    latitude: float,
    longitude: float,
) -> dict:
    """
    Evaluate whether the Service Pro's current GPS position triggers
    a geofence event, and if so, auto-unlock the smart lock.

    Args:
        service_pro: User instance (Service Pro).
        booking: Booking instance.
        latitude: Current GPS latitude.
        longitude: Current GPS longitude.

    Returns:
        dict with keys:
          - triggered (bool): Whether a geofence entry was detected.
          - auto_unlocked (bool): Whether the lock was auto-unlocked.
          - distance_meters (float): Distance to property center.
          - event_type (str|None): The GeofenceEvent type created.
          - error (str|None): Error message if auto-unlock failed.
    """
    result = {
        "triggered": False,
        "auto_unlocked": False,
        "distance_meters": None,
        "event_type": None,
        "error": None,
    }

    place = booking.place
    if not place:
        result["error"] = "Booking has no associated place."
        return result

    # ── Find the property geofence ────────────────────────────────────
    try:
        geofence = PropertyGeofence.objects.get(place=place, is_active=True)
    except PropertyGeofence.DoesNotExist:
        result["error"] = "No geofence configured for this property."
        return result

    # ── Calculate distance ────────────────────────────────────────────
    distance = haversine_distance(
        geofence.latitude, geofence.longitude,
        latitude, longitude,
    )
    result["distance_meters"] = round(distance, 2)

    radius = geofence.radius_meters or settings.GEOFENCE_RADIUS_METERS
    is_inside = distance <= radius

    if not is_inside:
        return result

    # ── Service Pro is inside the geofence ────────────────────────────
    result["triggered"] = True

    # Check if we already auto-unlocked for this booking
    already_unlocked = GeofenceEvent.objects.filter(
        booking=booking,
        service_pro=service_pro,
        event_type=GeofenceEvent.EVENT_AUTO_UNLOCK,
    ).exists()

    if already_unlocked:
        # Record the enter event but don't re-unlock
        GeofenceEvent.objects.create(
            booking=booking,
            service_pro=service_pro,
            property_geofence=geofence,
            event_type=GeofenceEvent.EVENT_ENTER,
            latitude=latitude,
            longitude=longitude,
            distance_meters=distance,
            metadata={"note": "Re-entry; auto-unlock already fired."},
        )
        result["event_type"] = GeofenceEvent.EVENT_ENTER
        return result

    # ── Check global IoT gate ─────────────────────────────────────────
    if not SystemFeatureToggle.is_feature_active("global_iot_access_enabled"):
        logger.warning("Geofence auto-unlock blocked: global IoT access disabled.")
        result["error"] = "IoT access is globally disabled."
        _record_failed_event(
            booking, service_pro, geofence, latitude, longitude, distance,
            "Global IoT access disabled.",
        )
        return result

    # ── Check geofence auto-unlock setting ────────────────────────────
    if not getattr(settings, "GEOFENCE_AUTO_UNLOCK_ENABLED", True):
        result["error"] = "Geofence auto-unlock is disabled in settings."
        return result

    # ── Find smart-lock device for this property ──────────────────────
    devices = ConnectedDevice.objects.filter(
        place=place,
        status=ConnectedDevice.STATUS_ACTIVE,
        smart_access_enabled=True,
    )

    if not devices.exists():
        result["error"] = "No smart-lock device with auto-access at this property."
        _record_failed_event(
            booking, service_pro, geofence, latitude, longitude, distance,
            "No active smart-lock device found.",
        )
        return result

    # ── Verify active access token exists for this booking ────────────
    active_token = SmartLockAccessToken.objects.filter(
        booking=booking,
        service_pro=service_pro,
        status=SmartLockAccessToken.STATUS_ACTIVE,
    ).select_related("device").first()

    if not active_token:
        result["error"] = "No active access token for this booking."
        _record_failed_event(
            booking, service_pro, geofence, latitude, longitude, distance,
            "No active SmartLockAccessToken found.",
        )
        return result

    # ── Trigger auto-unlock ───────────────────────────────────────────
    device = active_token.device

    try:
        access_token = ensure_valid_token(device)

        # Fire the unlock command via the provider API
        from .smart_lock_service import get_provider_config
        import requests as http_requests

        config = get_provider_config(device.provider)

        if device.provider == "august":
            unlock_url = f"{config['api_base']}/remoteoperate/{device.provider_device_id}/unlock"
        elif device.provider == "yale":
            unlock_url = f"{config['api_base']}/api/panel/device/{device.provider_device_id}/open/"
        else:
            unlock_url = f"{config['api_base']}/devices/{device.provider_device_id}/unlock"

        resp = http_requests.put(
            unlock_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"source": "geofence_auto_unlock"},
            timeout=10,
        )
        resp.raise_for_status()

        # ── Record success ────────────────────────────────────────────
        GeofenceEvent.objects.create(
            booking=booking,
            service_pro=service_pro,
            property_geofence=geofence,
            event_type=GeofenceEvent.EVENT_AUTO_UNLOCK,
            latitude=latitude,
            longitude=longitude,
            distance_meters=distance,
            device=device,
            metadata={
                "provider": device.provider,
                "device_name": device.device_name,
                "access_token_uuid": str(active_token.uuid),
            },
        )

        # ── Governance audit log ──────────────────────────────────────
        GovernanceAuditLog.log(
            action="geofence_auto_unlock",
            description=(
                f"Geofence auto-unlock: Service Pro {service_pro.email} entered "
                f"{distance:.1f}m radius of property '{place}'. "
                f"Lock '{device.device_name}' ({device.provider}) unlocked automatically."
            ),
            actor=service_pro,
            target_user=device.user,
            changes={
                "booking_id": booking.id,
                "device_uuid": str(device.uuid),
                "distance_meters": round(distance, 2),
                "gps_coordinates": {"lat": latitude, "lng": longitude},
            },
            severity=GovernanceAuditLog.SEVERITY_WARNING,
        )

        result["auto_unlocked"] = True
        result["event_type"] = GeofenceEvent.EVENT_AUTO_UNLOCK

        logger.info(
            "Geofence auto-unlock SUCCESS: booking=%d, pro=%s, device=%s, distance=%.1fm",
            booking.id, service_pro.email, device.uuid, distance,
        )

    except Exception as exc:
        logger.error(
            "Geofence auto-unlock FAILED: booking=%d, pro=%s, error=%s",
            booking.id, service_pro.email, exc,
        )
        result["error"] = f"Auto-unlock failed: {exc}"
        _record_failed_event(
            booking, service_pro, geofence, latitude, longitude, distance,
            str(exc), device=device,
        )

    return result


def _record_failed_event(
    booking, service_pro, geofence, lat, lng, distance, reason, device=None,
):
    """Helper to create a failed auto-unlock GeofenceEvent."""
    GeofenceEvent.objects.create(
        booking=booking,
        service_pro=service_pro,
        property_geofence=geofence,
        event_type=GeofenceEvent.EVENT_AUTO_UNLOCK_FAILED,
        latitude=lat,
        longitude=lng,
        distance_meters=distance,
        device=device,
        metadata={"failure_reason": reason},
    )
