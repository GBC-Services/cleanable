from django import forms
from apps.services.models import ServiceFee


class ServiceSelectWidget(forms.Select):
    """This is not used anymore after implementing ajax-based approach for getting services,
    based on the selected property type"""

    def create_option(
            self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value:
            service_fee = ServiceFee.objects.get(id=str(value))
            option["attrs"].update({"data-fee": service_fee.client_fee,
                                    "data-is-area-based-fee": str(service_fee.service.is_area_based_fee)})
        return option


class ServiceSelectMultipleWidget(forms.SelectMultiple):

    def create_option(
            self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value:
            service_fee = ServiceFee.objects.get(id=str(value))
            option["attrs"].update({"data-fee": service_fee.client_fee,
                                    "data-is-area-based-fee": str(service_fee.service.is_area_based_fee)})
        return option