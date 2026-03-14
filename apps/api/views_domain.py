"""
Domain Views
============

ViewSets for the core business domain:
  - LocationViewSet   — read-only geography hierarchy
  - ServiceViewSet    — read-only services catalogue
  - PlaceViewSet      — CRUD for Resident's places
  - CompanyViewSet    — read-only company listing
  - BookingViewSet    — full booking lifecycle
  - CleaningViewSet   — read-only cleaning records
  - WalletViewSet     — Service Pro digital wallet
  - StripeWebhookView — unauthenticated webhook receiver

All write endpoints are protected by RBAC via the permission classes in
``apps.api.permissions``.
"""

import datetime
import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking, BookingService, BookingStatusChange
from apps.cleanings.models import Cleaning
from apps.clients.models import Place
from apps.companies.models import Company
from apps.locations.models import City, Country, Region, RegionZipCode, State, ZipCode
from apps.services.models import ApartmentPlan, CleaningType, Service, ServiceFee

from .permissions import (
    IsAgencyOwner,
    IsOwnerOrAdmin,
    IsPlatformAdmin,
    IsResident,
    IsServicePro,
    IsStaff,
    ReadOnly,
)
from .serializers_domain import (
    ApartmentPlanSerializer,
    BookingCancelSerializer,
    BookingCreateSerializer,
    BookingDetailSerializer,
    BookingListSerializer,
    BookingModifySerializer,
    CitySerializer,
    CleaningDetailSerializer,
    CleaningListSerializer,
    CleaningTypeSerializer,
    CompanyDetailSerializer,
    CompanyListSerializer,
    CountrySerializer,
    DigitalWalletSerializer,
    PayoutRequestSerializer,
    PlaceCreateSerializer,
    PlaceDetailSerializer,
    PlaceListSerializer,
    RegionSerializer,
    ServiceFeeSerializer,
    ServiceSerializer,
    StateSerializer,
    WalletDashboardSerializer,
    WalletTransactionSerializer,
    ZipCodeSerializer,
)

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Pagination
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LocationViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class LocationViewSet(viewsets.ViewSet):
    """
    Read-only geography endpoints.

    GET /locations/countries/
    GET /locations/states/?country=<id>
    GET /locations/cities/?state=<id>
    GET /locations/zip-codes/?city=<id>
    GET /locations/regions/
    """

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="countries")
    def countries(self, request):
        qs = Country.objects.filter(is_active=True).order_by("name")
        return Response(CountrySerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="states")
    def states(self, request):
        qs = State.objects.filter(is_active=True)
        country_id = request.query_params.get("country")
        if country_id:
            qs = qs.filter(country_id=country_id)
        return Response(StateSerializer(qs.order_by("name"), many=True).data)

    @action(detail=False, methods=["get"], url_path="cities")
    def cities(self, request):
        qs = City.objects.filter(is_active=True)
        state_id = request.query_params.get("state")
        if state_id:
            qs = qs.filter(state_id=state_id)
        return Response(CitySerializer(qs.order_by("name"), many=True).data)

    @action(detail=False, methods=["get"], url_path="zip-codes")
    def zip_codes(self, request):
        qs = ZipCode.objects.all()
        city_id = request.query_params.get("city")
        if city_id:
            qs = qs.filter(city_id=city_id)
        return Response(ZipCodeSerializer(qs.order_by("value"), many=True).data)

    @action(detail=False, methods=["get"], url_path="regions")
    def regions(self, request):
        qs = Region.objects.filter(is_active=True).order_by("name")
        return Response(RegionSerializer(qs, many=True).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ServiceViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ServiceViewSet(viewsets.ViewSet):
    """
    Read-only services catalogue.

    GET /services/list/
    GET /services/fees/?region=<id>
    GET /services/apartment-plans/
    GET /services/cleaning-types/
    """

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="list")
    def list_services(self, request):
        qs = Service.objects.filter(is_active=True).order_by("id")
        return Response(ServiceSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="fees")
    def fees(self, request):
        qs = ServiceFee.objects.filter(is_active=True).select_related("service")
        region_id = request.query_params.get("region")
        if region_id:
            qs = qs.filter(snapshot__region_id=region_id)
        return Response(ServiceFeeSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="apartment-plans")
    def apartment_plans(self, request):
        qs = ApartmentPlan.objects.filter(is_active=True).order_by("name")
        return Response(ApartmentPlanSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="cleaning-types")
    def cleaning_types(self, request):
        qs = CleaningType.objects.filter(is_active=True).order_by("name")
        return Response(CleaningTypeSerializer(qs, many=True).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PlaceViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PlaceViewSet(viewsets.ViewSet):
    """
    CRUD for Resident's places.

    GET    /places/          — list
    POST   /places/          — create
    GET    /places/{id}/     — retrieve
    PATCH  /places/{id}/     — update
    """

    permission_classes = [permissions.IsAuthenticated, IsResident | IsPlatformAdmin]

    def list(self, request):
        qs = Place.objects.filter(
            client=request.user, is_active=True
        ).order_by("-id")
        return Response(PlaceListSerializer(qs, many=True).data)

    def create(self, request):
        serializer = PlaceCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        place = serializer.save()
        return Response(
            PlaceDetailSerializer(place).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        try:
            place = Place.objects.get(
                pk=pk, client=request.user, is_active=True
            )
        except Place.DoesNotExist:
            return Response(
                {"detail": "Place not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(PlaceDetailSerializer(place).data)

    def partial_update(self, request, pk=None):
        try:
            place = Place.objects.get(
                pk=pk, client=request.user, is_active=True
            )
        except Place.DoesNotExist:
            return Response(
                {"detail": "Place not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = PlaceCreateSerializer(
            place, data=request.data, partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        place = serializer.save()
        return Response(PlaceDetailSerializer(place).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CompanyViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve companies.  Write access is admin-only via the
    Django admin or separate internal endpoints.

    GET /companies/
    GET /companies/{id}/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Company.objects.filter(is_active=True).order_by("name")
        region_id = self.request.query_params.get("region")
        if region_id:
            qs = qs.filter(region_id=region_id)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CompanyDetailSerializer
        return CompanyListSerializer


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BookingViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class BookingViewSet(viewsets.ViewSet):
    """
    Full booking lifecycle.

    GET    /bookings/              — list (scoped by role)
    POST   /bookings/              — create + Stripe PaymentIntent
    GET    /bookings/{id}/         — retrieve
    POST   /bookings/{id}/cancel/  — cancel
    PATCH  /bookings/{id}/modify/  — reschedule / update comments
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsResident | IsAgencyOwner | IsStaff,
    ]
    pagination_class = StandardPagination

    # ── helpers ──────────────────────────────────────────────────────

    def _get_booking_for_user(self, request, pk):
        """Retrieve a booking scoped to the requesting user's role."""
        from apps.users.models import User

        qs = Booking.objects.filter(pk=pk, is_active=True)
        user = request.user

        if user.role == User.ROLE_RESIDENT:
            qs = qs.filter(client=user)
        elif user.role == User.ROLE_AGENCY_OWNER:
            qs = qs.filter(
                cleaning__company=user.company
            ).distinct()
        # Staff / admin see all

        return qs.first()

    # ── list ─────────────────────────────────────────────────────────

    def list(self, request):
        from apps.users.models import User

        qs = Booking.objects.filter(is_active=True).order_by("-id")
        user = request.user

        if user.role == User.ROLE_RESIDENT:
            qs = qs.filter(client=user)
        elif user.role == User.ROLE_AGENCY_OWNER:
            qs = qs.filter(
                cleaning__company=user.company
            ).distinct()

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                BookingListSerializer(page, many=True).data
            )
        return Response(BookingListSerializer(qs, many=True).data)

    # ── retrieve ─────────────────────────────────────────────────────

    def retrieve(self, request, pk=None):
        booking = self._get_booking_for_user(request, pk)
        if not booking:
            return Response(
                {"detail": "Booking not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(BookingDetailSerializer(booking).data)

    # ── create ───────────────────────────────────────────────────────

    def create(self, request):
        """
        Create a booking with fee calculation and Stripe PaymentIntent.

        Flow:
          1. Validate via BookingCreateSerializer
          2. Look up Place → copy bedrooms/bathrooms/area_size
          3. Look up ServiceFee objects → calculate total_fee
          4. Apply discount code if provided
          5. Create Booking + BookingService rows (atomic)
          6. Create Stripe PaymentIntent
          7. Return BookingDetailSerializer data + client_secret
        """
        if not request.user.role == request.user.ROLE_RESIDENT:
            return Response(
                {"detail": "Only Residents can create bookings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BookingCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        place = Place.objects.get(
            id=data["place_id"], client=request.user, is_active=True
        )
        service_fees = ServiceFee.objects.filter(
            id__in=data["service_fee_ids"], is_active=True
        ).select_related("service")

        # ── Fee calculation ──────────────────────────────────────────
        total_fee = Decimal("0.00")
        booking_services_data = []

        area_size = place.area_size or 0

        for sf in service_fees:
            if sf.service.is_area_based_fee:
                fee = Decimal(str(sf.client_fee)) * Decimal(str(area_size))
            else:
                fee = Decimal(str(sf.client_fee))
            total_fee += fee
            booking_services_data.append(
                {"service_fee": sf, "service": sf.service, "fee": fee}
            )

        # ── Scheduled datetimes ──────────────────────────────────────
        scheduled_date = data["scheduled_date"]
        scheduled_start_dt = datetime.datetime.combine(
            scheduled_date, data["scheduled_start_time"]
        )
        scheduled_end_dt = datetime.datetime.combine(
            scheduled_date, data["scheduled_end_time"]
        )
        # Make timezone-aware
        tz = timezone.get_current_timezone()
        scheduled_start_dt = timezone.make_aware(scheduled_start_dt, tz)
        scheduled_end_dt = timezone.make_aware(scheduled_end_dt, tz)

        with transaction.atomic():
            booking = Booking.objects.create(
                client=request.user,
                place=place,
                place_type=place.type,
                bedrooms_nmb=place.bedrooms_nmb,
                bathrooms_nmb=place.bathrooms_nmb,
                area_size=place.area_size,
                scheduled_date=scheduled_date,
                scheduled_start_dt=scheduled_start_dt,
                scheduled_end_dt=scheduled_end_dt,
                regularity_type=data.get(
                    "regularity_type", Service.REGULARITY_TYPE_ONE_TIME
                ),
                regularity_option=data.get("regularity_option"),
                comments=data.get("comments", ""),
                special_request=data.get("special_request", ""),
                total_fee=total_fee,
                status=Booking.STATUS_NEW,
            )

            # BookingService rows
            for bs in booking_services_data:
                BookingService.objects.create(
                    booking=booking,
                    service=bs["service"],
                    service_fee=bs["service_fee"],
                    fee=bs["fee"],
                )

            # Apply discount
            discount_code_str = data.get("discount_code", "")
            if discount_code_str:
                booking.apply_discount_code(discount_code_str)
            else:
                # Trigger total_fee_final calculation
                booking.save(force_update=True)

            # BookingStatusChange
            BookingStatusChange.objects.create(
                booking=booking, status=Booking.STATUS_NEW
            )

        # ── Stripe PaymentIntent ─────────────────────────────────────
        amount_cents = int(float(booking.total_fee_final) * 100)
        if amount_cents < 50:
            amount_cents = 50  # Stripe minimum

        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                metadata={
                    "booking_uuid": str(booking.uuid),
                    "booking_id": str(booking.id),
                    "client_email": request.user.email,
                },
                description=f"Cleanable booking #{booking.short_id}",
                receipt_email=request.user.email,
            )
            booking.stripe_payment_intent_id = intent["id"]
            booking.save(update_fields=["stripe_payment_intent_id"])
            client_secret = intent["client_secret"]
        except stripe.error.StripeError as exc:
            logger.error(
                "Stripe PaymentIntent creation failed for booking %s: %s",
                booking.uuid, exc,
            )
            client_secret = None

        response_data = BookingDetailSerializer(booking).data
        response_data["client_secret"] = client_secret
        return Response(response_data, status=status.HTTP_201_CREATED)

    # ── cancel ───────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """
        POST /bookings/{id}/cancel/

        Cancellable statuses: STATUS_NEW, STATUS_IN_WORK.
        """
        booking = self._get_booking_for_user(request, pk)
        if not booking:
            return Response(
                {"detail": "Booking not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if booking.status not in (Booking.STATUS_NEW, Booking.STATUS_IN_WORK):
            return Response(
                {
                    "detail": (
                        "Only bookings in 'New' or 'In Work' status "
                        "can be cancelled."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BookingCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")

        with transaction.atomic():
            booking.status = Booking.STATUS_CANCELLED_BY_CLIENT
            booking.save(update_fields=["status"])

            BookingStatusChange.objects.create(
                booking=booking,
                status=Booking.STATUS_CANCELLED_BY_CLIENT,
            )

        # Cancel Stripe PaymentIntent if it exists
        if booking.stripe_payment_intent_id:
            try:
                stripe.PaymentIntent.cancel(
                    booking.stripe_payment_intent_id,
                    cancellation_reason="abandoned",
                )
            except stripe.error.InvalidRequestError as exc:
                # Already cancelled / consumed — log and continue
                logger.warning(
                    "Could not cancel PaymentIntent %s for booking %s: %s",
                    booking.stripe_payment_intent_id, booking.uuid, exc,
                )
            except stripe.error.StripeError as exc:
                logger.error(
                    "Stripe error cancelling PaymentIntent %s: %s",
                    booking.stripe_payment_intent_id, exc,
                )

        return Response(
            BookingDetailSerializer(booking).data,
            status=status.HTTP_200_OK,
        )

    # ── modify ───────────────────────────────────────────────────────

    @action(detail=True, methods=["patch"], url_path="modify")
    def modify(self, request, pk=None):
        """
        PATCH /bookings/{id}/modify/

        Only STATUS_NEW bookings can be modified.
        Allows: scheduled_date, scheduled_start_time, scheduled_end_time,
                comments, special_request.
        """
        booking = self._get_booking_for_user(request, pk)
        if not booking:
            return Response(
                {"detail": "Booking not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if booking.status != Booking.STATUS_NEW:
            return Response(
                {"detail": "Only 'New' bookings can be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BookingModifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        update_fields = []

        if "comments" in data:
            booking.comments = data["comments"]
            update_fields.append("comments")

        if "special_request" in data:
            booking.special_request = data["special_request"]
            update_fields.append("special_request")

        # Rebuild scheduled datetimes when date/time fields change
        new_date = data.get("scheduled_date", booking.scheduled_date)
        new_start = data.get(
            "scheduled_start_time",
            booking.scheduled_start_dt.time() if booking.scheduled_start_dt else None,
        )
        new_end = data.get(
            "scheduled_end_time",
            booking.scheduled_end_dt.time() if booking.scheduled_end_dt else None,
        )

        tz = timezone.get_current_timezone()

        if "scheduled_date" in data:
            booking.scheduled_date = new_date
            update_fields.append("scheduled_date")

        if "scheduled_start_time" in data and new_start:
            dt = datetime.datetime.combine(new_date, new_start)
            booking.scheduled_start_dt = timezone.make_aware(dt, tz)
            update_fields.append("scheduled_start_dt")

        if "scheduled_end_time" in data and new_end:
            dt = datetime.datetime.combine(new_date, new_end)
            booking.scheduled_end_dt = timezone.make_aware(dt, tz)
            update_fields.append("scheduled_end_dt")

        if update_fields:
            booking.save(update_fields=update_fields)

        return Response(BookingDetailSerializer(booking).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CleaningViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CleaningViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only cleaning records.

    Residents see cleanings for their own bookings.
    Agency Owners / Service Pros see cleanings for their company.
    Staff and admins see all.

    GET /cleanings/
    GET /cleanings/{id}/
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        from apps.users.models import User

        user = self.request.user
        qs = Cleaning.objects.filter(is_active=True).order_by("-id")

        if user.role == User.ROLE_RESIDENT:
            qs = qs.filter(booking__client=user)
        elif user.role in (User.ROLE_AGENCY_OWNER, User.ROLE_SERVICE_PRO):
            if user.company_id:
                qs = qs.filter(company=user.company)
            else:
                qs = qs.none()
        # QA, Support, Admin → all

        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CleaningDetailSerializer
        return CleaningListSerializer


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WalletViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class WalletViewSet(viewsets.ViewSet):
    """
    Digital wallet for Service Pros.

    GET  /wallet/              — dashboard (balance + recent transactions)
    POST /wallet/payout/       — request instant payout
    GET  /wallet/transactions/ — paginated transaction history
    """

    permission_classes = [permissions.IsAuthenticated, IsServicePro]

    def _get_or_create_wallet(self, user):
        from apps.api.models_wallet import DigitalWallet

        wallet, _ = DigitalWallet.objects.get_or_create(user=user)
        return wallet

    def list(self, request):
        """GET /wallet/ — dashboard."""
        wallet = self._get_or_create_wallet(request.user)
        return Response(WalletDashboardSerializer(wallet).data)

    @action(detail=False, methods=["post"], url_path="payout")
    def payout(self, request):
        """POST /wallet/payout/ — request payout."""
        from apps.api.models_wallet import (
            DigitalWallet,
            PayoutRequest,
            WalletTransaction,
        )
        from .stripe_connect import process_payout

        wallet = self._get_or_create_wallet(request.user)

        serializer = PayoutRequestSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        amount = Decimal(str(serializer.validated_data["amount"]))

        if amount > wallet.available_balance:
            return Response(
                {"detail": "Requested amount exceeds available balance."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount <= Decimal("0"):
            return Response(
                {"detail": "Payout amount must be greater than zero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            payout_request = PayoutRequest.objects.create(
                wallet=wallet,
                amount=amount,
                status=PayoutRequest.STATUS_PROCESSING,
            )
            wallet.available_balance -= amount
            wallet.save(update_fields=["available_balance"])

        stripe_payout = None
        try:
            stripe_payout = process_payout(request.user, amount)
            payout_request.stripe_payout_id = stripe_payout["id"]
            payout_request.status = PayoutRequest.STATUS_PROCESSING
            payout_request.save(
                update_fields=["stripe_payout_id", "status"]
            )
            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type=WalletTransaction.TYPE_PAYOUT,
                amount=amount,
                reference_id=stripe_payout["id"],
                status=WalletTransaction.STATUS_PENDING,
                description="Instant payout requested",
            )
        except Exception as exc:
            # Roll back the balance deduction
            with transaction.atomic():
                wallet.available_balance += amount
                wallet.save(update_fields=["available_balance"])
                payout_request.status = PayoutRequest.STATUS_FAILED
                payout_request.failure_reason = str(exc)
                payout_request.save(
                    update_fields=["status", "failure_reason"]
                )
            logger.error(
                "Payout failed for user %s: %s", request.user.email, exc
            )
            return Response(
                {"detail": f"Payout failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            PayoutRequestSerializer(payout_request).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="transactions")
    def transactions(self, request):
        """GET /wallet/transactions/ — paginated ledger."""
        wallet = self._get_or_create_wallet(request.user)
        qs = wallet.transactions.all().order_by("-created")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                WalletTransactionSerializer(page, many=True).data
            )
        return Response(WalletTransactionSerializer(qs, many=True).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  StripeWebhookView
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class StripeWebhookView(APIView):
    """
    POST /webhooks/stripe/

    No authentication required — validated via Stripe-Signature header.
    Must be registered *outside* of DRF's JWT middleware scope.
    """

    permission_classes = [permissions.AllowAny]
    # Disable CSRF for webhook endpoint
    authentication_classes = []

    def post(self, request):
        from .stripe_connect import handle_webhook

        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            result = handle_webhook(payload, sig_header)
            return Response(result, status=status.HTTP_200_OK)
        except stripe.error.SignatureVerificationError as exc:
            logger.warning("Stripe webhook signature verification failed: %s", exc)
            return Response(
                {"detail": "Invalid signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            logger.error("Stripe webhook configuration error: %s", exc)
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            logger.exception("Unexpected error processing Stripe webhook: %s", exc)
            return Response(
                {"detail": "Webhook processing error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
