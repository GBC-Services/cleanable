from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from django.urls import reverse
from .models import CompanyCleanerInvite
import datetime
from django.db.models import Q


class CompanyCleanerInviteForm(forms.ModelForm):

    class Meta:
        model = CompanyCleanerInvite
        fields = ["email"]

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop("company")
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout.append(
            Div(
                HTML(f"<a href='{reverse('company_cleaners')}' class='btn btn-secondary me-1'>Back</a>"),
                Submit('submit', 'Save', css_class="btn btn-primary text-uppercase"),
                css_class="text-center"
            )
        )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if CompanyCleanerInvite.objects.filter(Q(email=email, company=self.company, is_active=True)
                                               |Q(user__email=email, company=self.company, is_active=True)).exists():
            raise forms.ValidationError("User with this email is already in you cleaners list")
        return email


class CleanerScheduleForm(forms.Form):
    is_active = forms.BooleanField()
