from django.db import models
from utils.models import BaseModel, BaseDictModel
from locations.models import Region
from django.urls import reverse, reverse_lazy


class ApartmentPlan(BaseDictModel):
    pass


class CleaningType(BaseDictModel):
    pass


class Service(BaseDictModel):
    REGULARITY_TYPE_ONE_TIME = 10
    REGULARITY_TYPE_REGULAR = 20
    REGULARITY_TYPES = (
        (REGULARITY_TYPE_ONE_TIME, "One time"),
        (REGULARITY_TYPE_REGULAR, "Regular")
    )
    description = models.TextField(blank=True, null=True, default=None)

    """cleaning_type: classic; move out clean"""
    apartment_plan = models.ForeignKey(ApartmentPlan, blank=True, null=True, default=None, on_delete=models.CASCADE)
    cleaning_type = models.ForeignKey(CleaningType, blank=True, null=True, default=None, on_delete=models.CASCADE)
    regularity_type = models.PositiveIntegerField(choices=REGULARITY_TYPES, default=REGULARITY_TYPE_ONE_TIME)
    is_area_based_fee = models.BooleanField(default=False)
    is_chore = models.BooleanField(default=False, choices=((True, "Yes"), (False, "No")))
    checklist = models.TextField(blank=True, null=True, default=None)

    def save(self, *args, **kwargs):
        if not self.is_chore:
            self.name = f"{self.cleaning_type}, {self.apartment_plan} ({self.regularity_type})"
        super().save(*args, **kwargs)

    @property
    def name_for_client(self):
        if self.apartment_plan:
            return f"{self.cleaning_type}, {self.apartment_plan}"
        else:
            return f"{self.name}"


class ServiceFeesSnapshot(BaseModel):
    region = models.ForeignKey(Region, blank=True, null=True, default=None, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.region.name}, {self.created}"

    def get_fees(self, as_service_fee_dict=False, is_chore=None):
        kwargs = dict()
        if not is_chore is None:
            kwargs["service__is_chore"] = is_chore
        fees = self.servicefee_set.filter(**kwargs).order_by("service__is_chore", "service_id")
        if as_service_fee_dict:
            return {item["service__uuid"]: item["client_fee"] for item in fees.values("service__uuid", "client_fee")}
        else:
            return fees

    def get_client_and_subcontractor_fees(self):
        fees_dict = dict()
        fees = self.get_fees().values("service__uuid", "client_fee", "subcontractor_fee")
        for item in fees:
            uuid = item["service__uuid"]
            client_fee = item["client_fee"]
            subcontractor_fee = item["subcontractor_fee"]
            fees_dict[uuid] = dict(client_fee=client_fee, subcontractor_fee=subcontractor_fee)
        return fees_dict

    def get_fees_dict_for_table(self):
        fees_dict = self.get_client_and_subcontractor_fees()
        return fees_dict

    def get_url(self):
        return f"{reverse('services')}?region={self.region.slug}&snapshot={self.uuid}"

    def get_send_to_company_url(self):
        """Url which renders a template with fees review for final sending to a company"""
        return f"{reverse('send_fees_to_subcontractor', kwargs=dict(uuid=self.uuid))}"

    def create_subcontractors_fees_url(self):
        """It is used in a form action"""
        return reverse("create_subcontractors_fees", kwargs=dict(uuid=self.uuid))


class ServiceFee(BaseModel):
    snapshot = models.ForeignKey(ServiceFeesSnapshot, blank=True, null=True, default=None, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    client_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subcontractor_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        name = f"{self.service.name_for_client}: {self.client_fee} USD"
        if self.service.is_area_based_fee:
            name += " per sqft"
        return name

