from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions, StrictButton, FieldWithButtons
from .models import Booking, BookingZipCodeSearch, DiscountCode
from locations.models import ZipCode, RegionZipCode
from clients.models import Place
import datetime
from ._widgets import ServiceSelectWidget, ServiceSelectMultipleWidget
from services.models import ServiceFee, ServiceFeesSnapshot
from clients.forms import PlaceForm
from django.db import transaction
from django.urls import reverse, reverse_lazy
from .mixins.forms import BookingDateTimeFormMixin


class BookingForm(BookingDateTimeFormMixin, forms.ModelForm):
    date = forms.DateField(input_formats=["%m/%d/%Y"], widget=forms.DateInput(format="%m/%d/%Y"))
    time_from = forms.TimeField(input_formats=["%I:%M %p"])
    time_to = forms.TimeField(input_formats=["%I:%M %p"])

    class Meta:
        model = Booking
        fields = [
                  # "regularity_type",  # for future possible using for one time or regular cleanings
                  "comments"]  # "scheduled_start_dt", "scheduled_end_dt",

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        place = kwargs.get("initial").get("place")
        super().__init__(*args, **kwargs)
        self.fields["services"] = forms.ModelMultipleChoiceField(queryset=ServiceFeesSnapshot.objects.none(),
                                                                 widget=ServiceSelectMultipleWidget())

        if place and place.type == Place.PLACE_TYPE_HOUSE:
            service_fees = place.region.get_area_based_and_extra_service_fees()
        else:
            # fees of the last snapshot of the region
            service_fees = place.region.get_fixed_fee_and_extra_service_fees()
        if not service_fees is None:
            self.fields["services"].queryset = service_fees
            if self.instance.pk:
                selected_services = [item.service for item in self.instance.get_booking_services(as_service_fee=True)]
                self.fields["services"].initial = service_fees.filter(service__in=selected_services)

        # self.fields["regularity_type"] = self.fields["regularity_type"].queryset.filter(is_active=True)

        total_fee = self.instance.total_fee if self.instance else 0
        fees_info = HTML(f"<div class='mb-3'>"
                         f"<b>Total Fee:</b> <span id='total_fee'>{total_fee}</span> USD"
                         f"</div>")

        self.fields["comments"].widget.attrs["rows"] = 3
        self.helper = FormHelper(self)

        self.helper.layout = Layout(
            Field("services", css_class="d-none"),
            # Field("regularity_type"),
            Field("date"),
            Field("time_from"),
            Field("time_to"),
            Field("comments"),
            fees_info,
            Div(
                HTML('<button onclick="history.back()" class="btn btn-secondary me-1">Back</button>'),
                Submit('submit', 'Submit', css_class="btn btn-primary"),
                css_class="text-center"
            )
        )


class BookingCommentOnlyForm(forms.ModelForm):

    class Meta:
        model = Booking
        fields = ["comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout.append(
            Div(
                HTML('<button onclick="history.back()" class="btn btn-secondary me-1">Back</button>'),
                Submit('submit', 'Save', css_class="btn btn-primary btn-block text-uppercase"),
                css_class="text-center"
            )
        )


class PlacesForm(forms.Form):

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["place"] = forms.ModelChoiceField(queryset=user.get_places())
        self.helper = FormHelper(self)
        self.helper.layout.append(
            Div(
                HTML('<button onclick="history.back()" class="btn btn-secondary me-1">Back</button>'),
                Submit('submit', 'Save', css_class="btn btn-primary btn-block text-uppercase"),
                css_class="text-center"
            )
        )


class DiscountCodeForm(forms.Form):
    discount_code = forms.CharField(max_length=24, label=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = "discount_apply_form"
        self.fields["discount_code"].widget.attrs["placeholder"] = "Discount code if any"
        self.helper.layout = Layout(
            FieldWithButtons('discount_code', StrictButton("Apply", css_class="btn btn-primary", type="submit"), input_size="input-group-sm")
        )

    def clean_discount_code(self):
        discount_code = self.cleaned_data.get("discount_code")
        if not DiscountCode.objects.filter(code=discount_code, is_active=True).exists():
            raise forms.ValidationError("This code is not valid")
        return discount_code


class PublicBookingZipCodeForm(forms.Form):
    """Checking zip code coverage"""
    zip_code = forms.CharField(label="Enter your zip code to check service coverage")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout.append(
            Div(
                HTML(f'<a href="{reverse("homepage")}" class="btn btn-secondary me-1">Back</a>'),
                Submit('submit', 'Submit', css_class="btn btn-primary btn-block text-uppercase"),
                css_class="text-center"
            )
        )

    def clean_zip_code(self):
        """ToDo: All valid zip codes should be prepopulated to the db"""
        zip_code = self.cleaned_data.get("zip_code")
        try:
            zip_code = ZipCode.objects.get(value=zip_code)
        except ZipCode.DoesNotExist:
            raise forms.ValidationError("This area is out of the coverage at this moment.")
        return zip_code


class PublicBookingServicesSelectionForm(forms.Form):
    """Services booking"""
    PLACE_TYPE_APARTMENT = Place.PLACE_TYPE_APARTMENT
    PLACE_TYPE_HOUSE = Place.PLACE_TYPE_HOUSE
    PLACE_TYPES = (
        (PLACE_TYPE_APARTMENT, "Apartment"), (PLACE_TYPE_HOUSE, "House")
    )
    place_type = forms.ChoiceField(choices=PLACE_TYPES)
    base_service = forms.ModelChoiceField(queryset=ServiceFeesSnapshot.objects.none(), required=False,
                                          widget=ServiceSelectWidget()
                                          )
    area_size = forms.IntegerField(required=False, label="Home Square Feet")

    def __init__(self, *args, **kwargs):
        service_fees = kwargs.pop("service_fees")
        super().__init__(*args, **kwargs)
        data = kwargs.get("data")
        if data:
            if data.get("place_type"):
                if int(data.get("place_type")) == self.PLACE_TYPE_APARTMENT:
                    base_service_qs = service_fees.filter(service__is_area_based_fee=False, service__is_chore=False)
                elif int(data.get("place_type")) == self.PLACE_TYPE_HOUSE:
                    base_service_qs = service_fees.filter(service__is_area_based_fee=True, service__is_chore=False)
                else:
                    base_service_qs = ServiceFee.objects.none()
            else:
                base_service_qs = ServiceFee.objects.none()
        else:
            base_service_qs = ServiceFee.objects.none()
        self.fields["base_service"].queryset = base_service_qs

        extra_services = list()
        for service_fee in service_fees.filter(service__is_chore=True).iterator():
            service_fee_uuid = f"extra_service_{str(service_fee.uuid)}"
            service_name = f"{service_fee.service.name}"
            client_fee = service_fee.client_fee
            self.fields[service_fee_uuid] = forms.ChoiceField(choices=(("", ""), ("Yes", "Yes")),
                                                              label=service_name, required=False)
            self.fields[service_fee_uuid].widget.attrs.update({"data-fee": client_fee})
            extra_services.append(Field(service_fee_uuid))
        self.helper = FormHelper(self)

        extra_services_nmb = len(extra_services)
        extra_services_nmb_half = round(extra_services_nmb/2)
        extra_services_column1 = Div(css_class="col-lg-6")
        extra_services_column2 = Div(css_class="col-lg-6")
        for index, item in enumerate(extra_services, start=1):
            if index <= extra_services_nmb_half:
                extra_services_column1.append(item)
            else:
                extra_services_column2.append(item)

        self.helper.layout = Layout(
            Div(
                Field("place_type"),
                Div(Field("base_service"), css_id="base_service_wrapper"),
                Div(Field("area_size"), css_id="area_size_wrapper", css_class="d-none"),
            ),
            Div(
                HTML("<div class='h3'>Add-ons</div>"),
                Div(
                    extra_services_column1,
                    extra_services_column2,
                    css_class="row", css_id="extra_services"
                ),
                css_class="mt-5 mb-3"
            ),

            Div(
                HTML(f'<a href="{reverse("public_booking_step_1")}" class="btn btn-secondary me-1">Back</a>'),
                Submit('submit', 'Submit', css_class="btn btn-primary btn-block text-uppercase"),
                css_class="text-center"
            )
        )

    def clean_area_size(self):
        cleaned_data = self.cleaned_data
        place_type = cleaned_data.get("place_type")
        area_size = cleaned_data.get("area_size")
        if int(place_type) == self.PLACE_TYPE_HOUSE and (not area_size or area_size is None):
            raise forms.ValidationError("Please set up home square feet value")
        return area_size


class PublicBookingDateTimeForm(BookingDateTimeFormMixin, forms.ModelForm):
    date = forms.DateField(input_formats=["%m/%d/%Y"], widget=forms.DateInput(format="%m/%d/%Y"))
    time_from = forms.TimeField(input_formats=["%I:%M %p"])
    time_to = forms.TimeField(input_formats=["%I:%M %p"])

    class Meta:
        model = Booking
        fields = ("scheduled_date", "scheduled_start_dt", "scheduled_end_dt", "comments")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.scheduled_date:
            self.fields["date"].initial = self.instance.scheduled_date
        if self.instance.scheduled_start_dt:
            self.fields["time_from"].initial = self.instance.scheduled_start_dt.time()
        if self.instance.scheduled_end_dt:
            self.fields["time_to"].initial = self.instance.scheduled_end_dt.time()

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Field("date"),
            Field("time_from"),
            Field("time_to"),
            Field("comments"),
            Div(
                HTML(f'<a href="{reverse("public_booking_step_2")}" class="btn btn-secondary me-1">Back</a>'),
                Submit('submit', 'Submit', css_class="btn btn-primary btn-block text-uppercase"),
                css_class="text-center"
            )
        )


class PublicBookingAddressForm(PlaceForm):
    """Address booking"""

    class Meta:
        model = Place
        fields = ("address", "apartment_nmb", "state", "city", "zip_code", "comments", "feature")

    def get_layout(self):
        layout = Layout(
            Div(
                Div(
                    Field("address", autocomplete="address-line1"),
                    Field("apartment_nmb", autocomplete="address-line2"),
                    Field("city", autocomplete="address-level2"),
                    Field("state", autocomplete="address-level1"),
                    Field("zip_code", autocomplete="postal-code"),
                    Div(css_id="minimap_container", css_class="minimap-container d-none"),
                    Div(Field("feature", css_class="d-none"), css_class="d-none"),
                    Field("comments"),
                    css_class="col-lg-4 mx-auto"
                ),
                css_class="row"
            ),

            Div(
                Div(
                    Div(
                        HTML(f'<a href="{reverse("public_booking_step_2")}" class="btn btn-secondary me-1">Back</a>'),
                        HTML('<button type="submit" class="btn btn-primary btn btn-primary">Save</button>'),
                        css_class="form-group text-center"
                    ),
                    css_class="col-lg-12"
                ),
                css_class="row"
            )
        )
        return layout

    def clean_zip_code(self):
        """ToDo: All valid zip codes should be prepopulated to the db"""
        zip_code = self.cleaned_data.get("zip_code")
        try:
            zip_code = ZipCode.objects.get(value=zip_code)
            try:
                RegionZipCode.objects.get(zip_code=zip_code)
            except RegionZipCode.DoesNotExist:
                raise forms.ValidationError("This area is out of the coverage at this moment.")
        except ZipCode.DoesNotExist:
            raise forms.ValidationError("This area is out of the coverage at this moment.")
        return zip_code