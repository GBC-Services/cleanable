from django.db import models
from utils.models import BaseModel, BaseDictModel
from django.core.validators import MinValueValidator, MaxValueValidator
from companies.models import Company
from django.contrib.auth import get_user_model
UserModel = get_user_model()


class ScheduleChange(BaseModel):
    cleaner = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    relevant_since_date = models.DateField(blank=True, default=None)


class Schedule(BaseModel):
    cleaner = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    schedule_change = models.ForeignKey(ScheduleChange, on_delete=models.CASCADE)
    relevant_since_date = models.DateField()
    weekday_from = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(7)])
    weekday_to = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(7)])
    work_start_dt = models.DateTimeField()
    work_end_dt = models.DateTimeField()
