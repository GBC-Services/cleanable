from django import forms
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
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
                Submit('submit', 'Sign In', css_class="btn btn-black btn-block text-uppercase")
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
    email = forms.EmailField(required=True, label='Email Address',
                             widget=forms.EmailInput(attrs={'placeholder': _("Email address")}))
    password1 = forms.CharField(label=False,
                                widget=forms.PasswordInput(attrs={"placeholder": _("Password")}))
    password2 = forms.CharField(label=False, widget=forms.PasswordInput(attrs={"placeholder": _("Password again")}))
    is_accepted_tos = forms.BooleanField(required=True, label=f'I accept <a href="{reverse("terms_of_use")}" '
                                                              f'target="_blank">Terms of Use</a>')
    is_accepted_pp = forms.BooleanField(required=True, label=f'I accept <a href="{reverse("privacy_policy")}" '
                                                             f'target="_blank">Privacy Policy</a>')
    is_accepted_emails = forms.BooleanField(required=False,
                                            label="Receive email updates about our service "
                                                  "and other related products (no third party emails)")

    field_order = ["first_name", "email", "password1", "password2", "is_accepted_tos",
                   "is_accepted_pp", "is_accepted_emails",]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

        self.helper.form_show_labels = True

        if settings.IS_CAPTCHA:
            self.fields["captcha"] = ReCaptchaField(label=False, required=True)
            captcha = Div(Field('captcha'), css_class="d-flex justify-content-center")
        else:
            captcha = None

        self.helper.layout = Layout(
            Div(
                Div(FloatingField('first_name', autocomplete='off', placeholder=_("First Name")),
                    css_class="col-lg-6 col-md-12"
                    ),
                css_class="form-row"
            ),
            FloatingField('email', placeholder=_("Email address")),
            Div(
                Div(FloatingField('password1', autocomplete='off', placeholder=_("Password")),
                    css_class="col-lg-6 col-md-12"
                    ),
                Div(FloatingField('password2', autocomplete='off', placeholder=_("Confirm password")),
                    css_class="col-lg-6 col-md-12"
                    ),
                css_class="form-row"
            ),
            captcha,
        )

    def save(self, request):
        is_accepted_emails = self.cleaned_data.get("is_accepted_emails")
        adapter = get_adapter(request)
        user = adapter.new_user(request)
        user.is_accepted_emails = is_accepted_emails
        adapter.save_user(request, user, self)
        self.custom_signup(request, user)
        setup_user_email(request, user, [])
        return user