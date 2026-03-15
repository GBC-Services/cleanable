"""
Resolution Pipeline — DRF API Views
=====================================

Endpoints:
  Complaints:
    POST   /api/v1/support/complaints/                — Resident creates a complaint
    GET    /api/v1/support/complaints/                — List (filtered by role)
    GET    /api/v1/support/complaints/<uuid>/          — Detail
    PATCH  /api/v1/support/complaints/<uuid>/          — Update (Support Architect)
    POST   /api/v1/support/complaints/<uuid>/acknowledge/ — Acknowledge
    GET    /api/v1/support/complaints/stats/           — Dashboard stats

  Resolution Actions (Decision Array):
    POST   /api/v1/support/complaints/<uuid>/refund/      — Execute refund
    POST   /api/v1/support/complaints/<uuid>/redo/        — Schedule re-do
    POST   /api/v1/support/complaints/<uuid>/blacklist/   — Cancel & Blacklist
    POST   /api/v1/support/complaints/<uuid>/note/        — Add internal note

  Blacklist:
    GET    /api/v1/support/blacklist/                  — List all blacklist entries

  Notifications:
    GET    /api/v1/support/complaints/<uuid>/notifications/ — Notification log
"""

import logging

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import (
    IsResident,
    IsSupportArchitect,
    IsPlatformAdmin,
)
from apps.support.models import SupportTicket
from apps.support.resolution_models import (
    AgencyBlacklist,
    Complaint,
    ComplaintNotification,
    ResolutionAction,
)
from apps.support.resolution_serializers import (
    AddNoteInputSerializer,
    AgencyBlacklistSerializer,
    CancelBlacklistInputSerializer,
    ComplaintCreateSerializer,
    ComplaintDetailSerializer,
    ComplaintListSerializer,
    ComplaintNotificationSerializer,
    ComplaintUpdateSerializer,
    RefundInputSerializer,
    ScheduleRedoInputSerializer,
)
from apps.support.resolution_engine import (
    add_resolution_note,
    execute_cancel_blacklist,
    execute_refund,
    execute_schedule_redo,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Complaint CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplaintListCreateView(generics.ListCreateAPIView):
    """
    GET  — List complaints (Residents see their own; Support Architects see all).
    POST — Resident creates a complaint → auto-escalated.
    """

    permission_classes = [
        permissions.IsAuthenticated
        & (IsResident | IsSupportArchitect | IsPlatformAdmin)
    ]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ComplaintCreateSerializer
        return ComplaintListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Complaint.objects.select_related(
            "resident", "booking", "cleaning", "company", "assigned_to",
        )

        # Residents see only their own complaints
        if user.role == user.ROLE_RESIDENT:
            qs = qs.filter(resident=user)
        # Support Architects + Admins see all
        # Filter by status
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        # Filter by scenario
        scenario_param = self.request.query_params.get("scenario")
        if scenario_param:
            qs = qs.filter(scenario=scenario_param)
        # Filter by urgency
        urgency_param = self.request.query_params.get("urgency")
        if urgency_param:
            qs = qs.filter(urgency=int(urgency_param))

        return qs

    def perform_create(self, serializer):
        complaint = serializer.save()
        # Auto-create a linked SupportTicket for the existing pipeline
        try:
            ticket = SupportTicket.objects.create(
                booking=complaint.booking,
                subject=f"Complaint: {complaint.get_scenario_display()}",
                text=complaint.description,
                user=complaint.resident,
                status=SupportTicket.STATUS_ESCALATED,
                priority=SupportTicket.PRIORITY_URGENT
                if complaint.urgency >= Complaint.URGENCY_HIGH
                else SupportTicket.PRIORITY_HIGH,
            )
            complaint.support_ticket = ticket
            complaint.save(update_fields=["support_ticket"])
        except Exception as e:
            logger.warning("Failed to auto-create SupportTicket: %s", e)

        # Dispatch initial escalation notification
        from apps.support.resolution_engine import _dispatch_notification, _collect_stakeholders
        from apps.users.models import User

        # Notify all Support Architects
        support_architects = User.objects.filter(
            role=User.ROLE_SUPPORT_ARCHITECT,
            is_active=True,
        )
        msg = (
            f"NEW COMPLAINT: {complaint.get_scenario_display()} — "
            f"Booking #{complaint.booking.short_id}. "
            f"Urgency: {complaint.get_urgency_display()}. "
            f"Resident: {complaint.resident.first_name} {complaint.resident.last_name}. "
            f"Immediate attention required."
        )
        for architect in support_architects:
            for channel in [
                ComplaintNotification.CHANNEL_PUSH,
                ComplaintNotification.CHANNEL_IN_APP,
            ]:
                _dispatch_notification(complaint, None, architect, channel, msg)
            if getattr(architect, "phone", None):
                _dispatch_notification(
                    complaint, None, architect,
                    ComplaintNotification.CHANNEL_SMS, msg,
                )


class ComplaintDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   — Complaint detail with resolution actions and notifications.
    PATCH — Support Architect updates status, urgency, assignment.
    """

    permission_classes = [
        permissions.IsAuthenticated
        & (IsResident | IsSupportArchitect | IsPlatformAdmin)
    ]
    lookup_field = "uuid"

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return ComplaintUpdateSerializer
        return ComplaintDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Complaint.objects.select_related(
            "resident", "booking", "cleaning", "company",
            "assigned_to", "support_ticket",
        ).prefetch_related(
            "resolution_actions__notifications",
            "notifications",
        )
        if user.role == user.ROLE_RESIDENT:
            qs = qs.filter(resident=user)
        return qs


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Acknowledge
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplaintAcknowledgeView(APIView):
    """POST — Support Architect acknowledges a complaint."""

    permission_classes = [
        permissions.IsAuthenticated
        & (IsSupportArchitect | IsPlatformAdmin)
    ]

    def post(self, request, uuid):
        try:
            complaint = Complaint.objects.get(uuid=uuid)
        except Complaint.DoesNotExist:
            return Response(
                {"detail": "Complaint not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if complaint.status not in (Complaint.STATUS_OPEN,):
            return Response(
                {"detail": "Complaint has already been acknowledged."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        complaint.status = Complaint.STATUS_ACKNOWLEDGED
        complaint.acknowledged_at = timezone.now()
        complaint.assigned_to = request.user
        complaint.save(update_fields=[
            "status", "acknowledged_at", "assigned_to", "updated",
        ])

        return Response(
            ComplaintDetailSerializer(complaint).data,
            status=status.HTTP_200_OK,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Decision Array — Resolution Actions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RefundView(APIView):
    """POST — Execute partial or full refund via Stripe."""

    permission_classes = [
        permissions.IsAuthenticated
        & (IsSupportArchitect | IsPlatformAdmin)
    ]

    def post(self, request, uuid):
        try:
            complaint = Complaint.objects.select_related("booking").get(uuid=uuid)
        except Complaint.DoesNotExist:
            return Response(
                {"detail": "Complaint not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = RefundInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        action = execute_refund(
            complaint=complaint,
            performed_by=request.user,
            refund_type=data["refund_type"],
            amount=data.get("amount"),
            notes=data.get("notes", ""),
        )

        from apps.support.resolution_serializers import ResolutionActionDetailSerializer
        return Response(
            ResolutionActionDetailSerializer(action).data,
            status=status.HTTP_201_CREATED,
        )


class ScheduleRedoView(APIView):
    """POST — Schedule a high-priority re-cleaning."""

    permission_classes = [
        permissions.IsAuthenticated
        & (IsSupportArchitect | IsPlatformAdmin)
    ]

    def post(self, request, uuid):
        try:
            complaint = Complaint.objects.select_related(
                "booking", "cleaning", "company",
            ).get(uuid=uuid)
        except Complaint.DoesNotExist:
            return Response(
                {"detail": "Complaint not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ScheduleRedoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        action = execute_schedule_redo(
            complaint=complaint,
            performed_by=request.user,
            use_different_agency=data["use_different_agency"],
            preferred_company_id=data.get("preferred_company_id"),
            notes=data.get("notes", ""),
        )

        from apps.support.resolution_serializers import ResolutionActionDetailSerializer
        return Response(
            ResolutionActionDetailSerializer(action).data,
            status=status.HTTP_201_CREATED,
        )


class CancelBlacklistView(APIView):
    """POST — Cancel service and blacklist the agency."""

    permission_classes = [
        permissions.IsAuthenticated
        & (IsSupportArchitect | IsPlatformAdmin)
    ]

    def post(self, request, uuid):
        try:
            complaint = Complaint.objects.select_related(
                "booking", "cleaning", "company",
            ).get(uuid=uuid)
        except Complaint.DoesNotExist:
            return Response(
                {"detail": "Complaint not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CancelBlacklistInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = execute_cancel_blacklist(
            complaint=complaint,
            performed_by=request.user,
            notes=serializer.validated_data.get("notes", ""),
        )

        from apps.support.resolution_serializers import ResolutionActionDetailSerializer
        return Response(
            ResolutionActionDetailSerializer(action).data,
            status=status.HTTP_201_CREATED,
        )


class AddNoteView(APIView):
    """POST — Add an internal note to the complaint."""

    permission_classes = [
        permissions.IsAuthenticated
        & (IsSupportArchitect | IsPlatformAdmin)
    ]

    def post(self, request, uuid):
        try:
            complaint = Complaint.objects.get(uuid=uuid)
        except Complaint.DoesNotExist:
            return Response(
                {"detail": "Complaint not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AddNoteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = add_resolution_note(
            complaint=complaint,
            performed_by=request.user,
            notes=serializer.validated_data["notes"],
        )

        from apps.support.resolution_serializers import ResolutionActionDetailSerializer
        return Response(
            ResolutionActionDetailSerializer(action).data,
            status=status.HTTP_201_CREATED,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Dashboard Stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplaintStatsView(APIView):
    """GET — Aggregated complaint stats for the Support Architect dashboard."""

    permission_classes = [
        permissions.IsAuthenticated
        & (IsSupportArchitect | IsPlatformAdmin)
    ]

    def get(self, request):
        qs = Complaint.objects.all()
        now = timezone.now()
        today = now.date()

        open_statuses = [
            Complaint.STATUS_OPEN,
            Complaint.STATUS_ACKNOWLEDGED,
            Complaint.STATUS_INVESTIGATING,
        ]

        stats = {
            "total": qs.count(),
            "open": qs.filter(status__in=open_statuses).count(),
            "unacknowledged": qs.filter(status=Complaint.STATUS_OPEN).count(),
            "resolved_today": qs.filter(
                status=Complaint.STATUS_RESOLVED,
                resolved_at__date=today,
            ).count(),
            "by_scenario": dict(
                qs.values_list("scenario")
                .annotate(count=Count("id"))
                .values_list("scenario", "count")
            ),
            "by_urgency": dict(
                qs.filter(status__in=open_statuses)
                .values_list("urgency")
                .annotate(count=Count("id"))
                .values_list("urgency", "count")
            ),
            "actions_today": ResolutionAction.objects.filter(
                executed_at__date=today,
            ).count(),
            "active_blacklists": AgencyBlacklist.objects.filter(
                is_active=True,
            ).count(),
        }

        return Response(stats, status=status.HTTP_200_OK)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Blacklist
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class BlacklistListView(generics.ListAPIView):
    """GET — List all agency blacklist entries."""

    permission_classes = [
        permissions.IsAuthenticated
        & (IsSupportArchitect | IsPlatformAdmin)
    ]
    serializer_class = AgencyBlacklistSerializer

    def get_queryset(self):
        return AgencyBlacklist.objects.select_related(
            "resident", "company", "complaint",
        ).filter(is_active=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Notification Log
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplaintNotificationsView(generics.ListAPIView):
    """GET — List all notifications for a specific complaint."""

    permission_classes = [
        permissions.IsAuthenticated
        & (IsSupportArchitect | IsPlatformAdmin)
    ]
    serializer_class = ComplaintNotificationSerializer

    def get_queryset(self):
        return ComplaintNotification.objects.filter(
            complaint__uuid=self.kwargs["uuid"],
        ).select_related("recipient")
