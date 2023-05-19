from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from .models import Place
import datetime


class PlaceForm(forms.ModelForm):

    class Meta:
        model = Place
        fields = ("name", "type", "bedrooms_nmb", "bathrooms_nmb", "kitchens_nmb", "other_rooms_nmb", "total_area_size",
                  "address", "comments",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comments"].widget.attrs["rows"] = 3
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Div(
                Div(
                    Field("name"),
                    css_class="col-lg-6"),
                Div(
                    Field("type"),
                    css_class="col-lg-6"),
                css_class="row"
            ),
            Div(
                Div(
                    Field("bedrooms_nmb"),
                    css_class="col-lg-4"),
                Div(
                    Field("bathrooms_nmb"),
                    css_class="col-lg-4"),
                Div(
                    Field("kitchens_nmb"),
                    css_class="col-lg-4"),
                css_class="row"
            ),

            Div(
                Div(
                    Field("other_rooms_nmb"),
                    css_class="col-lg-4"),
                Div(
                    Field("total_area_size"),
                    css_class="col-lg-4"),
                css_class="row"
            ),

            Div(
                Div(
                    Field("address"),
                    Field("comments"),
                    css_class="col-lg-12"),
                css_class="row"
            ),
            Row(
                Submit('submit', 'Save', css_class="btn btn-primary btn-block text-uppercase")
            )
        )