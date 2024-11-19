from django.db import models
from apps.utils.models import BaseModel, BaseDictModel
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse, reverse_lazy
from django.conf import settings
from apps.companies.models import Company
from django.contrib.sites.models import Site
import datetime
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
UserModel = get_user_model()
import time
from django.db import transaction


class CompanyCleanerInvite(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    email = models.EmailField(unique=True)
    user = models.OneToOneField(UserModel, blank=True, null=True, default=None, on_delete=models.CASCADE)

    def get_invite_link(self):
        current_site = Site.objects.get_current()
        domain = current_site.domain
        url = f"{settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL}://{domain}{reverse('account_signup')}cleaner?invite_id={self.uuid}"
        return url


class SchedulePeriod(BaseModel):
    date_start = models.DateField()
    date_end = models.DateField()

    @staticmethod
    def get_or_create_period(next_week=False):
        """Creating an object for the given period if it does not exist"""
        dt = timezone.now()
        """6 - because week days counting starts from 0"""
        current_week_end_date = (dt + timedelta(days=6 - dt.weekday())).date()
        if next_week:
            week_start_date = current_week_end_date + timedelta(days=1)
            week_end_date = week_start_date + timedelta(days=6)
        else:
            week_start_date = current_week_end_date - timedelta(days=6)
            week_end_date = current_week_end_date
        scheduled_period, _ = SchedulePeriod.objects.get_or_create(date_start=week_start_date, date_end=week_end_date)
        return scheduled_period

    def create_schedule_time_slots(self):
        time_slots = settings.TIME_SLOTS
        target_date = self.date_start
        with transaction.atomic():
            while target_date <= self.date_end:
                for time_slot in time_slots:
                    time_start, time_end = time_slot.split("-")
                    time_start = datetime.datetime.strptime(time_start, '%H:%M').time()
                    time_end = datetime.datetime.strptime(time_end, '%H:%M').time()

                    work_start_dt = datetime.datetime.combine(target_date, time_start)
                    work_end_dt = datetime.datetime.combine(target_date, time_end)

                    ScheduleTimeSlot.objects.get_or_create(period=self, date=target_date,
                                                           work_start_dt=work_start_dt, work_end_dt=work_end_dt)
                target_date += timedelta(days=1)
                # time.sleep(1)
        return True

    def get_schedule_time_slots(self):
        return self.scheduletimeslot_set.all()

    def get_or_create_cleaner_schedule(self, user):
        """Get an existing cleaner's schedule or create a default one"""
        cleaner_schedule = self.cleanerschedule_set.filter(user=user).order_by("time_slot")
        if not cleaner_schedule.exists():
            self.create_cleaner_schedule(user)
            cleaner_schedule = self.cleanerschedule_set.filter(user=user).order_by("time_slot")
        return cleaner_schedule

    def create_cleaner_schedule(self, user):
        bulk_list = list()
        for schedule_time_slot in self.get_schedule_time_slots().iterator():
            bulk_list.append(CleanerSchedule(user=user, period=self, time_slot=schedule_time_slot))
        CleanerSchedule.objects.bulk_create(bulk_list)
        return True

    def get_or_create_cleaner_schedule_data(self, user):
        """
        [
            {"name": "Monday", "uuid": 123, "1": True, "2": False, "3": True},
            {"name": "Tuesday", "uuid": 1235, "1": False, "2": False, "3": True}
        ]
        """
        cleaner_schedule = self.get_or_create_cleaner_schedule(user)
        data = dict()
        for item in cleaner_schedule.iterator():
            date = item.time_slot.date
            if not date in data:
                data[date] = dict(name=item.time_slot.date.strftime("%m/%d/%Y, %A"), time_slots=list())
            data[date]["time_slots"].append(
                dict(field_name=f"cleaner_schedule_uuid_{item.uuid }", is_active=item.is_active)
            )
        return list(data.values())

    def get_previous_period(self):
        previous_period_date_end = self.date_start - timedelta(days=1)
        try:
            return SchedulePeriod.objects.get(date_end=previous_period_date_end)
        except SchedulePeriod.DoesNotExist:
            return None

    def get_next_period(self):
        next_period_date_start = self.date_end + timedelta(days=1)
        try:
            return SchedulePeriod.objects.get(date_start=next_period_date_start)
        except SchedulePeriod.DoesNotExist:
            return None


class ScheduleTimeSlot(BaseModel):
    period = models.ForeignKey(SchedulePeriod, blank=True, null=True, default=None, on_delete=models.CASCADE)
    date = models.DateField()
    work_start_dt = models.DateTimeField()
    work_end_dt = models.DateTimeField()

    def __str__(self):
        return f"{self.date}, {self.work_start_dt.time()} - {self.work_end_dt.time()}"


class CleanerSchedule(BaseModel):
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    period = models.ForeignKey(SchedulePeriod, blank=True, null=True, default=None, on_delete=models.CASCADE)
    time_slot = models.ForeignKey(ScheduleTimeSlot, blank=True, null=True, default=None, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)