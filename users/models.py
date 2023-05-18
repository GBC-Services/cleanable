from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from .managers import CustomUserManager
from utils.models import BaseModel, BaseDictModel
from django.db.models import Q


class User(AbstractUser):
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
        super().save(*args, **kwargs)