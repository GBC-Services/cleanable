from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from .models import Cleaning
from clients.models import Place
import datetime


class ClientCleaningForm(forms.ModelForm):

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


class CleanerAssignForm(forms.Form):

    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company")
        date = kwargs.pop("date")
        super().__init__(*args, **kwargs)
        self.fields["cleaner"] = forms.ChoiceField(choices=self.get_cleaner_choices(company, date), label=False)
        self.helper = FormHelper(self)
        self.helper.form_method = "POST"
        self.helper.form_class = "cleaner-assign-form"
        self.helper.layout = Layout(
            Div(
                Div(
                    Field("cleaner", template="cleanings/partials/no_bottom_margin_field.html"),
                    css_class="flex-fill w-100"
                ),
                HTML("<button class='btn btn-primary flex-fill ms-3'>Assign</button"),
                css_class="d-flex justify-content-start"
            )
        )

    def get_cleaner_choices(self, company, date):
        cleaner_choices = [(None, "Not Selected")]
        cleaners = company.get_cleaners()
        for cleaner in cleaners.iterator():
            is_available = cleaner.get_availability_for_date(date)
            if is_available:
                cleaner_choices.append((cleaner.uuid, cleaner.get_full_name()))
        return cleaner_choices


class CleaningsFilterForm(forms.Form):
    date = forms.DateField(required=False, label=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = "Get"
        self.helper.layout = Layout(
            Div(
                Div(
                    Field("date", template="cleanings/partials/no_bottom_margin_field.html", placeholder="Filter by Date"),
                    css_class="flex-fill w-100"
                ),
                HTML("<button type='submit' class='btn btn-primary ms-3'>Apply</button"),
                css_class="d-flex"
            )
        )


class CleaningIssueForm(forms.ModelForm):

    class Meta:
        model = Cleaning
        fields = ["cleaner_comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cleaner_comments"].widget.attrs["rows"] = 5
        self.fields["cleaner_comments"].label = "Your comments"
        self.helper = FormHelper(self)

        self.helper.layout.append(
            Div(
                Submit('submit', 'Submit', css_class="btn btn-primary btn-block text-uppercase"),
                css_class='text-center'
            )
        )


class MessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea(attrs=dict(rows=2)), label=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = "chat_message_form"
        self.helper.layout = Layout(
            Div(
                Div(
                    Field("message", template="cleanings/partials/no_bottom_margin_field.html", placeholder="Write your message here"),
                    css_class="flex-fill w-100"
                ),
                Submit('submit', 'Send', css_class="btn btn-primary btn-block text-uppercase"),
                css_class="d-flex"
            )
        )