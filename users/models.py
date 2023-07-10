from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from .managers import CustomUserManager
from utils.models import BaseModel, BaseDictModel
from django.db.models import Q
from locations.models import Region
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField


class User(AbstractUser):
    ROLE_CLIENT = 10
    ROLE_GENERAL_ADMIN = 20
    ROLE_MANAGER = 30
    ROLE_CLEANER = 40
    ROLES = (
        (ROLE_CLIENT, "Client"),
        (ROLE_GENERAL_ADMIN, "General Admin"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_CLEANER, "Cleaner")
    )
    company = models.ForeignKey("companies.Company", blank=True, null=True, default=None, on_delete=models.CASCADE)
    role = models.PositiveIntegerField(choices=ROLES, default=ROLE_CLIENT)
    is_accepted_emails = models.BooleanField(default=False)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    username = None
    USERNAME_FIELD = 'email'
    email = models.EmailField('email address', unique=True)
    phone = PhoneNumberField(blank=True, null=True, default=None)
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        if self.is_cleaner:
            return f"{self.get_full_name()}"
        else:
            return f"{self.email}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._original_fields = {}
        for field in self._meta.get_fields(include_hidden=True):
            try:
                self._original_fields[field.name] = getattr(self, field.name)
            except:
                pass

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @property
    def is_client(self):
        return self.role == self.ROLE_CLIENT if self.role else False

    @property
    def is_cleaner(self):
        return self.role == self.ROLE_CLEANER if self.role else False

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER if self.role else False

    @property
    def is_general_admin(self):
        """It is possible to use here role instead of is_superuser"""
        return self.is_superuser and self.role == self.ROLE_GENERAL_ADMIN if self.role else False

    def get_places(self):
        return self.place_set.all().order_by("-id")

    def get_places_5(self):
        return self.get_places()[:5]

    def get_bookings(self, as_booking_ids=False):
        bookings = self.booking_set.all().order_by("-id")
        if as_booking_ids:
            return bookings.values_list("id", flat=True)
        else:
            return bookings

    def get_bookings_5(self):
        return self.get_bookings()[:5]

    def get_assigned_cleanings(self, as_cleaning_ids=False):
        cleaning_ids = self.cleanerforcleaning_set.all().values_list("cleaning_id", flat=True)
        if as_cleaning_ids:
            return cleaning_ids
        else:
            from cleanings.models import Cleaning
            return Cleaning.objects.filter(id__in=cleaning_ids)

    def get_availability_for_date(self, date):
        """For a cleaner"""
        return self.cleanerforcleaning_set.filter(time_slot__date=date, is_active=True)

    def get_cleanings(self):
        from cleanings.models import Cleaning
        assigned_cleaning_ids = self.cleanerforcleaning_set.all().values_list("cleaning_id", flat=True)
        return Cleaning.objects.filter(id__in=assigned_cleaning_ids)

    def get_cleanings_for_today(self):
        return self.get_cleanings().filter(scheduled_date=timezone.now().date())


class UserSession(BaseModel):
    user = models.ForeignKey(User, blank=True, null=True, default=None, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=64)