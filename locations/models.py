from django.db import models
from django.db.models import Q
from utils.models import BaseModel, BaseDictModel
from django.conf import settings


class Country(BaseDictModel):
    pass


class State(BaseDictModel):
    country = models.ForeignKey(Country, on_delete=models.CASCADE)


class City(BaseDictModel):
    state = models.ForeignKey(State, on_delete=models.CASCADE)
    pass


class ZipCode(BaseModel):
    city = models.ForeignKey(City, null=True, default=None, on_delete=models.CASCADE)
    value = models.CharField(max_length=12, unique=True)

    def __str__(self):
        return f"{self.value}"

    def get_service_fees(self, is_chore=None):
        region_zip_code = self.regionzipcode_set.filter(is_active=True).last()
        if region_zip_code:
            return region_zip_code.region.get_service_fees(is_chore=is_chore)
        else:
            return None


class Region(BaseDictModel):
    profit_rate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, default=None)

    def save(self, *args, **kwargs):
        if not self.profit_rate:
            self.profit_rate = settings.DEFAULT_PROFIT_RATE
        super().save(*args, **kwargs)

    def get_fees_snapshots(self):
        return self.servicefeessnapshot_set.all().order_by("-id")

    def get_fees_last_snapshot(self):
        """If snapshots are ordered by -id, then the most recent one should be selected with .first() instead of .last()"""
        return self.get_fees_snapshots().first()

    def get_service_fees(self, is_chore=None):
        snapshot = self.get_fees_last_snapshot()
        if snapshot:
            return snapshot.get_fees(is_chore=is_chore)
        else:
            return None

    def get_fixed_fee_and_extra_service_fees(self):
        qs = self.get_service_fees()
        if not qs is None:
            qs = qs.filter(Q(service__is_area_based_fee=False, service__is_chore=False)
                           | Q(service__is_chore=True))
        return qs

    def get_area_based_and_extra_service_fees(self):
        qs = self.get_service_fees()
        if not qs is None:
            qs = qs.filter(Q(service__is_area_based_fee=True, service__is_chore=False)
                           | Q(service__is_chore=True))
        return qs

    def get_companies(self):
        return self.company_set.filter(is_active=True)

    def get_fees_rate(self):
        return self.profit_rate if not self.profit_rate is None else 0


class RegionZipCode(BaseModel):
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    zip_code = models.ForeignKey(ZipCode, blank=True, null=True, default=None, on_delete=models.CASCADE)