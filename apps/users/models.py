from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from .managers import CustomUserManager
from apps.utils.models import BaseModel, BaseDictModel
from apps.locations.models import Region
from django.db.models import Q
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from apps.utils.images_utils import UploadToPathAndRenameImage, OptimizeImageSize
from crequest.middleware import CrequestMiddleware
from apps.services.models import Service


class User(AbstractUser):
    ROLE_CLIENT = 10
    ROLE_GENERAL_ADMIN = 20
    ROLE_MANAGER = 30
    ROLE_CLEANER = 40
    ROLE_SUPPORT_AGENT = 50
    ROLES = (
        (ROLE_CLIENT, "Client"),
        (ROLE_GENERAL_ADMIN, "General Admin"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_CLEANER, "Cleaner"),
        (ROLE_SUPPORT_AGENT, "Support Agent")
    )
    company = models.ForeignKey("companies.Company", blank=True, null=True, default=None, on_delete=models.CASCADE)
    role = models.PositiveIntegerField(choices=ROLES, default=ROLE_CLIENT)
    is_accepted_emails = models.BooleanField(default=False)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    username = None
    USERNAME_FIELD = 'email'
    email = models.EmailField('email address', unique=True)
    phone = PhoneNumberField(blank=True, null=True, default=None)
    description = models.TextField(blank=True, null=True, default=None)

    image = models.ImageField(upload_to=UploadToPathAndRenameImage(upload_to="users/images/initial"),
                              blank=True, null=True, default=None)
    image_small = models.ImageField(upload_to=UploadToPathAndRenameImage(upload_to="users/images/small"),
                                    blank=True, null=True, default=None, editable=False)
    image_xsmall = models.ImageField(upload_to=UploadToPathAndRenameImage(upload_to="users/images/xsmall"),
                                     blank=True, null=True, default=None, editable=False)
    is_contact_by_sms = models.BooleanField(choices=((True, "Yes"), (False, "No"), (None, "Not chosen")),
                                            null=True, default=None)
    is_contact_by_email = models.BooleanField(choices=((True, "Yes"), (False, "No"), (None, "Not chosen")),
                                              null=True, default=None)

    is_verified = models.BooleanField(default=False)

    cleaner_preferred_districts = models.TextField(blank=True, null=True, default=None)
    cleaner_preferred_service_types = models.ManyToManyField(Service, null=True)

    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._original_fields = {}
        for field in self._meta.get_fields(include_hidden=True):
            try:
                self._original_fields[field.name] = getattr(self, field.name)
            except:
                pass

    def __str__(self):
        if self.is_cleaner:
            return f"{self.get_full_name()} {self.email}"
        else:
            full_name = f"{self.get_full_name()}"
            return full_name if full_name else f"{self.email}"

    def save(self, *args, **kwargs):
        if self.image and self._original_fields["image"] != self.image \
                or (self.image and (not self.image_small or not self.image_xsmall)):
            optimize_size = OptimizeImageSize()
            self.image_small = optimize_size.launch(self.image, "small")
            self.image_xsmall = optimize_size.launch(self.image, "x-small")

        if self.image is None:
            self.image_small = None
            self.image_xsmall = None

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
    def is_support_agent(self):
        return self.role == self.ROLE_SUPPORT_AGENT if self.role else False

    @property
    def is_general_admin(self):
        """It is possible to use here role instead of is_superuser"""
        return self.is_superuser and self.role == self.ROLE_GENERAL_ADMIN if self.role else False

    def get_places(self):
        return self.place_set.filter(is_active=True).order_by("-id")

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
            from apps.cleanings.models import Cleaning
            return Cleaning.objects.filter(id__in=cleaning_ids)

    def get_availability_for_date(self, date):
        return self.cleanerschedule_set.filter(time_slot__date=date, is_active=True).exists()

    def get_availability_for_cleaning(self, cleaning):
        return self.cleanerschedule_set.filter(user=self, is_active=True,
                                              time_slot__date=cleaning.scheduled_date).exists()

    def get_cleanings(self):
        from apps.cleanings.models import Cleaning
        assigned_cleaning_ids = self.cleanerforcleaning_set.all().values_list("cleaning_id", flat=True)
        return Cleaning.objects.filter(id__in=assigned_cleaning_ids)

    def get_cleanings_for_today(self):
        return self.get_cleanings().filter(scheduled_date=timezone.now().date())

    def start_verification_process(self):
        for document_type in VerificationDocumentType.objects.filter(is_active=True).iterator():
            UserVerificationDocument.objects.get_or_create(user=self, document_type=document_type)

    def get_assigned_tickets(self):
        return self.support_tickets_assigned.filter(is_active=True)

    def get_cleanings_from_assigned_tickets(self):
        from apps.cleanings.models import Cleaning
        assigned_tickets = self.get_assigned_tickets().values_list("booking", flat=True)
        cleanings = Cleaning.objects.filter(booking_id__in=assigned_tickets).order_by("id")
        return cleanings

    def get_cleaners(self):
        from apps.cleanings.models import Cleaning, CleanerForCleaning
        cleanings = Cleaning.objects.filter(booking__client=self)
        cleaner_ids = CleanerForCleaning.objects.filter(cleaning__in=cleanings).values_list("cleaner_id", flat=True)
        return User.objects.filter(id__in=cleaner_ids).distinct()


class UserSession(BaseModel):
    user = models.ForeignKey(User, blank=True, null=True, default=None, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=64)


class VerificationDocumentType(BaseDictModel):
    pass


class UserVerificationDocument(BaseModel):
    STATUS_NOT_UPLOADED = 5
    STATUS_NEW = 10
    STATUS_APPROVED = 20
    STATUS_REJECTED = 30
    STATUSES = (
        (STATUS_NOT_UPLOADED, "Not Uploaded"),
        (STATUS_NEW, "New"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected")
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.ForeignKey(VerificationDocumentType, null=True, default=None, on_delete=models.CASCADE)
    file = models.FileField(upload_to="users/verification_documents", blank=True, null=True, default=None)
    status = models.PositiveIntegerField(choices=STATUSES, blank=True, null=True, default=STATUS_NOT_UPLOADED)
    updated_by = models.ForeignKey(User, blank=True, null=True, default=None, on_delete=models.CASCADE,
                                   related_name="verification_updated_by")

    def save(self, *args, **kwargs):
        request = CrequestMiddleware.get_request()
        self.updated_by = request.user
        if self.status == self.STATUS_NOT_UPLOADED and self.file:
            self.status = self.STATUS_NEW
        super().save(*args, **kwargs)
