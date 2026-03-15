"""
Support & QA — DRF API Views
==============================

REST endpoints for the AI-driven support triage pipeline and
spatial verification (post-job QA).

Endpoints
---------
Tickets:
  GET    /api/v1/support/tickets/              — list (filtered by role)
  POST   /api/v1/support/tickets/              — create
  GET    /api/v1/support/tickets/<uuid>/        — detail
  PATCH  /api/v1/support/tickets/<uuid>/        — update (Support Architect)
  POST   /api/v1/support/tickets/<uuid>/resolve/ — one-click resolve
  POST   /api/v1/support/tickets/<uuid>/messages/ — add message
  GET    /api/v1/support/tickets/stats/         — dashboard stats

Verification (QA):
  POST   /api/v1/support/verify/               — upload media (Service Pro)
  GET    /api/v1/support/verify/               — list verifications
  GET    /api/v1/support/verify/<uuid>/         — detail
  POST   /api/v1/support/verify/<uuid>/review/  — manual review (QA Inspector)

AI Triage Webhook:
  POST   /api/v1/support/webhooks/triage/       — CF Worker callback
"""

import base64
import logging

import requests
from django.conf import settings
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import (
    IsOwnerOrAdmin,
    IsPlatformAdmin,
    IsQAInspector,
    IsServicePro,
    IsStaff,
    IsSupportArchitect,
)
from apps.support.models import (
    JobVerification,
    SupportTicket,
    SupportTicketMessage,
    SupportTicketStatusChange,
)
from apps.support.serializers import (
    JobVerificationDetailSerializer,
    JobVerificationListSerializer,
    JobVerificationReviewSerializer,
    JobVerificationUploadSerializer,
    SupportTicketCreateSerializer,
    SupportTicketDetailSerializer,
    SupportTicketListSerializer,
    SupportTicketUpdateSerializer,
    TicketAITriageSerializer,
    TicketMessageCreateSerializer,
    TicketResolveSerializer,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def dispatch_triage_to_worker(ticket: SupportTicket):
    """
    Fire-and-forget: send the new ticket to the CF Worker for
    sentiment analysis + AI summary + category + suggested response.
    The Worker will call back via /api/v1/support/webhooks/triage/.
    """
    worker_url = getattr(settings, "CLOUDFLARE_WORKER_URL", "")
    api_key = getattr(settings, "CLOUDFLARE_WORKER_API_KEY", "")

    if not worker_url or not api_key:
        logger.warning("CF Worker URL/key not configured; skipping AI triage.")
        return

    triage_url = worker_url.rstrip("/") + "/triage"
    callback_url = getattr(
        settings, "SITE_URL", "http://localhost:8000"
    ).rstrip("/") + "/api/v1/support/webhooks/triage/"

    payload = {
        "ticket_id": ticket.pk,
        "subject": ticket.subject or "",
        "text": ticket.text,
        "user_role": ticket.user.get_role_display() if hasattr(ticket.user, "get_role_display") else "",
        "booking_id": ticket.booking_id,
        "callback_url": callback_url,
    }

    try:
        requests.post(
            triage_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=5,
        )
    except Exception as exc:
        logger.error("Failed to dispatch triage to CF Worker: %s", exc)


def dispatch_verification_to_worker(verification: JobVerification):
    """
    Send the uploaded media to the CF Worker for vision analysis.
    The Worker will call back via /api/v1/support/webhooks/verify/.
    """
    worker_url = getattr(settings, "CLOUDFLARE_WORKER_URL", "")
    api_key = getattr(settings, "CLOUDFLARE_WORKER_API_KEY", "")

    if not worker_url or not api_key:
        logger.warning("CF Worker URL/key not configured; skipping vision QA.")
        return

    verify_url = worker_url.rstrip("/") + "/verify"
    callback_url = getattr(
        settings, "SITE_URL", "http://localhost:8000"
    ).rstrip("/") + "/api/v1/support/webhooks/verify/"

    # Read the uploaded file and base64-encode for the Worker
    try:
        verification.media_file.seek(0)
        file_bytes = verification.media_file.read()
        image_b64 = base64.b64encode(file_bytes).decode("ascii")
    except Exception as exc:
        logger.error("Failed to read media file for verification %s: %s", verification.pk, exc)
        return

    payload = {
        "verification_id": verification.pk,
        "booking_id": verification.booking_id,
        "media_type": verification.media_type,
        "image_base64": image_b64,
        "callback_url": callback_url,
    }

    try:
        verification.status = JobVerification.STATUS_ANALYZING
        verification.save(update_fields=["status", "updated"])

        requests.post(
            verify_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
    except Exception as exc:
        logger.error("Failed to dispatch verification to CF Worker: %s", exc)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Support Ticket Views
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TicketListCreateView(generics.ListCreateAPIView):
    """
    GET  — list tickets. Non-staff see only their own.
    POST — create a ticket and dispatch to AI triage.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SupportTicketCreateSerializer
        return SupportTicketListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = SupportTicket.objects.filter(is_active=True).select_related(
            "user", "assigned_to", "category", "booking",
        )

        # Staff roles see all tickets; others see only their own
        from apps.users.models import User
        staff_roles = {
            User.ROLE_SUPPORT_ARCHITECT,
            User.ROLE_QA_INSPECTOR,
            User.ROLE_PLATFORM_ADMIN,
        }
        if user.role not in staff_roles:
            qs = qs.filter(user=user)

        # Filters
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=int(status_filter))

        priority_filter = self.request.query_params.get("priority")
        if priority_filter:
            qs = qs.filter(priority=int(priority_filter))

        sentiment_filter = self.request.query_params.get("sentiment")
        if sentiment_filter:
            qs = qs.filter(sentiment=sentiment_filter)

        ai_category_filter = self.request.query_params.get("ai_category")
        if ai_category_filter:
            qs = qs.filter(ai_category=ai_category_filter)

        assigned_to_filter = self.request.query_params.get("assigned_to")
        if assigned_to_filter:
            if assigned_to_filter == "unassigned":
                qs = qs.filter(assigned_to__isnull=True)
            else:
                qs = qs.filter(assigned_to_id=int(assigned_to_filter))

        return qs

    def perform_create(self, serializer):
        ticket = serializer.save()
        # Fire AI triage asynchronously
        dispatch_triage_to_worker(ticket)


class TicketDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   — ticket detail with messages and status history.
    PATCH — Support Architect / Platform Admin updates status, priority, etc.
    """
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return SupportTicketUpdateSerializer
        return SupportTicketDetailSerializer

    def get_queryset(self):
        return SupportTicket.objects.filter(is_active=True).select_related(
            "user", "assigned_to", "category", "booking",
        ).prefetch_related("messages__user", "status_changes__user")

    def perform_update(self, serializer):
        old_status = serializer.instance.status
        ticket = serializer.save()

        # Record status change if status was modified
        if ticket.status != old_status:
            SupportTicketStatusChange.objects.create(
                support_ticket=ticket,
                status=ticket.status,
                user=self.request.user,
            )

            # Set resolved_at when resolving
            if ticket.status == SupportTicket.STATUS_RESOLVED and not ticket.resolved_at:
                ticket.resolved_at = timezone.now()
                ticket.save(update_fields=["resolved_at", "updated"])


class TicketResolveView(APIView):
    """POST — one-click resolve (Support Architect / Platform Admin)."""

    permission_classes = [
        permissions.IsAuthenticated,
        IsSupportArchitect | IsPlatformAdmin,
    ]

    def post(self, request, uuid):
        try:
            ticket = SupportTicket.objects.get(uuid=uuid, is_active=True)
        except SupportTicket.DoesNotExist:
            return Response(
                {"detail": "Ticket not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        ser = TicketResolveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        old_status = ticket.status
        ticket.status = SupportTicket.STATUS_RESOLVED
        ticket.resolution_notes = ser.validated_data.get("resolution_notes", "")
        ticket.resolved_at = timezone.now()
        ticket.save(update_fields=["status", "resolution_notes", "resolved_at", "updated"])

        SupportTicketStatusChange.objects.create(
            support_ticket=ticket,
            status=SupportTicket.STATUS_RESOLVED,
            user=request.user,
        )

        return Response(
            {
                "detail": f"Ticket #{ticket.pk} resolved.",
                "ticket": SupportTicketDetailSerializer(ticket).data,
            },
            status=status.HTTP_200_OK,
        )


class TicketMessageCreateView(APIView):
    """POST — add a message to a ticket thread."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, uuid):
        try:
            ticket = SupportTicket.objects.get(uuid=uuid, is_active=True)
        except SupportTicket.DoesNotExist:
            return Response(
                {"detail": "Ticket not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        ser = TicketMessageCreateSerializer(
            data=request.data,
            context={"request": request, "ticket": ticket},
        )
        ser.is_valid(raise_exception=True)
        message = ser.save()

        return Response(
            {
                "detail": "Message added.",
                "message": {
                    "id": message.id,
                    "text": message.text,
                    "user": message.user.pk,
                    "created": message.created,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class TicketStatsView(APIView):
    """GET — dashboard statistics for Support Architect."""

    permission_classes = [
        permissions.IsAuthenticated,
        IsSupportArchitect | IsPlatformAdmin,
    ]

    def get(self, request):
        qs = SupportTicket.objects.filter(is_active=True)
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total = qs.count()
        open_tickets = qs.filter(
            status__in=[SupportTicket.STATUS_NEW, SupportTicket.STATUS_IN_WORK],
        ).count()
        resolved_today = qs.filter(
            status=SupportTicket.STATUS_RESOLVED,
            resolved_at__gte=today_start,
        ).count()
        escalated = qs.filter(status=SupportTicket.STATUS_ESCALATED).count()
        unassigned = qs.filter(
            assigned_to__isnull=True,
            status__in=[SupportTicket.STATUS_NEW, SupportTicket.STATUS_IN_WORK],
        ).count()

        # Priority breakdown
        priority_breakdown = dict(
            qs.filter(
                status__in=[SupportTicket.STATUS_NEW, SupportTicket.STATUS_IN_WORK],
            ).values_list("priority").annotate(c=Count("id")).values_list("priority", "c")
        )

        # Sentiment breakdown
        sentiment_breakdown = dict(
            qs.filter(sentiment__isnull=False).values_list("sentiment").annotate(
                c=Count("id"),
            ).values_list("sentiment", "c")
        )

        # AI category breakdown
        category_breakdown = dict(
            qs.filter(ai_category__isnull=False).values_list("ai_category").annotate(
                c=Count("id"),
            ).values_list("ai_category", "c")
        )

        # Average sentiment score
        avg_sentiment = qs.filter(
            sentiment_score__isnull=False,
        ).aggregate(avg=Avg("sentiment_score"))["avg"]

        return Response({
            "total": total,
            "open": open_tickets,
            "resolved_today": resolved_today,
            "escalated": escalated,
            "unassigned": unassigned,
            "priority_breakdown": {
                "low": priority_breakdown.get(SupportTicket.PRIORITY_LOW, 0),
                "medium": priority_breakdown.get(SupportTicket.PRIORITY_MEDIUM, 0),
                "high": priority_breakdown.get(SupportTicket.PRIORITY_HIGH, 0),
                "urgent": priority_breakdown.get(SupportTicket.PRIORITY_URGENT, 0),
            },
            "sentiment_breakdown": sentiment_breakdown,
            "category_breakdown": category_breakdown,
            "avg_sentiment_score": round(avg_sentiment, 3) if avg_sentiment else None,
        })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Job Verification Views
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class VerificationListCreateView(generics.ListCreateAPIView):
    """
    GET  — list verifications (QA Inspector / Platform Admin see all,
           Service Pro sees own).
    POST — Service Pro uploads post-job media → dispatches to CF Worker.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return JobVerificationUploadSerializer
        return JobVerificationListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = JobVerification.objects.filter(is_active=True).select_related(
            "booking", "service_pro", "reviewed_by",
        )

        from apps.users.models import User
        staff_roles = {
            User.ROLE_QA_INSPECTOR,
            User.ROLE_SUPPORT_ARCHITECT,
            User.ROLE_PLATFORM_ADMIN,
        }
        if user.role not in staff_roles:
            qs = qs.filter(service_pro=user)

        # Status filter
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=int(status_filter))

        return qs

    def perform_create(self, serializer):
        verification = serializer.save()
        # Dispatch to CF Worker for vision analysis
        dispatch_verification_to_worker(verification)


class VerificationDetailView(generics.RetrieveAPIView):
    """GET — verification detail with full AI analysis."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = JobVerificationDetailSerializer
    lookup_field = "uuid"

    def get_queryset(self):
        return JobVerification.objects.filter(is_active=True).select_related(
            "booking", "service_pro", "reviewed_by",
        )


class VerificationReviewView(APIView):
    """POST — QA Inspector manual review override."""

    permission_classes = [
        permissions.IsAuthenticated,
        IsQAInspector | IsPlatformAdmin,
    ]

    def post(self, request, uuid):
        try:
            verification = JobVerification.objects.get(uuid=uuid, is_active=True)
        except JobVerification.DoesNotExist:
            return Response(
                {"detail": "Verification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        ser = JobVerificationReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        verification.status = ser.validated_data["status"]
        verification.reviewer_notes = ser.validated_data.get("reviewer_notes", "")
        verification.reviewed_by = request.user
        verification.reviewed_at = timezone.now()
        verification.save(update_fields=[
            "status", "reviewer_notes", "reviewed_by", "reviewed_at", "updated",
        ])

        return Response(
            {
                "detail": f"Verification #{verification.pk} {'approved' if verification.status == JobVerification.STATUS_APPROVED else 'rejected'}.",
                "verification": JobVerificationDetailSerializer(verification).data,
            },
            status=status.HTTP_200_OK,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AI Triage Webhook (called by CF Worker)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TriageWebhookView(APIView):
    """
    POST — CF Worker calls back with sentiment analysis,
    AI summary, suggested response, category, and priority.
    Authenticated via CLEANABLE_API_KEY header.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Validate API key
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {getattr(settings, 'CLOUDFLARE_WORKER_API_KEY', '')}"
        if not auth or auth != expected:
            return Response(
                {"detail": "Unauthorized."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ser = TicketAITriageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            ticket = SupportTicket.objects.get(pk=data["ticket_id"], is_active=True)
        except SupportTicket.DoesNotExist:
            return Response(
                {"detail": "Ticket not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        ticket.sentiment = data["sentiment"]
        ticket.sentiment_score = data["sentiment_score"]
        ticket.priority = data["priority"]
        ticket.ai_category = data["ai_category"]
        ticket.ai_summary = data["ai_summary"]
        ticket.ai_suggested_response = data["ai_suggested_response"]
        ticket.ai_triaged_at = timezone.now()
        ticket.save(update_fields=[
            "sentiment", "sentiment_score", "priority",
            "ai_category", "ai_summary", "ai_suggested_response",
            "ai_triaged_at", "updated",
        ])

        return Response({"detail": "Triage data saved.", "ticket_id": ticket.pk})


class VerifyWebhookView(APIView):
    """
    POST — CF Worker calls back with vision analysis results.
    Authenticated via CLEANABLE_API_KEY header.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Validate API key
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {getattr(settings, 'CLOUDFLARE_WORKER_API_KEY', '')}"
        if not auth or auth != expected:
            return Response(
                {"detail": "Unauthorized."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        data = request.data
        verification_id = data.get("verification_id")

        try:
            verification = JobVerification.objects.get(pk=verification_id, is_active=True)
        except JobVerification.DoesNotExist:
            return Response(
                {"detail": "Verification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        cleanliness_score = float(data.get("cleanliness_score", 0))
        verification.cleanliness_score = cleanliness_score
        verification.ai_analysis = data.get("ai_analysis", {})
        verification.ai_summary = data.get("ai_summary", "")
        verification.issues_detected = data.get("issues_detected", [])
        verification.analyzed_at = timezone.now()

        # Auto-approve/flag/manual review based on thresholds
        if cleanliness_score >= JobVerification.AUTO_APPROVE_THRESHOLD:
            verification.status = JobVerification.STATUS_APPROVED
        elif cleanliness_score >= JobVerification.FLAG_THRESHOLD:
            verification.status = JobVerification.STATUS_FLAGGED
        else:
            verification.status = JobVerification.STATUS_MANUAL_REVIEW

        verification.save(update_fields=[
            "cleanliness_score", "ai_analysis", "ai_summary",
            "issues_detected", "analyzed_at", "status", "updated",
        ])

        return Response({
            "detail": "Verification analysis saved.",
            "verification_id": verification.pk,
            "status": verification.get_status_display(),
        })
