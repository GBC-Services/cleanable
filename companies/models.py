from django.db import models
from utils.models import BaseModel, BaseDictModel
from django.contrib.auth import get_user_model
UserModel = get_user_model()


class Company(BaseDictModel):
    logo = models.ImageField(upload_to="companies/", blank=True, null=True, default=None)
    description = models.TextField(blank=True, null=True, default=None)


class CompanyUser(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)


class CleaningType(BaseDictModel):
    """It could be some specific items for a certain company"""
    company = models.ForeignKey(Company, blank=True, null=True, default=None, on_delete=models.CASCADE)


class RegularityType(BaseDictModel):
    """It could be some specific items for a certain company"""
    company = models.ForeignKey(Company, blank=True, null=True, default=None, on_delete=models.CASCADE)


class CompanyService(BaseDictModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cleaning_type = models.ForeignKey(CleaningType, on_delete=models.CASCADE)  # classic; move out clean
    regularity_type = models.ForeignKey(RegularityType, on_delete=models.CASCADE)
    nmb_of_cleaners = models.PositiveIntegerField(default=1)
    hours_duration = models.PositiveIntegerField(default=1)

    # params, which will be matching from a customer's cleaning request
    bedrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    bathrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    kitchen_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    other_rooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    total_area_size = models.PositiveIntegerField(blank=True, null=True, default=None)