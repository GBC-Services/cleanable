"""
Payroll & Fiscal Auditing API Views
=====================================

Endpoints:
  Activity Statements   — list / detail (auto-generated after job completion)
  Payroll Cycles        — list / detail / close cycle / trigger payout / CSV export
  Tax Documents         — CRUD for agency compliance files (W-9 / 1099)
  Payment Holds         — Fiscal Auditor place / release / escalate overrides
  Dashboard Stats       — aggregated KPIs for the Fiscal Auditor dashboard
"""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User

from .models import (
    ActivityStatement,
    PayrollCycle,
    TaxDocument,
    PaymentHold,
)
from .serializers import (
    ActivityStatementSerializer,
    PayrollCycleListSerializer,
    PayrollCycleDetailSerializer,
    TaxDocumentSerializer,
    TaxDocumentUploadSerializer,
    TaxDocumentReviewSerializer,
    PaymentHoldSerializer,
    PaymentHoldCreateSerializer,
    PaymentHoldReleaseSerializer,
)


# ── Permissions ───────────────────────────────────────────────────────

def _is_fiscal_auditor(user):
    return user.role == User.ROLE_FISCAL_AUDITOR


def _is_agency_owner(user):
    return user.role == User.ROLE_AGENCY_OWNER


def _is_platform_admin(user):
    return user.role == User.ROLE_PLATFORM_ADMIN


def _is_fiscal_or_admin(user):
    return _is_fiscal_auditor(user) or _is_platform_admin(user)


# ══════════════════════════════════════════════════════════════════════
#  Activity Statements
# ══════════════════════════════════════════════════════════════════════

class ActivityStatementListView(APIView):
    """
    GET  /api/v1/payroll/statements/
    Query params: ?agency=<id>&service_pro=<id>&from=YYYY-MM-DD&to=YYYY-MM-DD
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = ActivityStatement.objects.filter(is_active=True)

        # Scope by role
        if _is_agency_owner(user) and user.company_id:
            qs = qs.filter(agency_id=user.company_id)
        elif not _is_fiscal_or_admin(user):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Filters
        agency = request.query_params.get("agency")
        if agency and _is_fiscal_or_admin(user):
            qs = qs.filter(agency_id=agency)

        pro = request.query_params.get("service_pro")
        if pro:
            qs = qs.filter(service_pro_id=pro)

        date_from = request.query_params.get("from")
        if date_from:
            qs = qs.filter(completed_at__date__gte=date_from)

        date_to = request.query_params.get("to")
        if date_to:
            qs = qs.filter(completed_at__date__lte=date_to)

        qs = qs.select_related("agency", "service_pro", "booking")[:200]
        serializer = ActivityStatementSerializer(qs, many=True)
        return Response(serializer.data)


class ActivityStatementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        try:
            stmt = ActivityStatement.objects.select_related(
                "agency", "service_pro", "booking", "cleaning",
            ).get(uuid=uuid, is_active=True)
        except ActivityStatement.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        if _is_agency_owner(user) and user.company_id != stmt.agency_id:
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not (_is_fiscal_or_admin(user) or _is_agency_owner(user)):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ActivityStatementSerializer(stmt)
        return Response(serializer.data)


# ══════════════════════════════════════════════════════════════════════
#  Payroll Cycles
# ══════════════════════════════════════════════════════════════════════

class PayrollCycleListView(APIView):
    """
    GET  /api/v1/payroll/cycles/
    Query params: ?agency=<id>&status=open|processing|paid|held
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = PayrollCycle.objects.filter(is_active=True)

        if _is_agency_owner(user) and user.company_id:
            qs = qs.filter(agency_id=user.company_id)
        elif not _is_fiscal_or_admin(user):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        agency = request.query_params.get("agency")
        if agency and _is_fiscal_or_admin(user):
            qs = qs.filter(agency_id=agency)

        cycle_status = request.query_params.get("status")
        if cycle_status:
            qs = qs.filter(status=cycle_status)

        qs = qs.select_related("agency")[:100]
        serializer = PayrollCycleListSerializer(qs, many=True)
        return Response(serializer.data)


class PayrollCycleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        try:
            cycle = PayrollCycle.objects.select_related("agency").prefetch_related(
                "line_items__service_pro",
                "line_items__agency",
                "line_items__booking",
                "holds__placed_by",
                "holds__released_by",
            ).get(uuid=uuid, is_active=True)
        except PayrollCycle.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        if _is_agency_owner(user) and user.company_id != cycle.agency_id:
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not (_is_fiscal_or_admin(user) or _is_agency_owner(user)):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PayrollCycleDetailSerializer(cycle)
        return Response(serializer.data)


class PayrollCycleCloseView(APIView):
    """
    POST /api/v1/payroll/cycles/<uuid>/close/
    Closes the cycle: aggregates totals, generates CSV, moves to 'processing'.
    Only Fiscal Auditor / Platform Admin.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        if not _is_fiscal_or_admin(request.user):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            cycle = PayrollCycle.objects.get(uuid=uuid, is_active=True)
        except PayrollCycle.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        if cycle.status != PayrollCycle.STATUS_OPEN:
            return Response(
                {"detail": f"Cycle is already '{cycle.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Aggregate line items
            items = cycle.line_items.filter(is_active=True)
            agg = items.aggregate(
                jobs=Count("id"),
                client=Sum("client_charged"),
                agency=Sum("agency_fee"),
                pro=Sum("pro_wage"),
                platform=Sum("platform_fee"),
                tips=Sum("tip_amount"),
            )
            cycle.total_jobs = agg["jobs"] or 0
            cycle.total_client_charged = agg["client"] or Decimal("0.00")
            cycle.total_agency_fees = agg["agency"] or Decimal("0.00")
            cycle.total_pro_wages = agg["pro"] or Decimal("0.00")
            cycle.total_platform_fees = agg["platform"] or Decimal("0.00")
            cycle.total_tips = agg["tips"] or Decimal("0.00")

            # Generate CSV
            csv_content = self._generate_csv(cycle, items)
            filename = (
                f"job_summary_{cycle.agency.name or cycle.agency_id}_"
                f"{cycle.period_start}_{cycle.period_end}.csv"
            )
            cycle.csv_file.save(filename, ContentFile(csv_content.encode("utf-8")))

            cycle.status = PayrollCycle.STATUS_PROCESSING
            cycle.save()

        serializer = PayrollCycleDetailSerializer(cycle)
        return Response(serializer.data)

    @staticmethod
    def _generate_csv(cycle, items):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Statement UUID",
            "Booking Short ID",
            "Service Pro",
            "Service Pro Email",
            "Services",
            "Scheduled Date",
            "Completed At",
            "Client Charged",
            "Agency Fee",
            "Pro Wage",
            "Platform Fee",
            "Tip",
        ])
        for item in items.select_related("service_pro", "booking"):
            writer.writerow([
                str(item.uuid),
                item.booking.short_id if item.booking else "",
                item.service_pro.get_full_name() if item.service_pro else "",
                item.service_pro.email if item.service_pro else "",
                item.service_names,
                str(item.scheduled_date or ""),
                str(item.completed_at or ""),
                str(item.client_charged),
                str(item.agency_fee),
                str(item.pro_wage),
                str(item.platform_fee),
                str(item.tip_amount),
            ])
        writer.writerow([])
        writer.writerow(["TOTALS", "", "", "", "", "", "",
                         str(cycle.total_client_charged),
                         str(cycle.total_agency_fees),
                         str(cycle.total_pro_wages),
                         str(cycle.total_platform_fees),
                         str(cycle.total_tips)])
        return buf.getvalue()


class PayrollCycleCSVDownloadView(APIView):
    """
    GET /api/v1/payroll/cycles/<uuid>/csv/
    Returns the generated CSV file.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        try:
            cycle = PayrollCycle.objects.get(uuid=uuid, is_active=True)
        except PayrollCycle.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        if _is_agency_owner(user) and user.company_id != cycle.agency_id:
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not (_is_fiscal_or_admin(user) or _is_agency_owner(user)):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not cycle.csv_file:
            return Response(
                {"detail": "CSV not yet generated. Close the cycle first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response = HttpResponse(
            cycle.csv_file.read(), content_type="text/csv",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="job_summary_{cycle.period_start}_{cycle.period_end}.csv"'
        )
        return response


class PayrollCyclePayoutView(APIView):
    """
    POST /api/v1/payroll/cycles/<uuid>/payout/
    Triggers Stripe Connect transfer to the agency.
    Only Fiscal Auditor / Platform Admin.  Blocked if active hold exists.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        if not _is_fiscal_or_admin(request.user):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            cycle = PayrollCycle.objects.select_related("agency").get(
                uuid=uuid, is_active=True,
            )
        except PayrollCycle.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        if cycle.status != PayrollCycle.STATUS_PROCESSING:
            return Response(
                {"detail": f"Cycle must be 'processing', currently '{cycle.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for active holds
        if cycle.holds.filter(status=PaymentHold.STATUS_ACTIVE).exists():
            return Response(
                {"detail": "Cannot payout — active payment hold exists."},
                status=status.HTTP_409_CONFLICT,
            )

        # Check agency has Stripe Connect account
        agency = cycle.agency
        if not agency.stripe_account_id:
            return Response(
                {"detail": "Agency does not have a Stripe Connect account configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Trigger Stripe Connect transfer
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY

            amount_cents = int(cycle.total_agency_fees * 100)
            if amount_cents <= 0:
                return Response(
                    {"detail": "Payout amount must be positive."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            transfer = stripe.Transfer.create(
                amount=amount_cents,
                currency="usd",
                destination=agency.stripe_account_id,
                description=(
                    f"Cleanable payroll {cycle.period_start}–{cycle.period_end}"
                ),
                metadata={
                    "payroll_cycle_uuid": str(cycle.uuid),
                    "agency_id": str(agency.id),
                },
            )

            cycle.stripe_transfer_id = transfer.id
            cycle.paid_at = timezone.now()
            cycle.status = PayrollCycle.STATUS_PAID
            cycle.save()

            return Response(PayrollCycleListSerializer(cycle).data)

        except Exception as e:
            return Response(
                {"detail": f"Stripe transfer failed: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )


# ══════════════════════════════════════════════════════════════════════
#  Tax Documents
# ══════════════════════════════════════════════════════════════════════

class TaxDocumentListView(APIView):
    """
    GET   /api/v1/payroll/tax-documents/
    POST  /api/v1/payroll/tax-documents/   (upload, agency owner only)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = TaxDocument.objects.filter(is_active=True)

        if _is_agency_owner(user) and user.company_id:
            qs = qs.filter(agency_id=user.company_id)
        elif not _is_fiscal_or_admin(user):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        agency = request.query_params.get("agency")
        if agency and _is_fiscal_or_admin(user):
            qs = qs.filter(agency_id=agency)

        doc_type = request.query_params.get("type")
        if doc_type:
            qs = qs.filter(document_type=doc_type)

        year = request.query_params.get("year")
        if year:
            qs = qs.filter(tax_year=year)

        qs = qs.select_related("agency", "uploaded_by", "reviewed_by")[:100]
        serializer = TaxDocumentSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        if not _is_agency_owner(user) or not user.company_id:
            return Response(
                {"detail": "Only Agency Owners can upload tax documents."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = TaxDocumentUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        doc = TaxDocument.objects.create(
            agency_id=user.company_id,
            uploaded_by=user,
            document_type=data["document_type"],
            file=data["file"],
            original_filename=data["file"].name,
            tax_year=data["tax_year"],
            notes=data.get("notes", ""),
        )

        return Response(
            TaxDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )


class TaxDocumentReviewView(APIView):
    """
    POST /api/v1/payroll/tax-documents/<uuid>/review/
    Fiscal Auditor / Platform Admin approves or rejects.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        if not _is_fiscal_or_admin(request.user):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            doc = TaxDocument.objects.get(uuid=uuid, is_active=True)
        except TaxDocument.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        ser = TaxDocumentReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        doc.status = data["status"]
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        if data.get("notes"):
            doc.notes = data["notes"]
        doc.save()

        return Response(TaxDocumentSerializer(doc).data)


class TaxDocumentDeleteView(APIView):
    """
    DELETE /api/v1/payroll/tax-documents/<uuid>/
    Soft-delete. Agency Owner (own docs) or Fiscal Auditor.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, uuid):
        try:
            doc = TaxDocument.objects.get(uuid=uuid, is_active=True)
        except TaxDocument.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        if _is_agency_owner(user) and user.company_id == doc.agency_id:
            pass  # allowed
        elif _is_fiscal_or_admin(user):
            pass  # allowed
        else:
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        doc.is_active = False
        doc.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════════════
#  Payment Holds
# ══════════════════════════════════════════════════════════════════════

class PaymentHoldCreateView(APIView):
    """
    POST /api/v1/payroll/cycles/<cycle_uuid>/hold/
    Fiscal Auditor places a hold and moves cycle to 'held'.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, cycle_uuid):
        if not _is_fiscal_auditor(request.user):
            return Response(
                {"detail": "Only Fiscal Auditors can place holds."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            cycle = PayrollCycle.objects.get(uuid=cycle_uuid, is_active=True)
        except PayrollCycle.DoesNotExist:
            return Response(
                {"detail": "Cycle not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if cycle.status == PayrollCycle.STATUS_PAID:
            return Response(
                {"detail": "Cannot hold — cycle already paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = PaymentHoldCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        with transaction.atomic():
            hold = PaymentHold.objects.create(
                payroll_cycle=cycle,
                placed_by=request.user,
                reason=ser.validated_data["reason"],
            )
            cycle.status = PayrollCycle.STATUS_HELD
            cycle.save()

        return Response(
            PaymentHoldSerializer(hold).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentHoldReleaseView(APIView):
    """
    POST /api/v1/payroll/holds/<uuid>/release/
    Releases a hold.  If no other active holds, cycle returns to 'processing'.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        if not _is_fiscal_or_admin(request.user):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            hold = PaymentHold.objects.select_related("payroll_cycle").get(
                uuid=uuid, is_active=True,
            )
        except PaymentHold.DoesNotExist:
            return Response(
                {"detail": "Hold not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if hold.status != PaymentHold.STATUS_ACTIVE:
            return Response(
                {"detail": f"Hold is already '{hold.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = PaymentHoldReleaseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        with transaction.atomic():
            hold.status = PaymentHold.STATUS_RELEASED
            hold.released_by = request.user
            hold.released_at = timezone.now()
            hold.release_notes = ser.validated_data.get("release_notes", "")
            hold.save()

            # If no more active holds, return cycle to processing
            cycle = hold.payroll_cycle
            remaining_holds = cycle.holds.filter(
                status=PaymentHold.STATUS_ACTIVE,
            ).count()
            if remaining_holds == 0 and cycle.status == PayrollCycle.STATUS_HELD:
                cycle.status = PayrollCycle.STATUS_PROCESSING
                cycle.save()

        return Response(PaymentHoldSerializer(hold).data)


# ══════════════════════════════════════════════════════════════════════
#  Fiscal Auditor Dashboard Stats
# ══════════════════════════════════════════════════════════════════════

class FiscalDashboardStatsView(APIView):
    """
    GET /api/v1/payroll/stats/
    Aggregated KPIs for the Fiscal Auditor dashboard.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_fiscal_or_admin(request.user):
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # Cycle stats
        cycles = PayrollCycle.objects.filter(is_active=True)
        open_cycles = cycles.filter(status=PayrollCycle.STATUS_OPEN).count()
        processing_cycles = cycles.filter(status=PayrollCycle.STATUS_PROCESSING).count()
        held_cycles = cycles.filter(status=PayrollCycle.STATUS_HELD).count()
        paid_this_month = cycles.filter(
            status=PayrollCycle.STATUS_PAID,
            paid_at__gte=thirty_days_ago,
        ).aggregate(total=Sum("total_agency_fees"))["total"] or Decimal("0.00")

        # Statement stats
        recent_statements = ActivityStatement.objects.filter(
            is_active=True, completed_at__gte=thirty_days_ago,
        )
        stmt_agg = recent_statements.aggregate(
            count=Count("id"),
            total_revenue=Sum("client_charged"),
            total_agency_fees=Sum("agency_fee"),
            total_pro_wages=Sum("pro_wage"),
            total_platform_fees=Sum("platform_fee"),
        )

        # Active holds
        active_holds = PaymentHold.objects.filter(
            is_active=True, status=PaymentHold.STATUS_ACTIVE,
        ).count()

        # Pending tax docs
        pending_tax_docs = TaxDocument.objects.filter(
            is_active=True, status=TaxDocument.STATUS_PENDING,
        ).count()

        return Response({
            "open_cycles": open_cycles,
            "processing_cycles": processing_cycles,
            "held_cycles": held_cycles,
            "paid_this_month": str(paid_this_month),
            "active_holds": active_holds,
            "pending_tax_docs": pending_tax_docs,
            "statements_30d": stmt_agg["count"] or 0,
            "revenue_30d": str(stmt_agg["total_revenue"] or Decimal("0.00")),
            "agency_fees_30d": str(stmt_agg["total_agency_fees"] or Decimal("0.00")),
            "pro_wages_30d": str(stmt_agg["total_pro_wages"] or Decimal("0.00")),
            "platform_fees_30d": str(stmt_agg["total_platform_fees"] or Decimal("0.00")),
        })
