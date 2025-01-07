from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Submit, HTML, Div, Row, Column
from crispy_bootstrap5.bootstrap5 import FloatingField
from crispy_forms.bootstrap import FormActions
from .models import Cleaning, SpecialCleaningRequest
from apps.clients.models import Place
from apps.bookings.mixins.forms import BookingOrCleaningDateTimeFormMixin
import datetime


class ClientCleaningForm(forms.ModelForm):

    class Meta:
        model = Cleaning
        fields = ["client_comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client_comments"].widget.attrs["rows"] = 3
        self.helper = FormHelper(self)

        self.helper.layout.append(
            Div(
                Submit('submit', 'Save', css_class="btn btn-primary btn-block text-uppercase"),
                css_class='text-center'
            )
        )


class CleanerCleaningForm(forms.ModelForm):

    class Meta:
        model = Cleaning
        fields = ["cleaner_comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cleaner_comments"].widget.attrs["rows"] = 3
        self.helper = FormHelper(self)

        self.helper.layout.append(
            Div(
                Submit('submit', 'Save', css_class="btn btn-primary btn-block text-uppercase"),
                css_class='text-center'
            )
        )


class ManagerCleaningForm(forms.ModelForm):

    class Meta:
        model = Cleaning
        fields = ["manager_comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager_comments"].widget.attrs["rows"] = 3
        self.helper = FormHelper(self)

        self.helper.layout.append(
            Div(
                Submit('submit', 'Save', css_class="btn btn-primary btn-block text-uppercase"),
                css_class='text-center'
            )
        )


class SupportAgentCleaningForm(BookingOrCleaningDateTimeFormMixin, forms.ModelForm):
    date = forms.DateField(input_formats=["%m/%d/%Y"], widget=forms.DateInput(format="%m/%d/%Y"))
    time_from = forms.TimeField(input_formats=["%I:%M %p"])
    time_to = forms.TimeField(input_formats=["%I:%M %p"])

    class Meta:
        model = Cleaning
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.scheduled_date:
            self.fields["date"].initial = self.instance.scheduled_date
        if self.instance.scheduled_start_dt:
            self.fields["time_from"].initial = self.instance.scheduled_start_dt.time()
        if self.instance.scheduled_end_dt:
            self.fields["time_to"].initial = self.instance.scheduled_end_dt.time()

        self.helper = FormHelper(self)

        self.helper.layout.append(
            Div(
                Submit('submit', 'Save', css_class="btn btn-primary btn-block text-uppercase"),
                css_class='text-center'
            )
        )


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
                    Field("date", template="cleanings/partials/no_bottom_margin_field.html",
                          placeholder="Filter by Date"),
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


class CleaningCommentOnlyForm(forms.ModelForm):
    score_for_cleaner = forms.IntegerField(min_value=1, max_value=5, label="Score for cleaner (1-5)")

    class Meta:
        model = Cleaning
        fields = ["client_comments", "score_for_cleaner", "feedback_for_cleaner"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if int(self.instance.status) != self.instance.STATUS_COMPLETED:
            del self.fields["score_for_cleaner"]
            del self.fields["feedback_for_cleaner"]
        else:
            del self.fields["client_comments"]

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Field("client_comments"),
            Field("score_for_cleaner"),
            Field("feedback_for_cleaner"),
            Div(
                HTML('<button onclick="history.back()" class="btn btn-secondary me-1">Back</button>'),
                Submit('submit', 'Save', css_class="btn btn-primary btn-block text-uppercase"),
                css_class="text-center"
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
                    Field("message", template="cleanings/partials/no_bottom_margin_field.html",
                          placeholder="Write your message here"),
                    css_class="flex-fill w-100"
                ),
                Submit('submit', 'Send', css_class="btn btn-primary btn-block text-uppercase"),
                css_class="d-flex"
            )
        )


class SpecialRequestForm(forms.ModelForm):

    class Meta:
        model = SpecialCleaningRequest
        fields = ["fee", "comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.fields["comments"].widget.attrs["rows"] = 3

        self.helper.layout.append(
            Div(
                HTML('<button onclick="history.back()" class="btn btn-secondary me-1">Back</button>'),
                Submit('submit', 'Confirm', css_class="btn btn-primary btn-block"),
                css_class='text-center'
            )
        )


class DatesForm(forms.Form):
    date_from = forms.DateField(required=False, input_formats=["%m/%d/%Y"], widget=forms.DateInput(format="%m/%d/%Y"))
    date_to = forms.DateField(required=False, input_formats=["%m/%d/%Y"], widget=forms.DateInput(format="%m/%d/%Y"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_from"].widget.attrs["placeholder"] = "Date From"
        self.fields["date_to"].widget.attrs["placeholder"] = "Date To"

        self.helper = FormHelper(self)
        self.helper.form_method = "GET"
        self.helper.form_show_labels = False
        self.helper.layout = Layout(
            Div(
                Div(Field("date_from", wrapper_class="me-1")),
                Div(Field("date_to", wrapper_class="me-1")),
                Div(HTML("<a href='/' class='btn btn-secondary btn-block text-uppercase me-1'>Clear</a>"),
                    css_class="mb-3"),
                Div(HTML("<button type='submit' class='btn btn-primary btn-block text-uppercase'>Apply</button>"),
                    css_class="mb-3"),
                css_class="d-flex justify-content-center align-items-end"
            )
        )
