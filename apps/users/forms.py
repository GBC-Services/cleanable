from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
from .models import User, UserVerificationDocument
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Fieldset, ButtonHolder, Div, HTML
from string import Template
from django.utils.safestring import mark_safe
from django.forms import ImageField
from django.utils import timezone
from django.urls import reverse


class UserCreationForm(UserCreationForm):

    class Meta(UserCreationForm):
        model = User
        fields = ("email",)


class UserChangeForm(UserChangeForm):

    class Meta:
        model = User
        fields = ("email",)


class ProfileForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ("first_name", "last_name", "description", "phone", "image",
                  "is_contact_by_sms", "is_contact_by_email",
                  "cleaner_preferred_districts", "cleaner_preferred_service_types")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["rows"] = 5
        self.fields["is_contact_by_sms"].label = "Contact me by sms"
        self.fields["is_contact_by_email"].label = "Contact me by email"

        if self.instance.is_cleaner:
            self.fields["cleaner_preferred_districts"].widget.attrs["rows"] = 3
            cleaner_preferred_districts = Field("cleaner_preferred_districts")
            cleaner_preferred_service_types = Field("cleaner_preferred_service_types")
        else:
            cleaner_preferred_districts = None
            cleaner_preferred_service_types = None
            del self.fields["cleaner_preferred_districts"]
            del self.fields["cleaner_preferred_service_types"]

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Field("first_name"),
            Field("last_name"),
            Field("description"),
            Field("phone"),
            Field("image", template="utils/image_field_widget.html"),
            Field("is_contact_by_sms"),
            Field("is_contact_by_email"),
            cleaner_preferred_districts,
            cleaner_preferred_service_types,
            Div(
                HTML(f"<a href='#' onclick='history.back()' class='btn btn-secondary me-1'>Back</a>"),
                Submit('submit', 'Save', css_class="btn btn-primary text-uppercase"),
                css_class="text-center"
            )
        )


class UserVerificationDocumentForm(forms.ModelForm):

    class Meta:
        model = UserVerificationDocument
        fields = ("file",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.layout.append(
            Div(
                HTML(f"<a href='{reverse('verification')}' class='btn btn-secondary me-1'>Back</a>"),
                Submit('submit', 'Save', css_class="btn btn-primary text-uppercase"),
                css_class="text-center"
            )
        )