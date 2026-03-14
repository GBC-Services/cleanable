"""
GPS Tracking & Geofence REST API Views
========================================

HTTP endpoints complementing the WebSocket GPS consumer:

  POST /api/v1/iot/gps/update/               — HTTP fallback for GPS updates
  GET  /api/v1/iot/gps/location/{booking_id}/ — Get current Service Pro location
  POST /api/v1/iot/geofence/setup/            — Create/update a property geofence
  GET  /api/v1/iot/geofence/{place_id}/       — Get geofence for a property
  POST /api/v1/iot/recommendations/           — Proxy to Cloudflare Worker AI

These are REST fallbacks for environments where WebSocket is unavailable
and for initial geofence configuration.
"""

import logging

import requests as http_requests
from django.conf import settings
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import (
    IsResident,
    IsPlatformAdmin,
    IsServicePro,
    IsSupportArchitect,
)
from apps.bookings.models import Booking
from apps.clients.models import Place

from .geofence_service import check_geofence_and_trigger
from .gps_models import GeofenceEvent, PropertyGeofence, ServiceProLocation

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GPSUpdateSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    accuracy = serializers.FloatField(required=False, allow_null=True)
    heading = serializers.FloatField(required=False, allow_null=True)
    speed = serializers.FloatField(required=False, allow_null=True)
    eta_minutes = serializers.IntegerField(required=False, allow_null=True)


class GeofenceSetupSerializer(serializers.Serializer):
    place_id = serializers.IntegerField()
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    radius_meters = serializers.FloatField(required=False, default=50.0, min_value=10, max_value=500)


class ServiceProLocationSerializer(serializers.ModelSerializer):
    service_pro_name = serializers.SerializerMethodField()

    class Meta:
        model = ServiceProLocation
        fields = [
            "uuid", "latitude", "longitude", "accuracy_meters",
            "heading", "speed_mps", "eta_minutes", "status",
            "is_within_geofence", "distance_to_property_meters",
            "last_updated_at", "service_pro_name",
        ]

    def get_service_pro_name(self, obj):
        return obj.service_pro.get_full_name() or obj.service_pro.email


class PropertyGeofenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyGeofence
        fields = [
            "uuid", "latitude", "longitude", "radius_meters",
            "geocoded_address", "is_active", "created_at",
        ]


class GeofenceEventSerializer(serializers.ModelSerializer):
    event_display = serializers.CharField(source="get_event_type_display")

    class Meta:
        model = GeofenceEvent
        fields = [
            "uuid", "event_type", "event_display", "latitude", "longitude",
            "distance_meters", "metadata", "created_at",
        ]


class RecommendationRequestSerializer(serializers.Serializer):
    place_id = serializers.IntegerField(required=False, allow_null=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GPS Update (HTTP Fallback)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GPSUpdateView(APIView):
    """
    POST /api/v1/iot/gps/update/

    HTTP fallback for submitting GPS updates when WebSocket is unavailable.
    Performs the same geofence check as the WebSocket consumer.

    Authorization: Service Pro only.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsServicePro | IsPlatformAdmin,
    ]

    def post(self, request):
        serializer = GPSUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Verify the booking belongs to this Service Pro
        try:
            booking = Booking.objects.select_related("place", "client").get(
                id=data["booking_id"],
            )
        except Booking.DoesNotExist:
            return Response(
                {"detail": "Booking not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check assignment
        assigned = getattr(booking, "cleaner", None) or getattr(booking, "service_pro", None)
        if not assigned or assigned.id != request.user.id:
            return Response(
                {"detail": "Not assigned to this booking."},
                status=status.HTTP_403_FORBIDDEN,
            )

        lat = data["latitude"]
        lng = data["longitude"]

        # Persist location
        location, _ = ServiceProLocation.objects.update_or_create(
            booking=booking,
            defaults={
                "service_pro": request.user,
                "latitude": lat,
                "longitude": lng,
                "accuracy_meters": data.get("accuracy"),
                "heading": data.get("heading"),
                "speed_mps": data.get("speed"),
                "eta_minutes": data.get("eta_minutes"),
            },
        )

        # Run geofence check
        geofence_result = check_geofence_and_trigger(
            service_pro=request.user,
            booking=booking,
            latitude=lat,
            longitude=lng,
        )

        # Update geofence-related fields
        location.is_within_geofence = geofence_result.get("triggered", False)
        location.distance_to_property_meters = geofence_result.get("distance_meters")
        location.save(update_fields=[
            "is_within_geofence", "distance_to_property_meters", "last_updated_at",
        ])

        # Broadcast via channel layer if available
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            if channel_layer:
                group_name = f"gps_tracking_{booking.id}"
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "location.update",
                        "latitude": lat,
                        "longitude": lng,
                        "accuracy": data.get("accuracy"),
                        "heading": data.get("heading"),
                        "speed": data.get("speed"),
                        "eta_minutes": data.get("eta_minutes"),
                        "status": location.status,
                        "distance_to_property": geofence_result.get("distance_meters"),
                        "is_within_geofence": geofence_result.get("triggered", False),
                        "geofence_event": geofence_result.get("event_type"),
                        "timestamp": location.last_updated_at.isoformat(),
                    },
                )
        except ImportError:
            pass

        return Response({
            "location": ServiceProLocationSerializer(location).data,
            "geofence": geofence_result,
        })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Service Pro Location (Read)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ServiceProLocationView(APIView):
    """
    GET /api/v1/iot/gps/location/{booking_id}/

    Get the current location of the assigned Service Pro for a booking.

    Authorization: Resident (booking owner), Service Pro (assigned),
    or Platform Admin.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsResident | IsServicePro | IsPlatformAdmin,
    ]

    def get(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {"detail": "Booking not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Authorization: must be the Resident or assigned Pro
        is_owner = booking.client and booking.client.id == request.user.id
        assigned = getattr(booking, "cleaner", None) or getattr(booking, "service_pro", None)
        is_assigned = assigned and assigned.id == request.user.id
        from apps.users.models import User
        is_admin = request.user.role == User.ROLE_PLATFORM_ADMIN

        if not (is_owner or is_assigned or is_admin):
            return Response(
                {"detail": "Not authorized to view this booking's location."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            location = ServiceProLocation.objects.get(booking=booking)
        except ServiceProLocation.DoesNotExist:
            return Response(
                {"detail": "No location data available for this booking."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get geofence events for this booking
        events = GeofenceEvent.objects.filter(
            booking=booking,
        ).order_by("-created_at")[:10]

        return Response({
            "location": ServiceProLocationSerializer(location).data,
            "geofence_events": GeofenceEventSerializer(events, many=True).data,
        })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Geofence Setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GeofenceSetupView(APIView):
    """
    POST /api/v1/iot/geofence/setup/

    Create or update a property geofence with GPS coordinates.

    Authorization: Resident (property owner) or Platform Admin.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsResident | IsPlatformAdmin,
    ]

    def post(self, request):
        serializer = GeofenceSetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            place = Place.objects.get(
                id=data["place_id"],
                client=request.user,
            )
        except Place.DoesNotExist:
            return Response(
                {"detail": "Property not found or not owned by you."},
                status=status.HTTP_404_NOT_FOUND,
            )

        geofence, created = PropertyGeofence.objects.update_or_create(
            place=place,
            defaults={
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "radius_meters": data.get("radius_meters", 50.0),
                "geocoded_address": str(place),
                "is_active": True,
            },
        )

        return Response(
            {
                "detail": "Geofence created." if created else "Geofence updated.",
                "geofence": PropertyGeofenceSerializer(geofence).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class GeofenceDetailView(APIView):
    """
    GET /api/v1/iot/geofence/{place_id}/

    Retrieve the geofence configuration for a property.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsResident | IsPlatformAdmin,
    ]

    def get(self, request, place_id):
        try:
            geofence = PropertyGeofence.objects.get(
                place_id=place_id,
                place__client=request.user,
                is_active=True,
            )
        except PropertyGeofence.DoesNotExist:
            return Response(
                {"detail": "No geofence configured for this property."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(PropertyGeofenceSerializer(geofence).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Predictive Recommendations (Cloudflare Worker Proxy)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PredictiveRecommendationsView(APIView):
    """
    POST /api/v1/iot/recommendations/

    Proxy endpoint that gathers the Resident's booking history,
    property data, and location, then forwards to the Cloudflare
    Worker for AI-powered predictive analysis.

    Authorization: Resident or Platform Admin.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsResident | IsPlatformAdmin,
    ]

    def post(self, request):
        serializer = RecommendationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        place_id = serializer.validated_data.get("place_id")

        # ── Gather booking history ────────────────────────────────────
        booking_qs = Booking.objects.filter(client=user).order_by("-scheduled_date")

        if place_id:
            booking_qs = booking_qs.filter(place_id=place_id)

        bookings = booking_qs[:30]

        booking_history = []
        for b in bookings:
            booking_history.append({
                "booking_id": b.id,
                "service_type": b.get_regularity_type_display() if hasattr(b, "get_regularity_type_display") else "Standard",
                "scheduled_date": str(b.scheduled_date) if b.scheduled_date else "",
                "status": b.get_status_display() if hasattr(b, "get_status_display") else "Unknown",
                "regularity": b.get_regularity_option_display() if b.regularity_option and hasattr(b, "get_regularity_option_display") else "One-time",
                "bedrooms": b.bedrooms_nmb or 0,
                "bathrooms": b.bathrooms_nmb or 0,
                "area_size": b.area_size or 0,
                "place_type": b.get_place_type_display() if hasattr(b, "get_place_type_display") else "Apartment",
            })

        # ── Gather property + location data ───────────────────────────
        place = None
        if place_id:
            try:
                place = Place.objects.select_related("city", "state", "zip_code").get(
                    id=place_id, client=user,
                )
            except Place.DoesNotExist:
                pass

        if not place:
            place = Place.objects.filter(client=user).select_related(
                "city", "state", "zip_code",
            ).first()

        if not place:
            return Response(
                {"detail": "No property found. Please add a property first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get geofence coordinates if available
        geofence = getattr(place, "geofence", None)
        lat = geofence.latitude if geofence else None
        lng = geofence.longitude if geofence else None

        location = {
            "city": str(place.city) if place.city else "",
            "state": str(place.state) if place.state else "",
            "zip_code": str(place.zip_code) if place.zip_code else "",
            "latitude": lat,
            "longitude": lng,
        }

        prop = {
            "place_type": place.get_type_display() if hasattr(place, "get_type_display") else "Apartment",
            "bedrooms": place.bedrooms_nmb or 2,
            "bathrooms": place.bathrooms_nmb or 1,
            "area_size": place.area_size or 1000,
        }

        # ── Call Cloudflare Worker ────────────────────────────────────
        worker_url = getattr(settings, "CLOUDFLARE_WORKER_URL", "")
        worker_key = getattr(settings, "CLOUDFLARE_WORKER_API_KEY", "")

        if not worker_url or not worker_key:
            return Response(
                {"detail": "Predictive recommendations service not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = {
            "resident_id": user.id,
            "resident_name": user.get_full_name() or user.email,
            "booking_history": booking_history,
            "location": location,
            "property": prop,
        }

        try:
            resp = http_requests.post(
                f"{worker_url}/recommend",
                json=payload,
                headers={
                    "Authorization": f"Bearer {worker_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return Response(resp.json())

        except http_requests.Timeout:
            return Response(
                {"detail": "Recommendation service timed out. Please try again."},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except http_requests.RequestException as exc:
            logger.error("Cloudflare Worker request failed: %s", exc)
            return Response(
                {"detail": "Recommendation service unavailable."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
