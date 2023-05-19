from django.db import models
from utils.models import BaseModel, BaseDictModel
from django.contrib.auth import get_user_model
UserModel = get_user_model()


class Company(BaseDictModel):
    logo = models.ImageField(upload_to="companies/", blank=True, null=True, default=None)
    description = models.TextField(blank=True, null=True, default=None)

    def get_is_user_manager(self, user):
        return self.companyuser_set.filter(user=user, is_active=True, is_admin=True).exists()

    def get_is_user_cleaner(self, user):
        return self.companyuser_set.filter(user=user, is_active=True, is_admin=False).exists()

    def get_cleanings(self, as_cleaning_ids=False):
        cleanings = self.cleaning_set.all()
        if as_cleaning_ids:
            return cleanings.values_list("id", flat=True)
        else:
            return cleanings

    def get_assigned_user_cleanings(self, user, as_cleaning_ids=False):
        cleaning_ids = user.get_assigned_cleanings(as_cleaning_ids=True)
        cleanings = self.get_cleanings().filter(id__in=cleaning_ids)
        if as_cleaning_ids:
            return cleanings.values_list("id", flat=True)
        else:
            return cleanings


class CompanyUser(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)


class CompanyService(BaseDictModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    """cleaning_type: classic; move out clean"""
    cleaning_type = models.ForeignKey("cleanings.CleaningType", blank=True, default=None,
                                      on_delete=models.CASCADE)
    regularity_type = models.ForeignKey("cleanings.RegularityType", blank=True, default=None,
                                        on_delete=models.CASCADE)
    nmb_of_cleaners = models.PositiveIntegerField(default=1)
    hours_duration = models.PositiveIntegerField(default=1)

    # params, which will be matching from a customer's cleaning request
    bedrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    bathrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    kitchen_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    other_rooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    total_area_size = models.PositiveIntegerField(blank=True, null=True, default=None)