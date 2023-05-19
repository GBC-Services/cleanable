from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from .models import CleaningRequest, Cleaning
from clients.models import Place
import datetime
from .mixins import CleaningMixin


class CleaningRequestForm(CleaningMixin, forms.ModelForm):
    """Displayed to the client"""
    date = forms.DateField(input_formats=["%m/%d/%Y"], widget=forms.DateInput(format="%m/%d/%Y"))
    time_from = forms.TimeField(input_formats=["%I:%M %p"])
    time_to = forms.TimeField(input_formats=["%I:%M %p"])

    class Meta:
        model = CleaningRequest
        fields = ["place", "cleaning_type", "regularity_type", "comments"]  # "scheduled_start_dt", "scheduled_end_dt",

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comments"].widget.attrs["rows"] = 3
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Field("place"),
            Field("cleaning_type"),
            Field("regularity_type"),
            Field("date"),
            Field("time_from"),
            Field("time_to"),
            Field("comments"),
            Row(
                Submit('submit', 'Submit', css_class="btn btn-primary btn-block text-uppercase")
            )
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        cleaned_data = self.cleaned_data
        date = cleaned_data.get("date")
        time_from = cleaned_data.get("time_from")
        time_to = cleaned_data.get("time_to")
        instance.scheduled_start_dt = datetime.datetime.combine(date, time_from)
        instance.scheduled_end_dt = datetime.datetime.combine(date, time_to)
        if commit:
            instance.save()
        return instance


class ClientCleaningForm(CleaningMixin, forms.ModelForm):

    class Meta:
        model = Cleaning
        fields = ["client_comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client_comments"].widget.attrs["rows"] = 3
        self.helper = FormHelper(self)


class CleanerCleaningForm(forms.ModelForm):

    class Meta:
        model = Cleaning
        fields = ["cleaner_comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cleaner_comments"].widget.attrs["rows"] = 3
        self.helper = FormHelper(self)


class ManagerCleaningForm(forms.ModelForm):

    class Meta:
        model = Cleaning
        fields = ["manager_comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager_comments"].widget.attrs["rows"] = 3
        self.helper = FormHelper(self)