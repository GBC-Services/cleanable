from django.db import models
from utils.models import BaseModel, BaseDictModel
from django.conf import settings
from django.urls import reverse, reverse_lazy
from services.models import Service, ServiceFee, ServiceFeesSnapshot
from locations.models import Region, ZipCode
from django.utils import timezone
from users.models import User
from phonenumber_field.modelfields import PhoneNumberField


class Company(BaseDictModel):
    name = models.CharField(max_length=128, blank=True, null=True, default=None, unique=True)
    phone = PhoneNumberField(blank=True, null=True, default=None)

    # ToDo: to think later if zip code Charfield is OK or it should be a ForeignKey to a ZipCode model"""
    zip_code = models.ForeignKey(ZipCode, blank=True, null=True, default=None, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, blank=True, null=True, default=None, on_delete=models.CASCADE)
    logo = models.ImageField(upload_to="companies/", blank=True, null=True, default=None)
    description = models.TextField(blank=True, null=True, default=None)

    def save(self, *args, **kwargs):
        if not self.pk and not self.region and self.zip_code:
            from locations.models import RegionZipCode
            region_zip_codes = RegionZipCode.objects.filter(zip_code=self.zip_code)
            if region_zip_codes.count() == 1:
                self.region = region_zip_codes.last().region
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("company_update")

    def get_is_user_manager(self, user):
        return user.company == self and user.is_manager and user.is_active

    def get_is_user_cleaner(self, user):
        return user.company == self and user.is_cleaner and user.is_active

    def get_managers(self):
        return self.user_set.filter(role=User.ROLE_MANAGER)

    def get_cleaners(self):
        return self.user_set.filter(role=User.ROLE_CLEANER)

    def get_company_cleaner_invites(self):
        return self.companycleanerinvite_set.all().order_by("-id")

    def get_cleanings(self, as_cleaning_ids=False):
        cleanings = self.cleaning_set.all()
        if as_cleaning_ids:
            return cleanings.values_list("id", flat=True)
        else:
            return cleanings

    def get_cleanings_5(self):
        return self.get_cleanings()[:5]

    def get_cleanings_to_assign(self):
        return self.cleaning_set.filter(status=10)  # initial status: not assigned

    def get_assigned_user_cleanings(self, user, as_cleaning_ids=False):
        cleaning_ids = user.get_assigned_cleanings(as_cleaning_ids=True)

        # double checking this just in case if a user had another company in the past (edge case)
        cleanings = self.get_cleanings().filter(id__in=cleaning_ids)
        if as_cleaning_ids:
            return cleanings.values_list("id", flat=True)
        else:
            return cleanings

    def get_services(self):
        return self.companyservicefee_set.filter(is_active=True)

    def get_fees_snapshots(self):
        return self.companyservicefeessnapshot_set.filter(is_active=True)

    def get_last_fees_snapshot(self):
        return self.get_fees_snapshots().last()

    def has_fees_accepted(self):
        snapshot = self.get_last_fees_snapshot()
        return snapshot.is_accepted if snapshot else False

    def get_client_ids(self):
        return self.get_cleanings().values_list("booking__user_id", flat=True)

    def get_availability_for_booking(self, booking):
        from cleaners.models import CleanerSchedule
        return CleanerSchedule.objects.filter(user__company=self, is_active=True,
                                              time_slot__date=booking.scheduled_date).exists()


class CompanyServiceFeesSnapshot(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    service_fees_snapshot = models.ForeignKey(ServiceFeesSnapshot, blank=True, null=True, default=None, on_delete=models.CASCADE)
    is_accepted = models.BooleanField(default=False)
    accepted_dt = models.DateTimeField(blank=True, null=True, default=None)

    def get_fees(self):
        return self.companyservicefee_set.all().order_by("service_id")

    def accept(self):
        if not self.is_accepted:
            self.is_accepted = True
            self.accepted_dt = timezone.now()
            self.save(force_update=True)
            return True
        else:
            return False


class CompanyServiceFee(BaseModel):
    snapshot = models.ForeignKey(CompanyServiceFeesSnapshot, blank=True, null=True, default=None, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, blank=True, null=True, default=None, on_delete=models.CASCADE)

    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # not clear if the below 2 fields are needed
    nmb_of_cleaners = models.PositiveIntegerField(default=1)
    hours_duration = models.PositiveIntegerField(blank=True, null=True, default=None)

    description = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        return f"{self.service.cleaning_type} for {self.service.apartment_plan} ({self.service.regularity_type})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
