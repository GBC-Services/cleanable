from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from .managers import CustomUserManager
from utils.models import BaseModel, BaseDictModel
from django.db.models import Q


class Role(BaseDictModel):
    pass


class User(AbstractUser):
    role = models.ForeignKey(Role, null=True, default=None, on_delete=models.CASCADE)
    is_accepted_emails = models.BooleanField(default=False)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    username = None
    USERNAME_FIELD = 'email'
    email = models.EmailField('email address', unique=True)
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return "{}".format(self.email)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._original_fields = {}
        for field in self._meta.get_fields(include_hidden=True):
            try:
                self._original_fields[field.name] = getattr(self, field.name)
            except:
                pass

    def save(self, *args, **kwargs):
        if not self.pk and not self.role:
            self.role, _ = Role.objects.get_or_create(name="Client")
        super().save(*args, **kwargs)

    @property
    def is_client(self):
        return self.role.name == "Client" if self.role else None

    @property
    def is_manager(self):
        return self.role.name == "Manager" if self.role else None

    @property
    def is_cleaner(self):
        return self.role.name == "Cleaner" if self.role else None

    def get_places(self):
        return self.place_set.all().order_by("-id")

    def get_places_5(self):
        return self.get_places()[:5]

    def get_ordered_cleanings(self, as_cleaning_ids=False):
        cleanings = self.cleaning_set.all().order_by("-id")
        if as_cleaning_ids:
            return cleanings.values_list("id", flat=True)
        else:
            return cleanings

    def get_ordered_cleanings_5(self):
        return self.get_ordered_cleanings()[:5]

    def get_assigned_cleanings(self, as_cleaning_ids=False):
        assigned_cleanings = self.assignedcleaning_set.all().order_by("-id")
        if as_cleaning_ids:
            return assigned_cleanings.values_list("cleaning_id", flat=True)
        else:
            return assigned_cleanings