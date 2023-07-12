from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from django.urls import reverse
from .models import Company, CompanyServiceFee
import datetime


class CompanyCreateForm(forms.ModelForm):

    class Meta:
        model = Company
        fields = ("name", "region", "description")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["rows"] = 6
        self.helper = FormHelper(self)
        self.helper.layout.append(
            Div(
                HTML(f"<a href='{reverse('companies')}' class='btn btn-secondary me-1'>Back</a>"),
                Submit('submit', 'Save', css_class="btn btn-primary text-uppercase"),
                css_class="text-center"
            )
        )


class CompanyForm(forms.ModelForm):

    class Meta:
        model = Company
        fields = ("name", "phone", "region", "description",)  # ToDo: maybe add logo as well

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request")
        user = request.user
        super().__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["rows"] = 6
        if user.is_general_admin:
            del self.fields["name"]
            del self.fields["phone"]
            del self.fields["description"]
            back_url = request.META.get("HTTP_REFERER", "/")
        elif user.is_manager:
            del self.fields["region"]
            back_url = reverse('company')

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Field("name"),
            Field("phone"),
            Field("region"),
            Field("description"),
            Div(
                HTML(f"<a href='{back_url}' class='btn btn-secondary me-1'>Back</a>"),
                Submit('submit', 'Save', css_class="btn btn-primary text-uppercase"),
                css_class="text-center"
            )
        )