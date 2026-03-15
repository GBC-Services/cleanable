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
    """
    Custom User model with email-based authentication and role-based access.

    Role Architecture (v2):
    ───────────────────────
    The platform serves a cleaning‑services marketplace with six distinct
    personas.  Each role maps to a power level integer that doubles as a
    coarse permission tier — higher numbers are *not* more privileged;
    they simply partition the permission space.

    Migration note: legacy roles (Client→10, General Admin→20, Manager→30,
    Cleaner→40, Support Agent→50) are preserved as aliases so that existing
    migrations remain valid.  New code should use the v2 constants.
    """

    # ── v2 Role Constants ─────────────────────────────────────────────
    ROLE_RESIDENT = 10           # End‑user / homeowner / tenant
    ROLE_SERVICE_PRO = 40        # Field worker (cleaner, technician)
    ROLE_AGENCY_OWNER = 30       # Cleaning company owner / manager
    ROLE_QA_INSPECTOR = 60       # Quality assurance inspector
    ROLE_SUPPORT_ARCHITECT = 50  # Customer support / success
    ROLE_PLATFORM_ADMIN = 20     # System administrator
    ROLE_FISCAL_AUDITOR = 70     # Payroll auditor / financial compliance

    # ── Legacy Aliases (for backwards‑compat in existing migrations) ──
    ROLE_CLIENT = ROLE_RESIDENT
    ROLE_GENERAL_ADMIN = ROLE_PLATFORM_ADMIN
    ROLE_MANAGER = ROLE_AGENCY_OWNER
    ROLE_CLEANER = ROLE_SERVICE_PRO
    ROLE_SUPPORT_AGENT = ROLE_SUPPORT_ARCHITECT

    ROLES = (
        (ROLE_RESIDENT, "Resident"),
        (ROLE_SERVICE_PRO, "Service Pro"),
        (ROLE_AGENCY_OWNER, "Agency Owner"),
        (ROLE_QA_INSPECTOR, "QA Inspector"),
        (ROLE_SUPPORT_ARCHITECT, "Support Architect"),
        (ROLE_PLATFORM_ADMIN, "Platform Admin"),
        (ROLE_FISCAL_AUDITOR, "Fiscal Auditor"),
    )

    ROLE_SLUG_MAP = {
        ROLE_RESIDENT: "resident",
        ROLE_SERVICE_PRO: "service_pro",
        ROLE_AGENCY_OWNER: "agency_owner",
        ROLE_QA_INSPECTOR: "qa_inspector",
        ROLE_SUPPORT_ARCHITECT: "support_architect",
        ROLE_PLATFORM_ADMIN: "platform_admin",
        ROLE_FISCAL_AUDITOR: "fiscal_auditor",
    }

    # ── Fields ────────────────────────────────────────────────────────
    company = models.ForeignKey(
        "companies.Company", blank=True, null=True, default=None,
        on_delete=models.CASCADE,
    )
    role = models.PositiveIntegerField(choices=ROLES, default=ROLE_RESIDENT)
    is_accepted_emails = models.BooleanField(default=False)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    username = None
    USERNAME_FIELD = "email"
    email = models.EmailField("email address", unique=True)
    phone = PhoneNumberField(blank=True, null=True, default=None)
    description = models.TextField(blank=True, null=True, default=None)

    image = models.ImageField(
        upload_to=UploadToPathAndRenameImage(upload_to="users/images/initial"),
        blank=True, null=True, default=None,
    )
    image_small = models.ImageField(
        upload_to=UploadToPathAndRenameImage(upload_to="users/images/small"),
        blank=True, null=True, default=None, editable=False,
    )
    image_xsmall = models.ImageField(
        upload_to=UploadToPathAndRenameImage(upload_to="users/images/xsmall"),
        blank=True, null=True, default=None, editable=False,
    )
    is_contact_by_sms = models.BooleanField(
        choices=((True, "Yes"), (False, "No"), (None, "Not chosen")),
        null=True, default=None,
    )
    is_contact_by_email = models.BooleanField(
        choices=((True, "Yes"), (False, "No"), (None, "Not chosen")),
        null=True, default=None,
    )
    is_verified = models.BooleanField(default=False)

    cleaner_preferred_districts = models.TextField(
        blank=True, null=True, default=None,
    )
    cleaner_preferred_service_types = models.ManyToManyField(
        Service, blank=True,
    )

    # ── OAuth2 / Smart‑Home Integration ───────────────────────────────
    oauth2_provider_tokens = models.JSONField(
        blank=True, default=dict,
        help_text="Stores encrypted refresh tokens for connected smart‑home services.",
    )

    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    class Meta:
        indexes = [
            models.Index(fields=["role"], name="idx_user_role"),
            models.Index(fields=["email"], name="idx_user_email"),
            models.Index(fields=["company", "role"], name="idx_user_company_role"),
        ]

    # ── Init / Str / Save ─────────────────────────────────────────────
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_fields = {}
        for field in self._meta.get_fields(include_hidden=True):
            try:
                self._original_fields[field.name] = getattr(self, field.name)
            except Exception:
                pass

    def __str__(self):
        if self.is_service_pro:
            return f"{self.get_full_name()} {self.email}"
        full_name = self.get_full_name()
        return full_name if full_name.strip() else self.email

    def save(self, *args, **kwargs):
        if (
            self.image
            and self._original_fields.get("image") != self.image
            or (self.image and (not self.image_small or not self.image_xsmall))
        ):
            optimize_size = OptimizeImageSize()
            self.image_small = optimize_size.launch(self.image, "small")
            self.image_xsmall = optimize_size.launch(self.image, "x-small")

        if self.image is None:
            self.image_small = None
            self.image_xsmall = None

        super().save(*args, **kwargs)

    # ── Role Properties ───────────────────────────────────────────────
    @property
    def role_slug(self):
        return self.ROLE_SLUG_MAP.get(self.role, "unknown")

    @property
    def is_resident(self):
        return self.role == self.ROLE_RESIDENT

    @property
    def is_client(self):
        """Legacy alias for is_resident."""
        return self.is_resident

    @property
    def is_service_pro(self):
        return self.role == self.ROLE_SERVICE_PRO

    @property
    def is_cleaner(self):
        """Legacy alias for is_service_pro."""
        return self.is_service_pro

    @property
    def is_agency_owner(self):
        return self.role == self.ROLE_AGENCY_OWNER

    @property
    def is_manager(self):
        """Legacy alias for is_agency_owner."""
        return self.is_agency_owner

    @property
    def is_qa_inspector(self):
        return self.role == self.ROLE_QA_INSPECTOR

    @property
    def is_support_architect(self):
        return self.role == self.ROLE_SUPPORT_ARCHITECT

    @property
    def is_support_agent(self):
        """Legacy alias for is_support_architect."""
        return self.is_support_architect

    @property
    def is_fiscal_auditor(self):
        return self.role == self.ROLE_FISCAL_AUDITOR

    @property
    def is_platform_admin(self):
        return self.is_superuser and self.role == self.ROLE_PLATFORM_ADMIN

    @property
    def is_general_admin(self):
        """Legacy alias for is_platform_admin."""
        return self.is_platform_admin

    # ── Query Helpers (unchanged from v1) ─────────────────────────────
    def get_places(self):
        return self.place_set.filter(is_active=True).order_by("-id")

    def get_places_5(self):
        return self.get_places()[:5]

    def get_bookings(self, as_booking_ids=False):
        bookings = self.booking_set.all().order_by("-id")
        if as_booking_ids:
            return bookings.values_list("id", flat=True)
        return bookings

    def get_bookings_5(self):
        return self.get_bookings()[:5]

    def get_assigned_cleanings(self, as_cleaning_ids=False):
        cleaning_ids = self.cleanerforcleaning_set.all().values_list(
            "cleaning_id", flat=True,
        )
        if as_cleaning_ids:
            return cleaning_ids
        from apps.cleanings.models import Cleaning
        return Cleaning.objects.filter(id__in=cleaning_ids)

    def get_availability_for_date(self, date):
        return self.cleanerschedule_set.filter(
            time_slot__date=date, is_active=True,
        ).exists()

    def get_availability_for_cleaning(self, cleaning):
        return self.cleanerschedule_set.filter(
            user=self, is_active=True,
            time_slot__date=cleaning.scheduled_date,
        ).exists()

    def get_cleanings(self):
        from apps.cleanings.models import Cleaning
        assigned_cleaning_ids = self.cleanerforcleaning_set.all().values_list(
            "cleaning_id", flat=True,
        )
        return Cleaning.objects.filter(id__in=assigned_cleaning_ids)

    def get_cleanings_for_today(self):
        return self.get_cleanings().filter(scheduled_date=timezone.now().date())

    def start_verification_process(self):
        for document_type in VerificationDocumentType.objects.filter(
            is_active=True,
        ).iterator():
            UserVerificationDocument.objects.get_or_create(
                user=self, document_type=document_type,
            )

    def get_assigned_tickets(self):
        return self.support_tickets_assigned.filter(is_active=True)

    def get_cleanings_from_assigned_tickets(self):
        from apps.cleanings.models import Cleaning
        assigned_tickets = self.get_assigned_tickets().values_list(
            "booking", flat=True,
        )
        return Cleaning.objects.filter(
            booking_id__in=assigned_tickets,
        ).order_by("id")

    def get_cleaners(self):
        from apps.cleanings.models import Cleaning, CleanerForCleaning
        cleanings = Cleaning.objects.filter(booking__client=self)
        cleaner_ids = CleanerForCleaning.objects.filter(
            cleaning__in=cleanings,
        ).values_list("cleaner_id", flat=True)
        return User.objects.filter(id__in=cleaner_ids).distinct()


class UserSession(BaseModel):
    user = models.ForeignKey(
        User, blank=True, null=True, default=None, on_delete=models.CASCADE,
    )
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
        (STATUS_REJECTED, "Rejected"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.ForeignKey(
        VerificationDocumentType, null=True, default=None,
        on_delete=models.CASCADE,
    )
    file = models.FileField(
        upload_to="users/verification_documents",
        blank=True, null=True, default=None,
    )
    status = models.PositiveIntegerField(
        choices=STATUSES, blank=True, null=True,
        default=STATUS_NOT_UPLOADED,
    )
    updated_by = models.ForeignKey(
        User, blank=True, null=True, default=None,
        on_delete=models.CASCADE, related_name="verification_updated_by",
    )

    def save(self, *args, **kwargs):
        request = CrequestMiddleware.get_request()
        self.updated_by = request.user
        if self.status == self.STATUS_NOT_UPLOADED and self.file:
            self.status = self.STATUS_NEW
        super().save(*args, **kwargs)
