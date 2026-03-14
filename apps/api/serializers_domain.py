"""
Domain Serializers
==================

Read-only and CRUD serializers for the core business models:
Locations, Services, Places, Companies, Bookings, Cleanings.

These expose the existing Django models through the REST API.
"""

from decimal import Decimal
from rest_framework import serializers

from apps.bookings.models import (
    Booking, BookingService, BookingStatusChange, DiscountCode,
)
from apps.cleanings.models import Cleaning, CleaningInvoice
from apps.clients.models import Place
from apps.companies.models import Company, CompanyServiceFee
from apps.locations.models import (
    City, Country, Region, RegionZipCode, State, ZipCode,
)
from apps.services.models import (
    ApartmentPlan, CleaningType, Service, ServiceFee, ServiceFeesSnapshot,
)
from apps.users.models import User
# Wallet models are imported lazily inside serializers to avoid circular imports
# They are loaded from apps.api.models_wallet


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Location Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name", "slug")


class StateSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = State
        fields = ("id", "name", "slug", "country", "country_name")


class CitySerializer(serializers.ModelSerializer):
    state_name = serializers.CharField(source="state.name", read_only=True)

    class Meta:
        model = City
        fields = ("id", "name", "slug", "state", "state_name")


class ZipCodeSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True, default="")

    class Meta:
        model = ZipCode
        fields = ("id", "value", "city", "city_name")


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ("id", "name", "slug", "profit_rate")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Service Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ApartmentPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApartmentPlan
        fields = ("id", "name", "slug")


class CleaningTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CleaningType
        fields = ("id", "name", "slug")


class ServiceSerializer(serializers.ModelSerializer):
    apartment_plan_name = serializers.CharField(
        source="apartment_plan.name", read_only=True, default="",
    )
    cleaning_type_name = serializers.CharField(
        source="cleaning_type.name", read_only=True, default="",
    )
    regularity_type_display = serializers.CharField(
        source="get_regularity_type_display", read_only=True,
    )

    class Meta:
        model = Service
        fields = (
            "id", "uuid", "name", "slug", "description",
            "apartment_plan", "apartment_plan_name",
            "cleaning_type", "cleaning_type_name",
            "regularity_type", "regularity_type_display",
            "is_area_based_fee", "is_chore", "checklist",
        )


class ServiceFeeSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    service_uuid = serializers.UUIDField(source="service.uuid", read_only=True)
    is_area_based = serializers.BooleanField(
        source="service.is_area_based_fee", read_only=True,
    )

    class Meta:
        model = ServiceFee
        fields = (
            "id", "service", "service_name", "service_uuid",
            "client_fee", "is_area_based",
        )


class ServiceFeesSnapshotSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True, default="")
    fees = ServiceFeeSerializer(source="servicefee_set", many=True, read_only=True)

    class Meta:
        model = ServiceFeesSnapshot
        fields = ("id", "uuid", "region", "region_name", "fees", "created")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Place Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PlaceListSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    full_address = serializers.CharField(source="get_full_address", read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True, default="")

    class Meta:
        model = Place
        fields = (
            "id", "uuid", "name", "type", "type_display",
            "address", "apartment_nmb", "full_address",
            "bedrooms_nmb", "bathrooms_nmb", "area_size",
            "region", "region_name",
            "city", "state", "zip_code",
        )


class PlaceDetailSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    full_address = serializers.CharField(source="get_full_address", read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True, default="")
    city_name = serializers.CharField(source="city.name", read_only=True, default="")
    state_name = serializers.CharField(source="state.name", read_only=True, default="")
    zip_code_value = serializers.CharField(source="zip_code.value", read_only=True, default="")
    google_maps_url = serializers.CharField(source="get_google_maps_url", read_only=True)

    class Meta:
        model = Place
        fields = (
            "id", "uuid", "name", "type", "type_display",
            "address", "apartment_nmb", "full_address",
            "bedrooms_nmb", "bathrooms_nmb", "area_size",
            "region", "region_name",
            "city", "city_name", "state", "state_name",
            "zip_code", "zip_code_value",
            "feature", "comments",
            "google_maps_url",
            "created", "updated",
        )


class PlaceCreateSerializer(serializers.ModelSerializer):
    """Used by Residents to create or update their places."""

    class Meta:
        model = Place
        fields = (
            "type", "address", "apartment_nmb",
            "bedrooms_nmb", "bathrooms_nmb", "area_size",
            "city", "state", "zip_code",
            "feature", "comments",
        )

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["client"] = request.user
        return super().create(validated_data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Company Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CompanyListSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True, default="")

    class Meta:
        model = Company
        fields = (
            "id", "uuid", "name", "slug", "phone",
            "region", "region_name",
            "logo_small", "logo_xsmall",
        )


class CompanyDetailSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True, default="")
    has_fees_accepted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Company
        fields = (
            "id", "uuid", "name", "slug", "phone", "description",
            "region", "region_name",
            "logo", "logo_small", "logo_xsmall",
            "e_signed_contract_url", "has_fees_accepted",
            "created", "updated",
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Booking Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class BookingServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    service_uuid = serializers.UUIDField(source="service.uuid", read_only=True)

    class Meta:
        model = BookingService
        fields = (
            "id", "service", "service_name", "service_uuid",
            "service_fee", "fee", "company_fee",
        )
        read_only_fields = ("id", "fee", "company_fee")


class DiscountCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscountCode
        fields = ("id", "code", "value", "is_percentage")


class BookingListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True,
    )
    place_address = serializers.CharField(
        source="place.get_full_address", read_only=True, default="",
    )
    service_names = serializers.CharField(
        source="get_service_names_as_string", read_only=True,
    )
    scheduled_range = serializers.CharField(
        source="get_scheduled_dt_range", read_only=True,
    )

    class Meta:
        model = Booking
        fields = (
            "id", "uuid", "short_id",
            "status", "status_display",
            "payment_status", "payment_status_display",
            "place", "place_address",
            "scheduled_date", "scheduled_range",
            "service_names",
            "total_fee", "discount_amount", "total_fee_final",
            "regularity_type",
            "created",
        )


class BookingDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True,
    )
    place_detail = PlaceListSerializer(source="place", read_only=True)
    services = BookingServiceSerializer(
        source="bookingservice_set", many=True, read_only=True,
    )
    client_email = serializers.EmailField(source="client.email", read_only=True, default="")
    next_cleaning = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            "id", "uuid", "short_id",
            "status", "status_display",
            "payment_status", "payment_status_display",
            "client", "client_email",
            "place", "place_detail", "place_type",
            "bedrooms_nmb", "bathrooms_nmb", "area_size",
            "scheduled_date", "scheduled_start_dt", "scheduled_end_dt",
            "regularity_type", "regularity_option",
            "comments", "special_request",
            "services",
            "total_fee", "discount_amount", "total_fee_final",
            "tip_amount", "is_tip_paid",
            "total_costs", "profit",
            "stripe_payment_intent_id",
            "next_cleaning",
            "created", "updated",
        )

    def get_next_cleaning(self, obj):
        cleaning = obj.get_next_cleaning()
        if cleaning:
            return {
                "id": cleaning.id,
                "uuid": str(cleaning.uuid),
                "status": cleaning.status,
                "status_display": cleaning.get_status_display(),
                "scheduled_date": cleaning.scheduled_date,
            }
        return None


class BookingCreateSerializer(serializers.Serializer):
    """
    Creates a booking with service fee calculation.

    Flow:
      1. Resident selects a place and services
      2. We look up the current ServiceFeesSnapshot for the place's region
      3. Calculate total fees, create BookingService rows
      4. Create Stripe PaymentIntent
      5. Return client_secret for frontend Stripe Elements
    """

    place_id = serializers.IntegerField()
    service_fee_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1,
    )
    scheduled_date = serializers.DateField()
    scheduled_start_time = serializers.TimeField()
    scheduled_end_time = serializers.TimeField()
    regularity_type = serializers.ChoiceField(
        choices=Service.REGULARITY_TYPES,
        default=Service.REGULARITY_TYPE_ONE_TIME,
    )
    regularity_option = serializers.ChoiceField(
        choices=Booking.REGULARITIES, required=False, allow_null=True,
    )
    comments = serializers.CharField(required=False, allow_blank=True, default="")
    special_request = serializers.CharField(required=False, allow_blank=True, default="")
    discount_code = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_place_id(self, value):
        request = self.context["request"]
        try:
            place = Place.objects.get(id=value, client=request.user, is_active=True)
        except Place.DoesNotExist:
            raise serializers.ValidationError("Place not found or does not belong to you.")
        return value

    def validate_service_fee_ids(self, value):
        fees = ServiceFee.objects.filter(id__in=value, is_active=True)
        if fees.count() != len(value):
            raise serializers.ValidationError("One or more service fees are invalid.")
        return value

    def validate(self, attrs):
        import datetime
        start = datetime.datetime.combine(attrs["scheduled_date"], attrs["scheduled_start_time"])
        end = datetime.datetime.combine(attrs["scheduled_date"], attrs["scheduled_end_time"])
        if end <= start:
            raise serializers.ValidationError(
                {"scheduled_end_time": "End time must be after start time."}
            )
        if attrs.get("regularity_type") == Service.REGULARITY_TYPE_REGULAR:
            if not attrs.get("regularity_option"):
                raise serializers.ValidationError(
                    {"regularity_option": "Required for regular bookings."}
                )
        return attrs


class BookingModifySerializer(serializers.Serializer):
    """Modify an existing booking (reschedule, update services)."""

    scheduled_date = serializers.DateField(required=False)
    scheduled_start_time = serializers.TimeField(required=False)
    scheduled_end_time = serializers.TimeField(required=False)
    comments = serializers.CharField(required=False, allow_blank=True)
    special_request = serializers.CharField(required=False, allow_blank=True)


class BookingCancelSerializer(serializers.Serializer):
    """Cancel a booking with optional reason."""

    reason = serializers.CharField(required=False, allow_blank=True, default="")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Cleaning Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CleaningListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    booking_uuid = serializers.UUIDField(source="booking.uuid", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True, default="")

    class Meta:
        model = Cleaning
        fields = (
            "id", "uuid", "booking_uuid",
            "company", "company_name",
            "status", "status_display",
            "scheduled_date", "scheduled_start_dt", "scheduled_end_dt",
            "score_for_cleaner",
            "created",
        )


class CleaningDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    booking_uuid = serializers.UUIDField(source="booking.uuid", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True, default="")
    cleaners = serializers.CharField(source="get_cleaners_as_text", read_only=True)

    class Meta:
        model = Cleaning
        fields = (
            "id", "uuid", "booking_uuid",
            "company", "company_name",
            "status", "status_display",
            "scheduled_date", "scheduled_start_dt", "scheduled_end_dt",
            "real_start_dt", "real_end_dt",
            "start_coordinates", "end_coordinates",
            "cleaners",
            "score_for_cleaner", "feedback_for_cleaner",
            "score_for_client", "feedback_for_client",
            "is_delayed",
            "created", "updated",
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Digital Wallet Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class DigitalWalletSerializer(serializers.Serializer):
    """Read-only summary of a Service Pro's wallet balances."""

    id = serializers.IntegerField(read_only=True)
    available_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True,
    )
    pending_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True,
    )
    lifetime_earnings = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    stripe_account_id = serializers.CharField(read_only=True, allow_null=True)
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)


class WalletTransactionSerializer(serializers.Serializer):
    """Read-only wallet ledger entry."""

    id = serializers.IntegerField(read_only=True)
    transaction_type = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True,
    )
    description = serializers.CharField(read_only=True)
    reference_id = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    booking_id = serializers.IntegerField(
        source="booking.id", read_only=True, allow_null=True, default=None,
    )
    created = serializers.DateTimeField(read_only=True)


class PayoutRequestSerializer(serializers.Serializer):
    """
    Create: supply ``amount`` (Decimal).
    Read: all fields.
    """

    id = serializers.IntegerField(read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.CharField(read_only=True)
    stripe_payout_id = serializers.CharField(
        read_only=True, allow_null=True, default=None,
    )
    requested_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(
        read_only=True, allow_null=True, default=None,
    )
    failure_reason = serializers.CharField(
        read_only=True, allow_null=True, default=None,
    )

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class WalletDashboardSerializer(serializers.Serializer):
    """
    Combined wallet dashboard: balance + recent transactions + pending payouts.
    """

    wallet = serializers.SerializerMethodField()
    recent_transactions = serializers.SerializerMethodField()
    pending_payouts = serializers.SerializerMethodField()

    def get_wallet(self, obj):
        return DigitalWalletSerializer(obj).data

    def get_recent_transactions(self, obj):
        txns = obj.transactions.all().order_by("-created")[:10]
        return WalletTransactionSerializer(txns, many=True).data

    def get_pending_payouts(self, obj):
        from apps.api.models_wallet import PayoutRequest
        requests = obj.payout_requests.filter(
            status__in=[
                PayoutRequest.STATUS_PENDING,
                PayoutRequest.STATUS_PROCESSING,
            ]
        ).order_by("-requested_at")
        return PayoutRequestSerializer(requests, many=True).data
