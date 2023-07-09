from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from django.urls import reverse
from .models import Service
import datetime
from locations.models import Region
from companies.models import Company
from django.template.loader import render_to_string
from django.conf import settings


class RegionFilterForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["region"] = forms.ModelChoiceField(queryset=Region.objects.filter(is_active=True), to_field_name="slug")
        self.helper = FormHelper(self)
        self.helper.label_class = "d-none"
        self.helper.form_method = "get"
        self.helper.form_class = "d-flex flex-row justify-content-center align-items-center flex-wrap"
        self.helper.layout = Layout(
            HTML("<div class='mb-3 me-3'>Select Region</div>"),
            Field("region"),
        )


class FeeForm(forms.Form):
    fee = forms.FloatField(min_value=0)


class SubcontractorsFeesForm(forms.Form):

    def __init__(self, *args, **kwargs):
        snapshot = kwargs.pop("snapshot")
        region = snapshot.region
        super().__init__(*args, **kwargs)
        self.fields["companies"] = forms.ModelMultipleChoiceField(queryset=region.get_companies(),
                                               to_field_name="uuid", label=f"Subcontractors for {region}")
        self.helper = FormHelper(self)
        self.helper.form_class = ""
        self.helper.form_action = snapshot.create_subcontractors_fees_url()
        self.helper.form_method = "post"

        service_fees = Service.objects.filter(is_active=True).order_by("id")
        context = dict(snapshot=snapshot, service_fees=service_fees, fees_dict=snapshot.get_fees(as_service_fee_dict=True))
        table = render_to_string("services/partials/service_fees_table.html", context)
        self.helper.layout = Layout(
            Div(
                Div(
                    Field("companies"),
                    css_class="col-lg-6 mx-auto"
                ),
                css_class="row"
            ),
            HTML(table),
            HTML("""
            <div class="mt-3 text-center">
                <button onclick="history.back()" class="btn btn-secondary me-1">Back</button>
                <button type="submit" id="fees_save_btn" class="btn btn-primary">Save</button>
            </div>
            """)
        )