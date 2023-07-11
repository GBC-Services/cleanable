from django.db import models
from utils.models import BaseModel, BaseDictModel
from locations.models import Country, State, City, ZipCode, Region, RegionZipCode
from users.models import User, UserSession


class Place(BaseDictModel):
    PLACE_TYPE_APARTMENT = 10
    PLACE_TYPE_HOUSE = 20
    PLACE_TYPE_COMMERCIAL = 30

    PLACE_TYPES = (
        (PLACE_TYPE_APARTMENT, "Apartment"),
        (PLACE_TYPE_HOUSE, "House"),
        (PLACE_TYPE_COMMERCIAL, "Commercial"),
    )
    client = models.ForeignKey(User, blank=True, null=True, default=None, on_delete=models.CASCADE)

    # for creating places before user signup
    user_session = models.ForeignKey(UserSession, blank=True, null=True, default=None, on_delete=models.CASCADE)

    type = models.PositiveIntegerField(choices=PLACE_TYPES, default=PLACE_TYPE_APARTMENT)

    bedrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    bathrooms_nmb = models.PositiveIntegerField(blank=True, null=True, default=None)
    area_size = models.PositiveIntegerField(blank=True, null=True, default=None)

    """Region is assigned from a zip code if zip code belongs to some region"""
    region = models.ForeignKey(Region, blank=True, null=True, default=None, on_delete=models.CASCADE)

    """Address"""
    address = models.CharField(max_length=256)
    apartment_nmb = models.CharField(max_length=12, blank=True, null=True, default=None)
    country = models.ForeignKey(Country, blank=True, null=True, default=None, on_delete=models.CASCADE)
    state = models.ForeignKey(State, blank=True, null=True, default=None, on_delete=models.CASCADE)
    city = models.ForeignKey(City, blank=True, null=True, default=None, on_delete=models.CASCADE)
    zip_code = models.ForeignKey(ZipCode, blank=True, null=True, default=None, on_delete=models.CASCADE)
    feature = models.TextField(blank=True, null=True, default=None)

    comments = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        return f"{self.get_full_address()}"

    def save(self, *args, **kwargs):
        if not self.country:
            self.country, _ = Country.objects.get_or_create(name="USA")
        if self.zip_code:
            try:
                region_zip_code = RegionZipCode.objects.get(zip_code__value=self.zip_code)
                self.region = region_zip_code.region
            except RegionZipCode.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def get_bookings(self):
        return self.booking_set.all()

    def get_google_maps_url(self):
        return f"https://maps.google.com/?q={self.get_full_address()}"

    def get_full_address(self):
        if self.city and self.state and self.zip_code:
            return f"{self.address}, {self.apartment_nmb}, {self.city.name}, {self.state.name}, {self.zip_code.value}"
        else:
            return self.address