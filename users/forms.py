from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
from .models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Fieldset, ButtonHolder, Div, HTML
from string import Template
from django.utils.safestring import mark_safe
from django.forms import ImageField
from django.utils import timezone


class UserCreationForm(UserCreationForm):

    class Meta(UserCreationForm):
        model = User
        fields = ('email',)


class UserChangeForm(UserChangeForm):

    class Meta:
        model = User
        fields = ('email',)