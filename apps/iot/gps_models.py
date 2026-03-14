"""
GPS & Geofencing Models
========================

Data models for real-time Service Pro location tracking and geofencing:

  ServiceProLocation  — Latest GPS coordinates for a Service Pro on an active booking
  GeofenceEvent       — Audit log of geofence enter/exit events + auto-unlock triggers
  PropertyGeofence    — Geocoordinates + radius for a Resident's property

Design decisions:
  • ``ServiceProLocation`` stores only the *latest* position — no full track history.
    This keeps the table small and fast.  Historical breadcrumbs are transient
    (held in Redis channel layer, flushed after the booking window closes).
  • ``GeofenceEvent`` is append-only for immutable audit trails.
  • ``PropertyGeofence`` stores the lat/lng of the property used for distance
    calculations.  Populated when a Resident first enables smart lock access
    (geocoded from their Place address via Mapbox).
"""

import uuid
from math import asin, cos, radians, sin, sqrt

from django.conf import settings
from django.db import models
from django.utils import timezone


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Haversine Distance (used by geofencing logic)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EARTH_RADIUS_METERS = 6_371_000


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance in meters between two GPS points.

    Args:
        lat1, lon1: Latitude/longitude of point A (decimal degrees).
        lat2, lon2: Latitude/longitude of point B (decimal degrees).

    Returns:
        Distance in meters.
    """
    rlat1, rlon1, rlat2, rlon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(a))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Property Geofence
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PropertyGeofence(models.Model):
    """
    Geocoordinates for a Resident's property.

    Used as the reference point for geofence calculations when
    a Service Pro approaches the property during an active booking.
    """

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    place = models.OneToOneField(
        "clients.Place",
        on_delete=models.CASCADE,
        related_name="geofence",
        help_text="The property this geofence belongs to.",
    )

    latitude = models.FloatField(help_text="Property latitude (decimal degrees).")
    longitude = models.FloatField(help_text="Property longitude (decimal degrees).")
    radius_meters = models.FloatField(
        default=50.0,
        help_text="Geofence radius in meters. Default 50m.",
    )

    # Address string used when geocoding (for debugging/audit)
    geocoded_address = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="The address string that was geocoded to obtain lat/lng.",
    )

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["latitude", "longitude"],
                name="idx_geofence_coords",
            ),
        ]

    def __str__(self):
        return f"Geofence for Place #{self.place_id} ({self.latitude}, {self.longitude})"

    def is_within_radius(self, lat: float, lng: float) -> bool:
        """Check if a GPS point falls within this geofence."""
        distance = haversine_distance(self.latitude, self.longitude, lat, lng)
        return distance <= self.radius_meters

    def distance_to(self, lat: float, lng: float) -> float:
        """Return distance in meters from the geofence center."""
        return haversine_distance(self.latitude, self.longitude, lat, lng)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Service Pro Location
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ServiceProLocation(models.Model):
    """
    Latest known GPS position for a Service Pro during an active booking.

    Updated in real-time via WebSocket (Django Channels consumer).
    Each booking has at most one active location record.
    """

    STATUS_EN_ROUTE = "en_route"
    STATUS_ARRIVED = "arrived"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_EN_ROUTE, "En Route"),
        (STATUS_ARRIVED, "Arrived"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
    ]

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    service_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gps_locations",
    )
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="service_pro_location",
        help_text="The booking this GPS track is associated with.",
    )

    # ── Live coordinates ─────────────────────────────────────────────
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy_meters = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS accuracy reported by the device (CEP50).",
    )
    heading = models.FloatField(
        null=True,
        blank=True,
        help_text="Compass heading in degrees (0-360).",
    )
    speed_mps = models.FloatField(
        null=True,
        blank=True,
        help_text="Speed in meters per second.",
    )

    # ── ETA ───────────────────────────────────────────────────────────
    eta_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Estimated minutes to arrival (calculated client-side or via routing API).",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_EN_ROUTE,
        db_index=True,
    )

    # ── Geofence state ───────────────────────────────────────────────
    is_within_geofence = models.BooleanField(
        default=False,
        help_text="True when the Service Pro is inside the property geofence.",
    )
    distance_to_property_meters = models.FloatField(
        null=True,
        blank=True,
        help_text="Current distance to the property geofence center.",
    )

    last_updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_updated_at"]
        indexes = [
            models.Index(
                fields=["service_pro", "status"],
                name="idx_spro_loc_status",
            ),
            models.Index(
                fields=["booking"],
                name="idx_spro_loc_booking",
            ),
        ]

    def __str__(self):
        return (
            f"GPS: {self.service_pro.email} → Booking #{self.booking_id} "
            f"({self.latitude:.6f}, {self.longitude:.6f}) [{self.status}]"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Geofence Event (Audit Log)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GeofenceEvent(models.Model):
    """
    Immutable record of geofence boundary crossings and the resulting
    actions (e.g., automatic smart lock unlock).

    These events feed into the GovernanceAuditLog for compliance and
    are also displayed on the Resident's En Route tracking view.
    """

    EVENT_ENTER = "enter"
    EVENT_EXIT = "exit"
    EVENT_AUTO_UNLOCK = "auto_unlock"
    EVENT_AUTO_UNLOCK_FAILED = "auto_unlock_failed"
    EVENT_CHOICES = [
        (EVENT_ENTER, "Entered Geofence"),
        (EVENT_EXIT, "Exited Geofence"),
        (EVENT_AUTO_UNLOCK, "Auto-Unlock Triggered"),
        (EVENT_AUTO_UNLOCK_FAILED, "Auto-Unlock Failed"),
    ]

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="geofence_events",
    )
    service_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="geofence_events",
    )
    property_geofence = models.ForeignKey(
        PropertyGeofence,
        on_delete=models.CASCADE,
        related_name="events",
    )

    event_type = models.CharField(
        max_length=30,
        choices=EVENT_CHOICES,
        db_index=True,
    )

    # Coordinates at the time of the event
    latitude = models.FloatField()
    longitude = models.FloatField()
    distance_meters = models.FloatField(
        help_text="Distance to property center when the event fired.",
    )

    # If auto-unlock was triggered, link to the device
    device = models.ForeignKey(
        "iot.ConnectedDevice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="geofence_events",
    )

    # Additional context
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["booking", "event_type"],
                name="idx_geofence_evt_booking",
            ),
        ]

    def __str__(self):
        return (
            f"GeofenceEvent: {self.get_event_type_display()} — "
            f"Booking #{self.booking_id} @ {self.distance_meters:.1f}m"
        )
