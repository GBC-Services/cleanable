from django.db import models
from utils.models import BaseModel, BaseDictModel
from clients.models import Place
from companies.models import Company, CompanyServiceFee
from services.models import CleaningType, Service, ServiceFee
import datetime
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib.auth import get_user_model
UserModel = get_user_model()


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
        (STATUS_NOT_ASSIGNED, "Not assigned"),
        (STATUS_NOT_STARTED, "Assigned, Not started"),
        (STATUS_CLEANER_IS_ON_THE_WAY, "Cleaner is on the way"),
        (STATUS_STARTED, "Started"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_NOT_COMPLETED, "Not completed. Issue Reported"),
        (STATUS_CANCELLED_BY_COMPANY, "Cancelled by company"),
        (STATUS_CANCELLED_BY_SERVICE, "Cancelled by service"),
        (STATUS_CANCELLED_BY_CLIENT, "Cancelled by client"),
    )

    """It can be a few cleaning for one booking if cleaning needs to be remade due to complain"""
    booking = models.ForeignKey("bookings.Booking", blank=True, default=None, on_delete=models.CASCADE)

    """A company can be retrieved from service as well"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    status = models.PositiveIntegerField(choices=STATUSES, default=STATUS_NOT_ASSIGNED)

    """It is also here (not only on a booking),
     because many cleanings can be assigned to one booking due to re-doing something."""
    scheduled_date = models.DateField(blank=True, null=True, default=None)
    scheduled_start_dt = models.DateTimeField(blank=True, null=True, default=None)
    scheduled_end_dt = models.DateTimeField(blank=True, null=True, default=None)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_fields = {}
        for field in ["status"]:
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
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("cleaning", kwargs=dict(uuid=self.uuid))

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
        date = datetime.datetime.strftime(self.scheduled_start_dt, '%m/%d/%Y')
        time_from = datetime.datetime.strftime(self.scheduled_start_dt, '%H:%M:%S')
        time_to = datetime.datetime.strftime(self.scheduled_end_dt, '%H:%M:%S')
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

    def get_status_changings(self):
        return self.cleaningstatuschange_set.all().order_by("-id")


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
