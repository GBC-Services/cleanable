from django.db import models
from utils.models import BaseModel, BaseDictModel
from clients.models import Client, Place
from companies.models import Company, CompanyService
from cleaners.models import Cleaner


class CleaningStatus(BaseDictModel):
    """It could be some specific items for a certain company"""
    company = models.ForeignKey(Company, blank=True, null=True, default=None, on_delete=models.CASCADE)


class FeedbackTagForCleaner(BaseDictModel):
    """It could be some specific items for a certain company"""
    company = models.ForeignKey(Company, blank=True, null=True, default=None, on_delete=models.CASCADE)


class FeedbackTagForClient(BaseDictModel):
    """It could be some specific items for a certain company"""
    company = models.ForeignKey(Company, blank=True, null=True, default=None, on_delete=models.CASCADE)


class Cleaning(BaseModel):
    # company can be retrieved from service as well
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    service = models.ForeignKey(CompanyService, on_delete=models.CASCADE)

    # client can be retrieved from place as well
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)

    status = models.ForeignKey(CleaningStatus, on_delete=models.CASCADE)
    scheduled_start_dt = models.DateTimeField()
    scheduled_end_dt = models.DateTimeField()
    real_start_dt = models.DateTimeField(blank=True, null=True, default=None)
    real_end_dt = models.DateTimeField(blank=True, null=True, default=None)

    client_comments = models.TextField(blank=True, null=True, default=None)
    manager_comments = models.TextField(blank=True, null=True, default=None)
    cleaner_comments = models.TextField(blank=True, null=True, default=None)

    score_for_cleaner = models.PositiveIntegerField(blank=True, null=True, default=None)
    feedback_for_cleaner = models.TextField(blank=True, null=True, default=None)
    feedback_tags_for_cleaner = models.ManyToManyField(FeedbackTagForCleaner)

    score_for_client = models.PositiveIntegerField(blank=True, null=True, default=None)
    feedback_for_client = models.TextField(blank=True, null=True, default=None)
    feedback_tags_for_client = models.ManyToManyField(FeedbackTagForClient)

    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    add_ons_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_fee_final = models.DecimalField(max_digits=10, decimal_places=2, default=0)


class AddOn(BaseDictModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    description = models.TextField(blank=True, null=True, default=None)


class CleaningAddOn(BaseDictModel):
    cleaning = models.ForeignKey(Cleaning, on_delete=models.CASCADE)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)


class AssignedCleaner(BaseModel):
    cleaning = models.ForeignKey(Cleaning, on_delete=models.CASCADE)
    cleaner = models.ForeignKey(Cleaner, on_delete=models.CASCADE)
