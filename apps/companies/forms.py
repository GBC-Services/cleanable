from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from django.urls import reverse
from .models import Company, CompanyDocument, CompanyServiceFee
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
    general_admin_fields = ["region", "e_signed_contract_url", "description"]

    class Meta:
        model = Company
        fields = ("name", "phone", "region", "description", "logo", "e_signed_contract_url")

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request")
        user = request.user
        super().__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["rows"] = 6
        self.fields["e_signed_contract_url"].label = "E-signed contract url"

        if user.is_general_admin:
            for field in self.fields.copy():
                if not field in self.general_admin_fields:
                    del self.fields[field]
            back_url = request.META.get("HTTP_REFERER", "/")
        elif user.is_manager:
            for field in self.general_admin_fields:
                del self.fields[field]
            back_url = reverse('company')

        self.helper = FormHelper(self)

        if user.is_general_admin:
            pass
        else:
            self.helper.layout = Layout(
                Field("name"),
                Field("phone"),
                Field("logo"),
            )
        self.helper.layout.append(
            Div(
                HTML(f"<a href='{back_url}' class='btn btn-secondary me-1'>Back</a>"),
                Submit('submit', 'Save', css_class="btn btn-primary text-uppercase"),
                css_class="text-center"
            )
        )


class CompanyDocumentForm(forms.ModelForm):

    class Meta:
        model = CompanyDocument
        fields = ["type", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.layout.append(
            Div(
                HTML(f"<button onclick='history.back()' class='btn btn-secondary me-1'>Back</button>"),
                Submit('submit', 'Save', css_class="btn btn-primary text-uppercase"),
                css_class="text-center"
            )
        )
