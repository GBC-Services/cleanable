"""
Location Privacy & Fleet Management REST API Views
====================================================

Endpoints for Ghost Mode, Strict Tracking, and GPS history:

  Service Pro Endpoints:
    GET/POST  /api/v1/iot/ghost-mode/            — Get or toggle Ghost Mode
    POST      /api/v1/iot/ghost-mode/checkin/     — Manual geographic check-in

  Agency Owner Endpoints:
    GET       /api/v1/iot/fleet/pros/             — List Service Pros with tracking status
    POST      /api/v1/iot/fleet/strict-tracking/  — Set strict tracking for a pro
    GET       /api/v1/iot/fleet/alerts/           — Ghost Mode conflict alerts

  Platform Admin Endpoints:
    GET       /api/v1/iot/gps-history/            — Query GPS history logs
    DELETE    /api/v1/iot/gps-history/scrub/      — Trigger manual GPS data scrub
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import (
    IsAgencyOwner,
    IsPlatformAdmin,
    IsServicePro,
    IsSupportArchitect,
)
from apps.users.models import User

from .privacy_models import (
    GhostModeAlert,
    GhostModeState,
    GPSHistoryLog,
    StrictTrackingRule,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GhostModeStateSerializer(serializers.ModelSerializer):
    service_pro_name = serializers.SerializerMethodField()
    is_strict_tracking_enforced = serializers.SerializerMethodField()

    class Meta:
        model = GhostModeState
        fields = [
            "uuid",
            "is_active",
            "activated_at",
            "deactivated_at",
            "last_manual_checkin_at",
            "last_manual_checkin_lat",
            "last_manual_checkin_lng",
            "service_pro_name",
            "is_strict_tracking_enforced",
        ]

    def get_service_pro_name(self, obj):
        return obj.service_pro.get_full_name() or obj.service_pro.email

    def get_is_strict_tracking_enforced(self, obj):
        """Check if any Agency Owner has enforced Strict Tracking."""
        return StrictTrackingRule.objects.filter(
            service_pro=obj.service_pro,
            is_enforced=True,
        ).exists()


class GhostModeToggleSerializer(serializers.Serializer):
    enable = serializers.BooleanField()


class ManualCheckinSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class StrictTrackingSerializer(serializers.ModelSerializer):
    service_pro_name = serializers.SerializerMethodField()
    service_pro_email = serializers.SerializerMethodField()

    class Meta:
        model = StrictTrackingRule
        fields = [
            "uuid",
            "service_pro",
            "service_pro_name",
            "service_pro_email",
            "is_enforced",
            "reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uuid", "created_at", "updated_at"]

    def get_service_pro_name(self, obj):
        return obj.service_pro.get_full_name() or obj.service_pro.email

    def get_service_pro_email(self, obj):
        return obj.service_pro.email


class StrictTrackingCreateSerializer(serializers.Serializer):
    service_pro_id = serializers.IntegerField()
    is_enforced = serializers.BooleanField(default=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class GhostModeAlertSerializer(serializers.ModelSerializer):
    service_pro_name = serializers.SerializerMethodField()
    alert_type_display = serializers.CharField(source="get_alert_type_display")
    resolution_display = serializers.CharField(source="get_resolution_display")

    class Meta:
        model = GhostModeAlert
        fields = [
            "uuid",
            "service_pro",
            "service_pro_name",
            "booking",
            "alert_type",
            "alert_type_display",
            "resolution",
            "resolution_display",
            "message",
            "metadata",
            "created_at",
            "resolved_at",
        ]

    def get_service_pro_name(self, obj):
        return obj.service_pro.get_full_name() or obj.service_pro.email


class GPSHistoryLogSerializer(serializers.ModelSerializer):
    service_pro_name = serializers.SerializerMethodField()

    class Meta:
        model = GPSHistoryLog
        fields = [
            "id",
            "service_pro",
            "service_pro_name",
            "booking",
            "latitude",
            "longitude",
            "accuracy_meters",
            "heading",
            "speed_mps",
            "ghost_mode_active",
            "recorded_at",
        ]

    def get_service_pro_name(self, obj):
        return obj.service_pro.get_full_name() or obj.service_pro.email


class FleetProSerializer(serializers.Serializer):
    """Serializer for the fleet management pro listing."""
    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    ghost_mode_active = serializers.BooleanField()
    ghost_mode_since = serializers.DateTimeField(allow_null=True)
    strict_tracking_enforced = serializers.BooleanField()
    strict_tracking_reason = serializers.CharField(allow_blank=True)
    last_gps_lat = serializers.FloatField(allow_null=True)
    last_gps_lng = serializers.FloatField(allow_null=True)
    last_gps_time = serializers.DateTimeField(allow_null=True)
    pending_alerts_count = serializers.IntegerField()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Service Pro: Ghost Mode Toggle
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GhostModeView(APIView):
    """
    GET  /api/v1/iot/ghost-mode/    — Get current Ghost Mode state
    POST /api/v1/iot/ghost-mode/    — Toggle Ghost Mode on/off
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsServicePro | IsPlatformAdmin,
    ]

    def get(self, request):
        ghost_state, _ = GhostModeState.objects.get_or_create(
            service_pro=request.user,
        )
        return Response(GhostModeStateSerializer(ghost_state).data)

    def post(self, request):
        serializer = GhostModeToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enable = serializer.validated_data["enable"]

        ghost_state, _ = GhostModeState.objects.get_or_create(
            service_pro=request.user,
        )

        if enable:
            # Check if Strict Tracking is enforced and there's an active shift
            if self._is_strict_tracking_blocking(request.user):
                return Response(
                    {
                        "detail": (
                            "Ghost Mode cannot be activated. Your Agency Owner has "
                            "enforced Strict Tracking during active shifts."
                        ),
                        "blocked_by": "strict_tracking",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            ghost_state.activate()

            # Trigger conflict check asynchronously
            try:
                from .tasks import check_ghost_mode_conflicts
                check_ghost_mode_conflicts.delay()
            except Exception:
                pass

            return Response({
                "detail": "Ghost Mode activated. Live GPS broadcasting paused.",
                "state": GhostModeStateSerializer(ghost_state).data,
            })
        else:
            ghost_state.deactivate()
            return Response({
                "detail": "Ghost Mode deactivated. GPS broadcasting resumed.",
                "state": GhostModeStateSerializer(ghost_state).data,
            })

    def _is_strict_tracking_blocking(self, user):
        """Check if Strict Tracking prevents Ghost Mode activation."""
        from apps.bookings.models import Booking
        from apps.cleanings.models import CleanerForCleaning

        # Check if any agency owner has enforced strict tracking
        has_strict = StrictTrackingRule.objects.filter(
            service_pro=user,
            is_enforced=True,
        ).exists()

        if not has_strict:
            return False

        # Check if there's an active booking right now
        now = timezone.now()
        active_cleaning_ids = CleanerForCleaning.objects.filter(
            cleaner=user,
        ).values_list("cleaning__booking_id", flat=True)

        has_active_booking = Booking.objects.filter(
            id__in=active_cleaning_ids,
            scheduled_start_dt__lte=now,
            scheduled_end_dt__gte=now,
            status__in=[Booking.STATUS_NEW, Booking.STATUS_IN_WORK],
        ).exists()

        return has_active_booking


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Service Pro: Manual Check-In
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GhostModeCheckinView(APIView):
    """
    POST /api/v1/iot/ghost-mode/checkin/

    Manual geographic check-in while Ghost Mode is active.
    Required when Ghost Mode conflicts with a scheduled job.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsServicePro | IsPlatformAdmin,
    ]

    def post(self, request):
        serializer = ManualCheckinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lat = serializer.validated_data["latitude"]
        lng = serializer.validated_data["longitude"]

        try:
            ghost_state = GhostModeState.objects.get(
                service_pro=request.user,
            )
        except GhostModeState.DoesNotExist:
            return Response(
                {"detail": "Ghost Mode has not been configured."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not ghost_state.is_active:
            return Response(
                {"detail": "Ghost Mode is not currently active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ghost_state.record_manual_checkin(lat, lng)

        # Resolve any pending alerts for this pro
        pending_alerts = GhostModeAlert.objects.filter(
            service_pro=request.user,
            resolution=GhostModeAlert.RESOLUTION_PENDING,
        )
        resolved_count = pending_alerts.update(
            resolution=GhostModeAlert.RESOLUTION_CHECKED_IN,
            resolved_at=timezone.now(),
        )

        # Log the check-in coordinates to GPS history
        GPSHistoryLog.objects.create(
            service_pro=request.user,
            latitude=lat,
            longitude=lng,
            ghost_mode_active=True,
        )

        return Response({
            "detail": "Manual check-in recorded.",
            "latitude": lat,
            "longitude": lng,
            "timestamp": ghost_state.last_manual_checkin_at.isoformat(),
            "resolved_alerts": resolved_count,
        })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Agency Owner: Fleet Management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FleetProsView(APIView):
    """
    GET /api/v1/iot/fleet/pros/

    List all Service Pros under this Agency Owner's company with
    their current Ghost Mode status, strict tracking settings,
    and last known GPS coordinates.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsAgencyOwner | IsPlatformAdmin,
    ]

    def get(self, request):
        user = request.user

        # Get all Service Pros in the same company
        if user.company:
            pros = User.objects.filter(
                company=user.company,
                role=User.ROLE_SERVICE_PRO,
            )
        else:
            # Platform Admin sees all
            if user.role == User.ROLE_PLATFORM_ADMIN:
                pros = User.objects.filter(role=User.ROLE_SERVICE_PRO)
            else:
                pros = User.objects.none()

        results = []
        for pro in pros:
            # Ghost mode state
            ghost_state = getattr(pro, "ghost_mode_state", None)
            if ghost_state is None:
                try:
                    ghost_state = GhostModeState.objects.get(service_pro=pro)
                except GhostModeState.DoesNotExist:
                    ghost_state = None

            # Strict tracking rule from this owner
            strict_rule = StrictTrackingRule.objects.filter(
                agency_owner=user,
                service_pro=pro,
            ).first()

            # Last GPS location
            from .gps_models import ServiceProLocation
            last_loc = ServiceProLocation.objects.filter(
                service_pro=pro,
            ).order_by("-last_updated_at").first()

            # Pending alerts count
            pending_count = GhostModeAlert.objects.filter(
                service_pro=pro,
                agency_owner=user,
                resolution=GhostModeAlert.RESOLUTION_PENDING,
            ).count()

            results.append({
                "id": pro.id,
                "email": pro.email,
                "full_name": pro.get_full_name() or pro.email,
                "ghost_mode_active": ghost_state.is_active if ghost_state else False,
                "ghost_mode_since": ghost_state.activated_at if ghost_state and ghost_state.is_active else None,
                "strict_tracking_enforced": strict_rule.is_enforced if strict_rule else False,
                "strict_tracking_reason": strict_rule.reason if strict_rule else "",
                "last_gps_lat": last_loc.latitude if last_loc else None,
                "last_gps_lng": last_loc.longitude if last_loc else None,
                "last_gps_time": last_loc.last_updated_at if last_loc else None,
                "pending_alerts_count": pending_count,
            })

        serializer = FleetProSerializer(results, many=True)
        return Response({
            "count": len(results),
            "results": serializer.data,
        })


class StrictTrackingView(APIView):
    """
    GET  /api/v1/iot/fleet/strict-tracking/    — List rules
    POST /api/v1/iot/fleet/strict-tracking/    — Create/update a rule
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsAgencyOwner | IsPlatformAdmin,
    ]

    def get(self, request):
        rules = StrictTrackingRule.objects.filter(
            agency_owner=request.user,
        ).select_related("service_pro")
        return Response({
            "count": rules.count(),
            "results": StrictTrackingSerializer(rules, many=True).data,
        })

    def post(self, request):
        serializer = StrictTrackingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Verify the Service Pro exists and is in the same company
        try:
            pro = User.objects.get(
                id=data["service_pro_id"],
                role=User.ROLE_SERVICE_PRO,
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Service Pro not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Company check (unless Platform Admin)
        if request.user.role != User.ROLE_PLATFORM_ADMIN:
            if not request.user.company or pro.company != request.user.company:
                return Response(
                    {"detail": "This Service Pro is not in your agency."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        rule, created = StrictTrackingRule.objects.update_or_create(
            agency_owner=request.user,
            service_pro=pro,
            defaults={
                "is_enforced": data["is_enforced"],
                "reason": data.get("reason", ""),
            },
        )

        # If strict tracking is now enforced and the pro has ghost mode on
        # during an active shift, auto-deactivate ghost mode
        if rule.is_enforced:
            try:
                ghost_state = GhostModeState.objects.get(
                    service_pro=pro,
                    is_active=True,
                )
                # Check for active shift
                view = GhostModeView()
                if view._is_strict_tracking_blocking(pro):
                    ghost_state.deactivate()
                    logger.info(
                        "Auto-deactivated Ghost Mode for %s due to strict tracking enforcement",
                        pro.email,
                    )
            except GhostModeState.DoesNotExist:
                pass

        return Response(
            {
                "detail": "Strict tracking rule created." if created else "Strict tracking rule updated.",
                "rule": StrictTrackingSerializer(rule).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class FleetAlertsView(APIView):
    """
    GET /api/v1/iot/fleet/alerts/

    List Ghost Mode alerts for the Agency Owner's team.
    Supports filtering by resolution status.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsAgencyOwner | IsPlatformAdmin,
    ]

    def get(self, request):
        queryset = GhostModeAlert.objects.filter(
            agency_owner=request.user,
        ).select_related("service_pro", "booking")

        # Optional filters
        resolution = request.query_params.get("resolution")
        if resolution:
            queryset = queryset.filter(resolution=resolution)

        service_pro_id = request.query_params.get("service_pro_id")
        if service_pro_id:
            queryset = queryset.filter(service_pro_id=service_pro_id)

        alerts = queryset[:50]

        return Response({
            "count": queryset.count(),
            "results": GhostModeAlertSerializer(alerts, many=True).data,
        })

    def patch(self, request):
        """Resolve an alert."""
        alert_uuid = request.data.get("alert_uuid")
        new_resolution = request.data.get("resolution")

        if not alert_uuid or not new_resolution:
            return Response(
                {"detail": "alert_uuid and resolution are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_resolutions = [c[0] for c in GhostModeAlert.RESOLUTION_CHOICES]
        if new_resolution not in valid_resolutions:
            return Response(
                {"detail": f"Invalid resolution. Choose from: {valid_resolutions}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            alert = GhostModeAlert.objects.get(
                uuid=alert_uuid,
                agency_owner=request.user,
            )
        except GhostModeAlert.DoesNotExist:
            return Response(
                {"detail": "Alert not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        alert.resolution = new_resolution
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["resolution", "resolved_at"])

        return Response({
            "detail": "Alert updated.",
            "alert": GhostModeAlertSerializer(alert).data,
        })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Platform Admin: GPS History
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GPSHistoryView(APIView):
    """
    GET /api/v1/iot/gps-history/

    Query GPS history logs for dispute resolution.
    Requires Platform Admin or Support Architect role.

    Query parameters:
      - service_pro_id: Filter by Service Pro ID
      - booking_id:     Filter by Booking ID
      - from_date:      Start date (ISO format)
      - to_date:        End date (ISO format)
      - limit:          Max records (default 100, max 500)
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsPlatformAdmin | IsSupportArchitect,
    ]

    def get(self, request):
        queryset = GPSHistoryLog.objects.all()

        service_pro_id = request.query_params.get("service_pro_id")
        if service_pro_id:
            queryset = queryset.filter(service_pro_id=service_pro_id)

        booking_id = request.query_params.get("booking_id")
        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)

        from_date = request.query_params.get("from_date")
        if from_date:
            queryset = queryset.filter(recorded_at__gte=from_date)

        to_date = request.query_params.get("to_date")
        if to_date:
            queryset = queryset.filter(recorded_at__lte=to_date)

        limit = min(int(request.query_params.get("limit", 100)), 500)
        logs = queryset.select_related("service_pro")[:limit]

        retention_days = getattr(settings, "GPS_HISTORY_RETENTION_DAYS", 30)

        return Response({
            "count": queryset.count(),
            "retention_days": retention_days,
            "results": GPSHistoryLogSerializer(logs, many=True).data,
        })


class GPSScrubView(APIView):
    """
    POST /api/v1/iot/gps-history/scrub/

    Trigger a manual GPS data scrub (admin-only).
    Normally runs automatically via Celery Beat.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsPlatformAdmin,
    ]

    def post(self, request):
        try:
            from .tasks import scrub_old_gps_history
            result = scrub_old_gps_history.delay()
            return Response({
                "detail": "GPS history scrub task queued.",
                "task_id": result.id,
            })
        except Exception as exc:
            logger.error("Failed to queue GPS scrub task: %s", exc)
            return Response(
                {"detail": "Failed to queue scrub task."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
