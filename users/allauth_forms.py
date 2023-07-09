from django import forms
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from django.utils.html import format_html
from django.contrib.sites.models import Site
from allauth.account.forms import LoginForm, ResetPasswordForm, SignupForm
from allauth.account.adapter import get_adapter
from allauth.account.utils import setup_user_email
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from captcha.fields import ReCaptchaField
from django.conf import settings
from django.utils.safestring import mark_safe
from cleaners.models import CompanyCleanerInvite
from companies.models import Company
from locations.models import ZipCode
from django.contrib.auth import get_user_model
UserModel = get_user_model()
current_site = Site.objects.get_current()
CURRENT_SITE_NAME = current_site.name


class CustomCheckbox(Field):
    template = 'account/custom_checkbox.html'


class CustomResetPasswordForm(ResetPasswordForm):

    def __init__(self, *args, **kwargs):
        super(CustomResetPasswordForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.fields['email'].label = False


class CustomLoginForm(LoginForm):

    def __init__(self, *args, **kwargs):
        super(CustomLoginForm, self).__init__(*args, **kwargs)
        self.fields['login'] = forms.CharField(required=True, widget=forms.TextInput(attrs={"placeholder": _("Email")}))
        self.fields['login'].label = False
        self.fields['password'].label = False
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column(Field('login', css_class="login-input"), css_class='form-group col-md-6 mb-0'),
                Column(Field('password', css_class="password-input"), css_class='form-group col-md-6 mb-0'),
                css_class=''
            ),
            Row(
                Submit('submit', 'Sign In', css_class="btn btn-primary btn-block text-uppercase")
            )
        )

    def user_credentials(self):
        """For Django axes"""
        """https://django-axes.readthedocs.io/en/latest/6_integration.html#integration-with-django-allauth"""
        credentials = super().user_credentials()
        credentials['login'] = credentials.get('email') or credentials.get('username')
        return credentials


class CustomSignupForm(SignupForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=True, label='Email Address',
                             widget=forms.EmailInput(attrs={'placeholder': _("Email address")}))
    password1 = forms.CharField(label=False,
                                widget=forms.PasswordInput(attrs={"placeholder": _("Password")}))
    password2 = forms.CharField(label=False, widget=forms.PasswordInput(attrs={"placeholder": _("Password again")}))
    company = forms.CharField()
    zip_code = forms.CharField(max_length=12)
    is_accepted_tos = forms.BooleanField(required=True, label=mark_safe(f'I accept '
                                                                        f'<a href="{reverse("terms_of_use")}" '
                                                                        f'target="_blank">Terms of Use</a>'))
    is_accepted_pp = forms.BooleanField(required=True, label=mark_safe(f'I accept '
                                                                       f'<a href="{reverse("privacy_policy")}" '
                                                                        f'target="_blank">Privacy Policy</a>'))
    is_accepted_emails = forms.BooleanField(required=False,
                                            label="Receive email updates about our service "
                                                  "and other related products (no third party emails)")

    field_order = ["first_name", "last_name", "email", "password1", "password2", "company", "zip_code",
                   "is_accepted_tos", "is_accepted_pp", "is_accepted_emails",]

    def __init__(self, *args, **kwargs):
        self.role = kwargs.pop("role") if kwargs.get("role") else None
        self.invite_id = kwargs.pop("invite_id") if kwargs.get("invite_id") else None
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_show_labels = True

        self.acceptable_roles_to_assign = {"company": UserModel.ROLE_MANAGER, "cleaner": UserModel.ROLE_CLEANER}

        if self.role != "company":
            del self.fields["company"]
            del self.fields["zip_code"]

        if settings.IS_CAPTCHA:
            self.fields["captcha"] = ReCaptchaField(label=False, required=True)
            captcha = Div(Field('captcha'), css_class="d-flex justify-content-center")
        else:
            captcha = None

        self.helper.layout = Layout(
            Div(
                Div(
                    Field('first_name', autocomplete='off', placeholder=_("First Name")),
                    css_class="col-lg-6"
                ),
                Div(
                    Field('last_name', autocomplete='off', placeholder=_("Last Name")),
                    css_class="col-lg-6"
                ),
                css_class="row"
            ),
            Field('email', placeholder=_("Email address")),
            Div(
                Div(Field('password1', autocomplete='off', placeholder=_("Password")),
                    css_class="col-lg-12"
                    ),
                Div(Field('password2', autocomplete='off', placeholder=_("Confirm password")),
                    css_class="col-lg-12"
                    ),
                css_class="row"
            ),
            Field("company"),
            Field("zip_code"),
            Field("is_accepted_tos"),
            Field("is_accepted_pp"),
            Field("is_accepted_emails"),
            captcha,
        )

    def save(self, request):
        is_accepted_emails = self.cleaned_data.get("is_accepted_emails")
        adapter = get_adapter(request)
        user = adapter.new_user(request)
        if self.role in self.acceptable_roles_to_assign:
            user.role = self.acceptable_roles_to_assign[self.role]
            if self.role == "cleaner":
                _, _, company = self.get_company_from_cleaner_invite_id(user.email)
                if not company is None:
                    user.company = company
            if self.role == "company":
                company_name = self.cleaned_data.get("company")
                zip_code = self.cleaned_data.get("zip_code")
                zip_code, _ = ZipCode.objects.get_or_create(value=zip_code)
                user.company = Company.objects.create(name=company_name, zip_code=zip_code)
        user.is_accepted_emails = is_accepted_emails
        adapter.save_user(request, user, self)
        self.custom_signup(request, user)
        setup_user_email(request, user, [])
        return user

    def get_company_from_cleaner_invite_id(self, email):
        invite_id = self.invite_id
        if not invite_id is None:
            try:
                cleaner_invite = CompanyCleanerInvite.objects.get(uuid=invite_id, is_active=True, user__isnull=True)
                if email.lower() == cleaner_invite.email.lower():
                    company = cleaner_invite.company
                    return "success", "OK!", company
                else:
                    return "error", "Invite for this email does not exist", None
            except CompanyCleanerInvite.DoesNotExist:
                return "error", "Error! Such invite does not exist", None
        else:
            return "error", "Error! Use provided invite link for signup", None  # improve this by saving invite_id to cache

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if self.role == "cleaner":
            status, message, company = self.get_company_from_cleaner_invite_id(email)
            if status == "error":
                raise forms.ValidationError(message)
        return email

    def clean_company(self):
        """For company signup as a manager. In other roles this field will be excluded."""
        company = self.cleaned_data.get("company")
        if Company.objects.filter(name=company).exists():
            raise forms.ValidationError("This company name is already taken!")
        return company