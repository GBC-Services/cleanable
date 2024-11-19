from django import forms
from .models import SupportTicket, SupportTicketMessage
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Fieldset, ButtonHolder, Div, HTML
from django.urls import reverse


class SupportTicketForm(forms.ModelForm):

    class Meta:
        model = SupportTicket
        fields = ("booking", "category", "subject", "text",)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["booking"].queryset = user.get_bookings()
        self.fields["text"].widget.attrs["rows"] = 5

        self.helper = FormHelper(self)
        self.helper.layout.append(
            Div(
                HTML(f"<a href='{reverse('support_tickets')}' class='btn btn-secondary me-1'>Back</a>"),
                Submit('submit', 'Save', css_class="btn btn-primary text-uppercase"),
                css_class="text-center"
            )
        )


class SupportTicketMessageForm(forms.ModelForm):

    class Meta:
        model = SupportTicketMessage
        fields = ("text",)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["text"].widget.attrs["rows"] = 3
        self.fields["text"].label = False
        self.fields["text"].widget.attrs["placeholder"] = "Write you message here..."

        if user.is_general_admin or user.is_support_agent:
            self.fields["status"] = forms.ChoiceField(choices=SupportTicket.STATUSES)
            button_text = "Save"
            self.fields["text"].required = False
        else:
            button_text = "Submit"

        self.helper = FormHelper(self)
        self.helper.layout.append(
            Div(
                Submit("submit", button_text, css_class="btn btn-primary text-uppercase"),
                css_class="text-center"
            )
        )