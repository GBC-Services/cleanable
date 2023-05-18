from django.db import models
from utils.models import BaseModel, BaseDictModel


class Client(BaseModel):
    pass


class PlaceType(BaseDictModel):
    pass


class Place(BaseDictModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    type = models.ForeignKey(PlaceType, on_delete=models.CASCADE)

    bedrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    bathrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    kitchen_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    other_rooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    total_area_size = models.PositiveIntegerField(blank=True, null=True, default=None)

    address = models.CharField(max_length=256)
    address_id = models.CharField(max_length=128)
    comments = models.TextField()




