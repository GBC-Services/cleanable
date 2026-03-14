"""
Django Channels Consumers — Real-Time GPS Tracking
===================================================

WebSocket consumers for:

  GPSTrackingConsumer
    Path: /ws/gps-tracking/{booking_uuid}/
    Protocol:
      • Service Pro connects and sends GPS updates (lat, lng, accuracy, heading, speed, eta)
      • Consumer validates the Service Pro is assigned to the booking
      • Each GPS update is broadcast to all channel group subscribers
        (the Resident's En Route map view)
      • Consumer runs geofence check on every update; if the Service Pro
        enters the 50m radius, fires the auto-unlock trigger
      • Persists latest position to ServiceProLocation model

  AlertConsumer
    Path: /ws/alerts/
    Protocol:
      • Support Architects connect to receive emergency lockout alerts
      • Read-only: clients don't send messages, only receive broadcasts

Authentication:
  Both consumers use Django Channels' AuthMiddlewareStack (session auth)
  or accept a JWT token in the first message for token-based auth.
"""

import json
import logging
from datetime import datetime

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GPS Tracking Consumer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GPSTrackingConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket endpoint for real-time GPS coordinate streaming.

    Connection URL: /ws/gps-tracking/{booking_uuid}/

    Inbound messages (from Service Pro's mobile app):
    {
        "type": "gps_update",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 8.5,
        "heading": 180.0,
        "speed": 12.3,
        "eta_minutes": 7,
        "timestamp": "2026-03-14T19:30:00Z"
    }

    Outbound messages (to Resident's En Route map):
    {
        "type": "location_update",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy": 8.5,
        "heading": 180.0,
        "speed": 12.3,
        "eta_minutes": 7,
        "status": "en_route",
        "distance_to_property": 1250.5,
        "is_within_geofence": false,
        "geofence_event": null,
        "timestamp": "2026-03-14T19:30:00Z"
    }

    Geofence trigger event (broadcast when auto-unlock fires):
    {
        "type": "geofence_event",
        "event": "auto_unlock",
        "distance_meters": 42.3,
        "device_name": "Front Door Lock",
        "timestamp": "2026-03-14T19:30:00Z"
    }

    Authentication flow:
      1. Session auth via AuthMiddlewareStack (for browser clients), OR
      2. First message includes {"type": "authenticate", "token": "<JWT>"}
         for mobile clients.
    """

    booking_uuid = None
    booking = None
    service_pro = None
    group_name = None
    authenticated = False

    async def connect(self):
        """Accept the WebSocket and join the booking's GPS tracking group."""
        self.booking_uuid = self.scope["url_route"]["kwargs"]["booking_uuid"]
        self.group_name = f"gps_tracking_{self.booking_uuid}"

        # Check if user is already authenticated via session
        user = self.scope.get("user")
        if user and user.is_authenticated:
            is_valid = await self._validate_participant(user)
            if is_valid:
                self.authenticated = True

        # Always accept — we'll validate on first message if not session-authed
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        if self.authenticated:
            await self.send_json({
                "type": "connected",
                "booking_uuid": self.booking_uuid,
                "message": "Connected to GPS tracking.",
            })

    async def disconnect(self, close_code):
        """Leave the tracking group on disconnect."""
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

        # If this was the Service Pro, update status
        if self.service_pro and self.booking:
            await self._update_location_status("completed")

    async def receive_json(self, content, **kwargs):
        """Handle inbound messages from the Service Pro's device."""
        msg_type = content.get("type", "")

        # ── JWT authentication (for mobile clients) ──────────────────
        if msg_type == "authenticate":
            token = content.get("token", "")
            user = await self._authenticate_jwt(token)
            if user:
                is_valid = await self._validate_participant(user)
                if is_valid:
                    self.authenticated = True
                    await self.send_json({
                        "type": "authenticated",
                        "booking_uuid": self.booking_uuid,
                    })
                    return
            await self.send_json({
                "type": "error",
                "message": "Authentication failed or not authorized for this booking.",
            })
            await self.close(code=4001)
            return

        if not self.authenticated:
            await self.send_json({
                "type": "error",
                "message": "Not authenticated. Send {\"type\": \"authenticate\", \"token\": \"<JWT>\"} first.",
            })
            return

        # ── GPS update ───────────────────────────────────────────────
        if msg_type == "gps_update":
            await self._handle_gps_update(content)
            return

        # ── Status update (arrived, in_progress, completed) ──────────
        if msg_type == "status_update":
            new_status = content.get("status", "")
            if new_status in ("arrived", "in_progress", "completed"):
                await self._update_location_status(new_status)
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "status.update",
                        "status": new_status,
                        "timestamp": timezone.now().isoformat(),
                    },
                )
            return

        await self.send_json({
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        })

    # ── GPS Processing ───────────────────────────────────────────────

    async def _handle_gps_update(self, data):
        """Process a GPS coordinate update from the Service Pro."""
        lat = data.get("latitude")
        lng = data.get("longitude")

        if lat is None or lng is None:
            await self.send_json({
                "type": "error",
                "message": "latitude and longitude are required.",
            })
            return

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            await self.send_json({
                "type": "error",
                "message": "Invalid coordinate values.",
            })
            return

        accuracy = data.get("accuracy")
        heading = data.get("heading")
        speed = data.get("speed")
        eta_minutes = data.get("eta_minutes")
        timestamp = data.get("timestamp", timezone.now().isoformat())

        # ── Persist to database ──────────────────────────────────────
        location_data = await self._persist_location(
            lat, lng, accuracy, heading, speed, eta_minutes,
        )

        # ── Run geofence check ───────────────────────────────────────
        geofence_result = await self._check_geofence(lat, lng)

        # ── Broadcast to all group subscribers ───────────────────────
        broadcast_payload = {
            "type": "location.update",
            "latitude": lat,
            "longitude": lng,
            "accuracy": accuracy,
            "heading": heading,
            "speed": speed,
            "eta_minutes": eta_minutes,
            "status": location_data.get("status", "en_route"),
            "distance_to_property": geofence_result.get("distance_meters"),
            "is_within_geofence": geofence_result.get("triggered", False),
            "geofence_event": geofence_result.get("event_type"),
            "timestamp": timestamp,
        }

        await self.channel_layer.group_send(self.group_name, broadcast_payload)

        # ── If geofence auto-unlock fired, send special event ────────
        if geofence_result.get("auto_unlocked"):
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "geofence.event",
                    "event": "auto_unlock",
                    "distance_meters": geofence_result.get("distance_meters"),
                    "device_name": geofence_result.get("device_name", "Smart Lock"),
                    "timestamp": timezone.now().isoformat(),
                },
            )

    # ── Channel Layer Event Handlers ─────────────────────────────────
    # These are called when group_send dispatches to this consumer.

    async def location_update(self, event):
        """Forward a location update to the WebSocket client."""
        await self.send_json({
            "type": "location_update",
            "latitude": event["latitude"],
            "longitude": event["longitude"],
            "accuracy": event.get("accuracy"),
            "heading": event.get("heading"),
            "speed": event.get("speed"),
            "eta_minutes": event.get("eta_minutes"),
            "status": event.get("status"),
            "distance_to_property": event.get("distance_to_property"),
            "is_within_geofence": event.get("is_within_geofence"),
            "geofence_event": event.get("geofence_event"),
            "timestamp": event.get("timestamp"),
        })

    async def geofence_event(self, event):
        """Forward a geofence event to the WebSocket client."""
        await self.send_json({
            "type": "geofence_event",
            "event": event.get("event"),
            "distance_meters": event.get("distance_meters"),
            "device_name": event.get("device_name"),
            "timestamp": event.get("timestamp"),
        })

    async def status_update(self, event):
        """Forward a status change to the WebSocket client."""
        await self.send_json({
            "type": "status_update",
            "status": event.get("status"),
            "timestamp": event.get("timestamp"),
        })

    # ── Database Operations (sync → async bridge) ────────────────────

    @database_sync_to_async
    def _validate_participant(self, user):
        """
        Verify the user is either the assigned Service Pro or the
        Resident for this booking.
        """
        from apps.bookings.models import Booking

        try:
            booking = Booking.objects.select_related("client", "place").get(
                uuid=self.booking_uuid if hasattr(Booking, 'uuid') else None,
                id=self.booking_uuid if not hasattr(Booking, 'uuid') else None,
            )
        except (Booking.DoesNotExist, ValueError):
            # Try by short_id or id
            try:
                booking = Booking.objects.select_related("client", "place").get(
                    id=int(self.booking_uuid),
                )
            except (Booking.DoesNotExist, ValueError, TypeError):
                return False

        self.booking = booking

        # Service Pro: check assignment via booking's cleaner/service pro fields
        # The booking model uses different field names in the legacy codebase
        assigned_pro = getattr(booking, "cleaner", None) or getattr(booking, "service_pro", None)
        if assigned_pro and assigned_pro.id == user.id:
            self.service_pro = user
            return True

        # Resident: the booking client
        if booking.client and booking.client.id == user.id:
            return True

        # Platform Admin override
        from apps.users.models import User
        if hasattr(User, "ROLE_PLATFORM_ADMIN") and user.role == User.ROLE_PLATFORM_ADMIN:
            return True

        return False

    @database_sync_to_async
    def _authenticate_jwt(self, token):
        """Validate a JWT token and return the user."""
        try:
            from rest_framework_simplejwt.tokens import AccessToken

            validated = AccessToken(token)
            user_id = validated.get("user_id")

            from apps.users.models import User
            return User.objects.get(id=user_id)
        except Exception as exc:
            logger.warning("JWT authentication failed: %s", exc)
            return None

    @database_sync_to_async
    def _persist_location(self, lat, lng, accuracy, heading, speed, eta_minutes):
        """Create or update the ServiceProLocation record."""
        from .gps_models import ServiceProLocation

        if not self.booking or not self.service_pro:
            return {"status": "en_route"}

        location, created = ServiceProLocation.objects.update_or_create(
            booking=self.booking,
            defaults={
                "service_pro": self.service_pro,
                "latitude": lat,
                "longitude": lng,
                "accuracy_meters": accuracy,
                "heading": heading,
                "speed_mps": speed,
                "eta_minutes": eta_minutes,
            },
        )
        return {"status": location.status}

    @database_sync_to_async
    def _check_geofence(self, lat, lng):
        """Run geofence check and trigger auto-unlock if applicable."""
        if not self.booking or not self.service_pro:
            return {}

        from .geofence_service import check_geofence_and_trigger

        return check_geofence_and_trigger(
            service_pro=self.service_pro,
            booking=self.booking,
            latitude=lat,
            longitude=lng,
        )

    @database_sync_to_async
    def _update_location_status(self, new_status):
        """Update the ServiceProLocation status."""
        from .gps_models import ServiceProLocation

        if not self.booking:
            return

        ServiceProLocation.objects.filter(
            booking=self.booking,
        ).update(status=new_status)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Alert Consumer (Support Architect Notifications)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AlertConsumer(AsyncJsonWebsocketConsumer):
    """
    Read-only WebSocket for Support Architect emergency alerts.

    Connection URL: /ws/alerts/

    Outbound messages:
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
    """

    group_name = "support_architects_alerts"

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Verify the user is a Support Architect or Platform Admin
        is_authorized = await self._check_authorization(user)
        if not is_authorized:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({
            "type": "connected",
            "message": "Connected to emergency alerts channel.",
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name, self.channel_name
        )

    async def receive_json(self, content, **kwargs):
        """Alert channel is read-only."""
        await self.send_json({
            "type": "error",
            "message": "This channel is read-only.",
        })

    # ── Event handlers ───────────────────────────────────────────────

    async def emergency_lockout(self, event):
        """Forward emergency lockout alert to the client."""
        await self.send_json({
            "type": "emergency_lockout",
            **event.get("payload", {}),
        })

    # ── Authorization ────────────────────────────────────────────────

    @database_sync_to_async
    def _check_authorization(self, user):
        """Check if the user is a Support Architect or Platform Admin."""
        from apps.users.models import User
        return user.role in (
            User.ROLE_SUPPORT_ARCHITECT,
            User.ROLE_PLATFORM_ADMIN,
        )
