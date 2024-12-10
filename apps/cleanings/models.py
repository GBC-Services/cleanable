from django.db import models
from apps.utils.models import BaseModel, BaseDictModel
from apps.utils.stripe_utils import StripeUtils
from apps.companies.models import Company, CompanyServiceFee
import datetime
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib.sites.models import Site
from django.core.validators import MinValueValidator, MaxValueValidator
from icalendar import Calendar, Event

from django.contrib.auth import get_user_model
UserModel = get_user_model()

from django.conf import settings
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class FeedbackTagForCleaner(BaseDictModel):
    pass


class FeedbackTagForClient(BaseDictModel):
    pass


class Cleaning(BaseModel):
    """Combination of booking and a company"""
    """ToDo: A global question: rating for a cleaning or for a booking?"""
    STATUS_NOT_ASSIGNED = 10
    STATUS_NOT_STARTED = 20
    STATUS_CLEANER_IS_ON_THE_WAY = 30
    STATUS_STARTED = 40
    STATUS_COMPLETED = 50
    STATUS_NOT_COMPLETED = 60
    STATUS_CANCELLED_BY_COMPANY = 70
    STATUS_CANCELLED_BY_SERVICE = 80
    STATUS_CANCELLED_BY_CLIENT = 90

    STATUSES = (
        (STATUS_NOT_ASSIGNED, "Waiting for cleaner assignment"),
        (STATUS_NOT_STARTED, "Assigned, Not started"),
        (STATUS_CLEANER_IS_ON_THE_WAY, "Cleaner is on the way"),
        (STATUS_STARTED, "Started"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_NOT_COMPLETED, "Not completed. Issue Reported"),
        (STATUS_CANCELLED_BY_COMPANY, "Cancelled by company"),
        (STATUS_CANCELLED_BY_SERVICE, "Cancelled by service"),
        (STATUS_CANCELLED_BY_CLIENT, "Cancelled by client"),
    )

    PAYMENT_STATUS_NOT_PAID = 10
    PAYMENT_STATUS_PARTIALLY_PAID = 20
    PAYMENT_STATUS_FULLY_PAID = 30
    PAYMENT_STATUSES = (
        (PAYMENT_STATUS_NOT_PAID, "Not paid"),
        (PAYMENT_STATUS_PARTIALLY_PAID, "Partially paid"),
        (PAYMENT_STATUS_FULLY_PAID, "Paid")
    )

    """It can be a few cleaning for one booking, if cleaning needs to be remade due to complain"""
    booking = models.ForeignKey("bookings.Booking", blank=True, default=None, on_delete=models.CASCADE)

    """A company can be retrieved from service as well"""
    company = models.ForeignKey(Company, blank=True, null=True, default=None, on_delete=models.CASCADE)
    status = models.PositiveIntegerField(choices=STATUSES, default=STATUS_NOT_ASSIGNED)
    payment_status = models.PositiveIntegerField(choices=PAYMENT_STATUSES, default=PAYMENT_STATUS_NOT_PAID)

    """It is also here (not only on a booking),
     because many cleanings can be assigned to one booking due to re-doing something."""
    scheduled_date = models.DateField(blank=True, null=True, default=None)
    scheduled_start_dt = models.DateTimeField(blank=True, null=True, default=None)
    scheduled_end_dt = models.DateTimeField(blank=True, null=True, default=None)

    """This is needed for regular cleaning bookings to calculate the next day of the cleaning to cope with the cases,
    when some cleaning might be postponed to another date due to some circumstances, but the initial schedule 
    should be followed anyway: initially_scheduled_date"""
    initially_scheduled_date = models.DateField(blank=True, null=True, default=None)

    real_start_dt = models.DateTimeField(blank=True, null=True, default=None)
    real_end_dt = models.DateTimeField(blank=True, null=True, default=None)
    start_coordinates_dt = models.DateTimeField(blank=True, null=True, default=None)
    start_coordinates = models.CharField(max_length=128, blank=True, null=True, default=None)
    is_start_match_cleaning_location = models.BooleanField(blank=True, null=True, default=None)
    end_coordinates_dt = models.DateTimeField(blank=True, null=True, default=None)
    end_coordinates = models.CharField(max_length=128, blank=True, null=True, default=None)
    is_end_match_cleaning_location = models.BooleanField(blank=True, null=True, default=None)

    client_comments = models.TextField(blank=True, null=True, default=None)
    cleaner_comments = models.TextField(blank=True, null=True, default=None)
    manager_comments = models.TextField(blank=True, null=True, default=None)

    score_for_cleaner = models.PositiveIntegerField(blank=True, null=True, default=None,
                                                    validators=[MinValueValidator(1), MaxValueValidator(5)])
    feedback_for_cleaner = models.TextField(blank=True, null=True, default=None)
    feedback_tags_for_cleaner = models.ManyToManyField(FeedbackTagForCleaner, blank=True, default=None)

    score_for_client = models.PositiveIntegerField(blank=True, null=True, default=None,
                                                   validators=[MinValueValidator(1), MaxValueValidator(5)])
    feedback_for_client = models.TextField(blank=True, null=True, default=None)
    feedback_tags_for_client = models.ManyToManyField(FeedbackTagForClient, blank=True, default=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_fields = {}
        for field in ["status", "scheduled_start_dt", "company", "payment_status"]:
            try:
                field_name = field
                val = getattr(self, field_name)
                self._original_fields[field_name] = val
            except Exception as e:
                pass

    def save(self, *args, **kwargs):
        if not self.scheduled_date:
            self.scheduled_date = self.booking.scheduled_date
            self.scheduled_start_dt = self.booking.scheduled_start_dt
            self.scheduled_end_dt = self.booking.scheduled_end_dt

        if self.status != self._original_fields["status"]:
            if self.status == self.STATUS_STARTED:
                self.real_start_dt = timezone.now()
            if self.status == self.STATUS_COMPLETED:
                self.real_end_dt = timezone.now()

        if not self.pk:
            self.initially_scheduled_date = self.scheduled_date
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("cleaning", kwargs=dict(uuid=self.uuid))

    def get_title(self):
        return f"Cleaning for {self.scheduled_date} {self.scheduled_start_dt.time()}"

    def get_cleaners(self):
        return self.cleanerforcleaning_set.all()

    def get_cleaners_as_text(self):
        cleaners = self.get_cleaners().values("cleaner__first_name", "cleaner__last_name")
        cleaners_list = list()
        for cleaner in cleaners:
            cleaners_list.append(f"{cleaner['cleaner__first_name']} {cleaner['cleaner__last_name']}")
        return ", ".join(cleaners_list)

    def assign_cleaner(self, cleaner):
        CleanerForCleaning.objects.get_or_create(cleaning=self, cleaner=cleaner)
        if self.status == self.STATUS_NOT_ASSIGNED:
            self.status = self.STATUS_NOT_STARTED
            self.save(force_update=True)
        return True

    def get_scheduled_dt_range(self):
        date = datetime.datetime.strftime(self.scheduled_start_dt, '%m/%d/%Y') if self.scheduled_start_dt else ""
        time_from = datetime.datetime.strftime(self.scheduled_start_dt, '%H:%M:%S') if self.scheduled_start_dt else ""
        time_to = datetime.datetime.strftime(self.scheduled_end_dt, '%H:%M:%S') if self.scheduled_end_dt else ""
        scheduled_dt_range = f"{date}, {time_from}-{time_to}"
        return scheduled_dt_range

    def set_next_status(self):
        status_index_to_select = None
        for index, status in enumerate(self.STATUSES):
            status_code, _ = status
            if status_index_to_select is None:
                if status_code == self.status:
                    status_index_to_select = index + 1
            else:
                self.set_status(status_code)
                break
        return True

    def set_status(self, status_code):
        self.status = status_code
        self.save(force_update=True)
        return True

    def save_coordinates(self, coordinates):
        """Think more about anti-exploit logic here"""
        if self.status == self.STATUS_NOT_STARTED:
            self.start_coordinates_dt = timezone.now()
            self.start_coordinates = coordinates
            self.save(force_update=True)
        if self.status == self.STATUS_STARTED:
            self.end_coordinates_dt = timezone.now()
            self.end_coordinates = coordinates
            self.save(force_update=True)
        return True

    def save_chat_message(self, user, message):
        return CleaningChatMessage.objects.create(cleaning=self, user=user, text=message)

    def get_messages(self):
        return self.cleaningchatmessage_set.all().order_by("id")

    def get_status_changes(self):
        return self.cleaningstatuschange_set.all().order_by("-id")

    def create_invoice(self):
        stripe_id = StripeUtils().create_invoice(self.booking, self.scheduled_start_dt)
        CleaningInvoice.objects.create(cleaning=self, stripe_id=stripe_id)
        return True

    def create_initial_paid_invoice(self, stripe_email, stripe_customer_id):
        CleaningInvoice.objects.create(cleaning=self, is_paid=True, is_main=True,
                                       stripe_email=stripe_email, stripe_customer_id=stripe_customer_id,
                                       stripe_invoice_url=self.booking.get_stripe_invoice_url())
        self.payment_status = self.PAYMENT_STATUS_FULLY_PAID
        self.save(force_update=True)
        return True

    def get_invoices(self):
        return self.cleaninginvoice_set.filter(is_active=True)

    def get_main_invoice(self):
        invoice = self.get_invoices().filter(is_main=True).last()
        if invoice:
            return invoice
        else:
            return None

    def get_payment_status(self):
        return f"{self.get_payment_status_display}"

    def get_invoice_url(self):
        invoice = self.get_main_invoice()
        if invoice:
            return invoice.get_invoice_url()
        else:
            return None

    def get_data_for_calendar(self):
        cal = Calendar()
        site = Site.objects.get_current()
    
        cal.add('prodid', f'-//{site.name} Events Calendar//{site.domain}//')
        cal.add('version', '2.0')

        ical_event = Event()
        ical_event.add('summary', self.get_title())
        ical_event.add('dtstart', self.scheduled_start_dt)
        ical_event.add('dtend', self.scheduled_end_dt)
        ical_event['uid'] = f"{self.uuid}"
        cal.add_component(ical_event)
        return cal

    def get_google_calendar_link(self):
        dt_start = self.scheduled_start_dt.isoformat().replace("+", "").replace(":", "").replace("-", "")
        dt_end = self.scheduled_end_dt.isoformat().replace("+", "").replace(":", "").replace("-", "")
        details = f"{self.booking.get_service_names_as_string()}"
        location = f"{self.booking.place.get_full_address()}"
        url = f"https://www.google.com/calendar/event?action=TEMPLATE&text={self.get_title()}" \
              f"&dates={dt_start}/{dt_end}&details={details}&location={location}"
        return url


class SpecialCleaningRequest(BaseModel):
    STATUS_NEW = 10
    STATUS_ACCEPTED = 20
    STATUS_CANCELLED_BY_COMPANY = 40
    STATUS_CANCELLED_BY_SERVICE = 50

    STATUSES = (
        (STATUS_NEW, "New"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_CANCELLED_BY_COMPANY, "Cancelled by Company"),
        (STATUS_CANCELLED_BY_SERVICE, "Cancelled by Service"),
    )

    booking = models.ForeignKey("bookings.Booking", blank=True, null=True, default=None, on_delete=models.CASCADE)
    cleaning = models.ForeignKey(Cleaning, blank=True, null=True, default=None, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True, default=None)
    status = models.PositiveIntegerField(choices=STATUSES, blank=True, null=True, default=STATUS_NEW)
    fee = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=None)
    comments = models.TextField(blank=True, null=True, default=None)

    def set_status(self, status):
        self.status = status
        self.save(force_update=True)
        return True


class CleaningInvoice(BaseModel):
    cleaning = models.ForeignKey(Cleaning, on_delete=models.CASCADE)

    stripe_email = models.EmailField(blank=True, null=True, default=None)
    stripe_customer_id = models.CharField(max_length=64, blank=True, null=True, default=None)

    stripe_id = models.CharField(max_length=64, blank=True, null=True, default=None)
    stripe_invoice_url = models.URLField(blank=True, null=True, default=None)

    is_main = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False)

    def check_if_is_paid_now(self):
        if not self.is_paid:
            stripe_invoice = stripe.Invoice.retrieve(self.stripe_id)
            if stripe_invoice["status"] == "paid":
                self.is_paid = True
                self.save(force_update=True)
                return True
        return self.is_paid

    def get_invoice_url(self):
        if self.stripe_invoice_url:
            stripe_invoice_url = self.stripe_invoice_url
        else:
            if self.stripe_id:
                stripe_invoice = stripe.Invoice.retrieve(self.stripe_id)
                stripe_invoice_url = stripe_invoice["hosted_invoice_url"]
                self.stripe_invoice_url = stripe_invoice_url
                self.save(force_update=True)
            else:
                return None
        return stripe_invoice_url


class CleaningStatusChange(BaseModel):
    cleaning = models.ForeignKey(Cleaning, on_delete=models.CASCADE)
    status = models.PositiveIntegerField(choices=Cleaning.STATUSES)


class CleanerForCleaning(BaseModel):
    """If more than 1 cleaner per cleaning (for doing faster bigger amount of work)"""
    cleaning = models.ForeignKey(Cleaning, on_delete=models.CASCADE)
    cleaner = models.ForeignKey(UserModel, blank=True, default=None, on_delete=models.CASCADE)


class CleaningChatMessage(BaseModel):
    cleaning = models.ForeignKey(Cleaning, on_delete=models.CASCADE)
    user = models.ForeignKey(UserModel, blank=True, default=None, on_delete=models.CASCADE)
    text = models.TextField()
