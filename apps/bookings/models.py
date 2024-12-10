from django.db import models
from apps.utils.models import BaseModel, BaseDictModel
from apps.clients.models import Place
from apps.companies.models import CompanyServiceFee
from apps.services.models import Service, ServiceFee
from apps.users.models import User, UserSession
from apps.locations.models import ZipCode
from apps.cleanings.models import Cleaning
from apps.locations.models import Region
from django.urls import reverse
from django.conf import settings
from django.db.models import Sum
from django.db import transaction
import datetime
import urllib.parse
import stripe
from django.utils import timezone

stripe.api_key = settings.STRIPE_SECRET_KEY


class DiscountCode(BaseModel):
    region = models.ForeignKey(Region, blank=True, null=True, default=None, on_delete=models.SET_NULL)
    code = models.CharField(max_length=24, blank=True, null=True, default=None)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_percentage = models.BooleanField(default=False)
    comments = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        return f"{self.code}"


class BookingZipCodeSearch(BaseModel):
    user_session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    zip_code = models.ForeignKey(ZipCode, on_delete=models.CASCADE)


class Booking(BaseModel):
    STATUS_NEW = 10
    STATUS_IN_WORK = 20
    STATUS_COMPLETED = 30
    STATUS_CANCELLED_BY_COMPANY = 40
    STATUS_CANCELLED_BY_SERVICE = 50
    STATUS_CANCELLED_BY_CLIENT = 60

    STATUSES = (
        (STATUS_NEW, "New"),
        (STATUS_IN_WORK, "In work"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED_BY_COMPANY, "Cancelled by Company"),
        (STATUS_CANCELLED_BY_SERVICE, "Cancelled by Service"),
        (STATUS_CANCELLED_BY_CLIENT, "Cancelled by client"),
    )

    REGULARITY_WEEKLY = 10
    REGULARITY_BI_WEEKLY = 20
    REGULARITY_MONTHLY = 30
    REGULARITIES = (
        (REGULARITY_WEEKLY, "Weekly"),
        (REGULARITY_BI_WEEKLY, "Bi-weekly"),
        (REGULARITY_MONTHLY, "Monthly")
    )

    PAYMENT_STATUS_NOT_PAID = 10
    PAYMENT_STATUS_PARTIALLY_PAID = 20
    PAYMENT_STATUS_FULLY_PAID = 30
    PAYMENT_STATUSES = (
        (PAYMENT_STATUS_NOT_PAID, "Not paid"),
        (PAYMENT_STATUS_PARTIALLY_PAID, "Partially paid"),
        (PAYMENT_STATUS_FULLY_PAID, "Paid")
    )

    status = models.PositiveIntegerField(choices=STATUSES, default=10)
    payment_status = models.PositiveIntegerField(choices=PAYMENT_STATUSES, default=PAYMENT_STATUS_NOT_PAID)
    regularity_type = models.PositiveIntegerField(choices=Service.REGULARITY_TYPES,
                                                  default=Service.REGULARITY_TYPE_ONE_TIME)
    regularity_option = models.PositiveIntegerField(choices=REGULARITIES, blank=True, null=True, default=None)

    # client can be retrieved from place as well
    client = models.ForeignKey(User, blank=True, null=True, default=None, on_delete=models.CASCADE)
    user_session = models.ForeignKey(UserSession, blank=True, null=True, default=None, on_delete=models.CASCADE)

    place = models.ForeignKey(Place, blank=True, null=True, default=None, on_delete=models.CASCADE)
    place_type = models.PositiveIntegerField(choices=Place.PLACE_TYPES, default=Place.PLACE_TYPE_APARTMENT)

    """Duplicating here information from place, because it can be changed there 
    by the user at any moment, but it sustainability is crucial for consistency 
    of data (correctness of booking fee) checking at any moment in the future."""
    bedrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    bathrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    area_size = models.PositiveIntegerField(blank=True, null=True, default=None)

    scheduled_date = models.DateField(blank=True, null=True, default=None)
    scheduled_start_dt = models.DateTimeField(blank=True, null=True, default=None)
    scheduled_end_dt = models.DateTimeField(blank=True, null=True, default=None)
    comments = models.TextField(blank=True, null=True, default=None)

    preferred_cleaners = models.ManyToManyField(User, blank=True, default=None,
                                                related_name="booking_preferred_cleaners")
    special_request = models.TextField(blank=True, null=True, default=None)

    total_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_code = models.ForeignKey(DiscountCode, blank=True, null=True, default=None, on_delete=models.CASCADE)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_fee_final = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    stripe_payment_intent_id = models.CharField(max_length=64, blank=True, null=True, default=None)
    stripe_email = models.EmailField(blank=True, null=True, default=None)
    stripe_customer_id = models.CharField(max_length=64, blank=True, null=True, default=None)

    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stripe_tip_payment_intent_id = models.CharField(max_length=64, blank=True, null=True, default=None)
    is_tip_paid = models.BooleanField(default=False)

    total_costs = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # The fields below were moved here from cleaning
    client_comments = models.TextField(blank=True, null=True, default=None)
    cleaner_comments = models.TextField(blank=True, null=True, default=None)
    manager_comments = models.TextField(blank=True, null=True, default=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_fields = {}
        for field in ["status", "discount_code"]:
            try:
                field_name = field
                val = getattr(self, field_name)
                self._original_fields[field_name] = val
            except Exception as e:
                pass

    def __str__(self):
        scheduled_date = self.scheduled_date.strftime('%m/%d/%Y') if self.scheduled_date else ""
        if self.place:
            address = self.place.get_full_address()
            if address:
                return f"{scheduled_date}, {address}, {self.total_fee_final} USD"
            else:
                return f"{scheduled_date}, {self.total_fee_final} USD"
        else:
            return f"{scheduled_date}, {self.total_fee_final} USD"

    def save(self, *args, **kwargs):
        if self.place and self.place_type == Place.PLACE_TYPE_HOUSE and not self.area_size:
            self.area_size = self.place.area_size

        if self.place and not self.place_type:
            self.place_type = self.place.type

        if self.discount_code:
            if self.discount_code.is_percentage:
                self.discount_amount = float(self.discount_code.value)/100 * float(self.total_fee)
            else:
                self.discount_amount = self.discount_code.value
        total_fee_final = float(self.total_fee) - float(self.discount_amount)
        self.total_fee_final = total_fee_final if total_fee_final > 0 else 0
        self.profit = self.total_fee_final - float(self.total_costs)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("booking", kwargs=dict(uuid=self.uuid))

    def create_cleaning(self, company=None):
        from apps.cleanings.models import Cleaning
        is_one_time_cleaning = self.get_is_one_time()
        with transaction.atomic():
            """Prevent creating another cleaning for on time cleaning booking, 
            if a cleaning already exists."""
            if is_one_time_cleaning and Cleaning.objects.filter(booking=self, status__lte=Cleaning.STATUS_NOT_COMPLETED)\
                    .exists():
                return True

            kwargs = dict(booking=self, company=company)
            last_cleaning = self.get_last_cleaning()
            if is_one_time_cleaning or (not is_one_time_cleaning and not last_cleaning):
                Cleaning.objects.create(**kwargs)
            else:
                kwargs["company"] = last_cleaning.company
                days_nmb = self.get_days_nmb_between_cleanings()
                scheduled_date = last_cleaning.scheduled_date + datetime.timedelta(days=days_nmb)
                kwargs["scheduled_date"] = scheduled_date
                kwargs["scheduled_start_dt"] = datetime.datetime.combine(scheduled_date, self.scheduled_start_dt.time())
                kwargs["scheduled_end_dt"] = datetime.datetime.combine(scheduled_date, self.scheduled_end_dt.time())
                Cleaning.objects.get_or_create(**kwargs)
            self.save(force_update=True)

            return True

    def send_special_request_for_cleaning(self, company):
        from apps.cleanings.models import SpecialCleaningRequest
        SpecialCleaningRequest.objects.get_or_create(booking=self, company=company, description=self.special_request)
        return True

    def get_cleanings(self):
        return self.cleaning_set.all().order_by("-id")

    def is_active_cleaning(self):
        return self.get_active_cleanings().exists()

    def get_active_cleanings(self):
        return self.get_cleanings().filter(status__lte=Cleaning.STATUS_NOT_COMPLETED)

    def get_booking_services(self, as_service_fee=False):
        services = self.bookingservice_set.filter(is_active=True)
        if as_service_fee:
            service_fee_ids = services.values_list("service_fee_id")
            return ServiceFee.objects.filter(id__in=service_fee_ids)
        else:
            return services

    def get_service_names(self):
        services = self.get_booking_services()
        return services.values_list("service__name", flat=True)

    def get_service_names_as_string(self):
        return ", ".join(self.get_service_names())

    def update_services(self, service_fees):
        if self.status == self.STATUS_NEW:
            with transaction.atomic():
                booking_services_ids = list()
                for service_fee in service_fees.iterator():
                    if service_fee.service.is_area_based_fee:
                        fee = float(service_fee.client_fee) * float(self.area_size)
                    else:
                        fee = service_fee.client_fee
                    booking_service, _ = BookingService.objects\
                        .update_or_create(booking=self, service=service_fee.service,
                                          defaults=dict(is_active=True, service_fee=service_fee, fee=fee))
                    booking_services_ids.append(booking_service.id)
                self.bookingservice_set.exclude(id__in=booking_services_ids).update(is_active=False)
                self.total_fee = self.recalculate_fees()
                self.save(force_update=True)
                return True
        return False

    def recalculate_fees(self):
        fees = self.get_booking_services().aggregate(fees=Sum("fee"))["fees"]
        return fees

    def cancel(self):
        self.status = self.STATUS_CANCELLED_BY_CLIENT
        self.save(force_update=True)
        return True

    def get_scheduled_dt_range(self):
        scheduled_dt_range = ""
        if self.scheduled_start_dt:
            date = datetime.datetime.strftime(self.scheduled_start_dt, '%m/%d/%Y')
            time_from = datetime.datetime.strftime(self.scheduled_start_dt, '%H:%M:%S')
            time_to = datetime.datetime.strftime(self.scheduled_end_dt, '%H:%M:%S')
            scheduled_dt_range = f"{date}, {time_from}-{time_to}"
        return scheduled_dt_range

    def get_status_notification_class(self):
        return "alert-success" if self.status <= self.STATUS_COMPLETED else "alert-secondary"

    def get_last_cleaning(self):
        return self.cleaning_set.last()

    def get_last_completed_cleaning(self):
        return self.cleaning_set.filter(status=Cleaning.STATUS_COMPLETED)

    def get_successful_payment_url(self):
        return reverse("successful_payment", kwargs=dict(uuid=self.uuid))

    def get_stripe_invoice_url(self):
        """Showing invoice for the very first payment after creating a booking."""
        invoice_url = ""
        if self.stripe_payment_intent_id:
            payment_intent = stripe.PaymentIntent.retrieve(self.stripe_payment_intent_id)
            charge_id = payment_intent["latest_charge"]
            if charge_id:
                charge = stripe.Charge.retrieve(charge_id)
                invoice_url = charge["receipt_url"]
        return invoice_url

    def apply_discount_code(self, discount_code):
        discount_code = DiscountCode.objects.filter(is_active=True, code=discount_code).last()
        if discount_code:
            self.discount_code = discount_code
            self.save(force_update=True)
        return True

    def mark_paid(self, payment_intent):
        """Adding a payment information to the cleaning if there is only one cleaning in the booking"""
        stripe_email = payment_intent["receipt_email"]
        stripe_customer_id = payment_intent["customer"]

        self.stripe_payment_intent_id = payment_intent["id"]
        self.stripe_email = stripe_email
        self.stripe_customer_id = stripe_customer_id
        self.save(force_update=True)

        cleanings = self.get_cleanings()
        if self.get_cleanings().count() == 1:
            cleaning = cleanings.last()
            if not cleaning.get_invoices():
                cleaning.create_initial_paid_invoice(stripe_email=stripe_email,
                                                     stripe_customer_id=stripe_customer_id)

    def get_encoded_stripe_email(self):
        return urllib.parse.quote(self.stripe_email)

    def get_payment_status(self):
        return "Paid" if self.is_paid else "Waiting for payment"

    def get_is_regular(self):
        return self.regularity_type == Service.REGULARITY_TYPE_REGULAR

    def get_is_one_time(self):
        return self.regularity_type == Service.REGULARITY_TYPE_ONE_TIME

    def get_days_nmb_between_cleanings(self):
        days_nmb = None
        if self.regularity_option == self.REGULARITY_WEEKLY:
            days_nmb = 7
        elif self.regularity_option == self.REGULARITY_BI_WEEKLY:
            days_nmb = 14
        elif self.regularity_option == self.REGULARITY_MONTHLY:
            days_nmb = 28  # 4 weeks?
        return days_nmb

    def get_next_cleaning(self):
        return self.get_cleanings().filter(scheduled_start_dt__gt=timezone.now()).order_by("scheduled_start_dt").first()


class BookingStatusChange(BaseModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    status = models.PositiveIntegerField(choices=Booking.STATUSES)


class BookingService(BaseModel):
    """Since cleaning can be made even for an add-on only, all cleaning related service will be in ths model"""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)

    # for easier accessibility via backward querysets
    service = models.ForeignKey(Service, on_delete=models.CASCADE)

    """Charges from a client"""
    # main service fee by a website, charged from the client
    service_fee = models.ForeignKey(ServiceFee, blank=True, null=True, default=None, on_delete=models.CASCADE)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    """Payout to a sub-contractor"""
    # a reference to a service fee instance from a subcontractor
    company_service_fee = models.ForeignKey(CompanyServiceFee, blank=True, null=True, default=None, on_delete=models.CASCADE)
    # a service fee, paid to the sub-contractor
    company_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    comments = models.TextField(blank=True, null=True, default=None)


class BookingChatMessage(BaseModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    user = models.ForeignKey(User, blank=True, default=None, on_delete=models.CASCADE)
    text = models.TextField()