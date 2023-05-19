from django.db import models
from utils.models import BaseModel, BaseDictModel
from django.contrib.auth import get_user_model
UserModel = get_user_model()


class PlaceType(BaseDictModel):
    pass


class Place(BaseDictModel):
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    type = models.ForeignKey(PlaceType, on_delete=models.CASCADE)

    bedrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=0)
    bathrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=0)
    kitchens_nmb = models.PositiveIntegerField(blank=True, null=True, default=0)
    other_rooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=0)
    total_area_size = models.PositiveIntegerField(blank=True, null=True, default=None)

    address = models.CharField(max_length=256)
    address_id = models.CharField(max_length=128)
    comments = models.TextField(blank=True, null=True, default=None)

