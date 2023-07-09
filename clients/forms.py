from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from .models import Place
from locations.models import Country, State, City, ZipCode
import datetime


class PlaceForm(forms.ModelForm):

    class Meta:
        model = Place
        fields = ("name", "type", "area_size", "address", "apartment_nmb", "state", "city", "zip_code", "comments", "feature")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["state"] = forms.CharField()
        self.fields["city"] = forms.CharField()
        self.fields["zip_code"] = forms.CharField()
        self.fields["comments"].widget.attrs["rows"] = 3

        self.helper = FormHelper(self)
        self.helper.form_id = "id_form"
        self.helper.attrs["autocomplete"] = "off"
        self.helper.layout = self.get_layout()

    def get_layout(self):
        layout = Layout(
            Div(
                Div(
                    Field("name"),
                    Field("type"),
                    Field("area_size"),

                    Field("address", autocomplete="address-line1"),

                    Field("apartment_nmb", autocomplete="address-line2"),
                    Field("city", autocomplete="address-level2"),
                    Field("state", autocomplete="address-level1"),
                    Field("zip_code", autocomplete="postal-code"),
                    Div(css_id="minimap_container", css_class="minimap-container d-none"),
                    Field("comments"),
                    Div(Field("feature"), css_class="d-none"),
                    css_class="col-lg-12 mx-auto"),
                css_class="row"
            ),
            Div(
                HTML('<button onclick="history.back()" class="btn btn-secondary me-1">Back</button>'),
                HTML('<button type="submit" class="btn btn-primary btn btn-primary">Save</button>'),
                css_class="form-group text-center"
            )
        )
        return layout

    def clean_state(self):
        state = self.cleaned_data.get("state")
        country, _ = Country.objects.get_or_create(name="USA")
        state, _ = State.objects.get_or_create(country=country, name=state)
        return state

    def clean_city(self):
        state = self.cleaned_data.get("state")
        city = self.cleaned_data.get("city")
        city, _ = City.objects.get_or_create(state=state, name=city)
        return city

    def clean_zip_code(self):
        city = self.cleaned_data.get("city")
        zip_code = self.cleaned_data.get("zip_code")
        zip_code, _ = ZipCode.objects.get_or_create(city=city, value=zip_code.upper())
        return zip_code