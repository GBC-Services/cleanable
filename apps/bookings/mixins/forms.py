import datetime
from django import forms


class BookingOrCleaningDateTimeFormMixin:

    def save(self, commit=True):
        instance = super().save(commit=False)
        cleaned_data = self.cleaned_data
        date = cleaned_data.get("date")
        time_from = cleaned_data.get("time_from")
        time_to = cleaned_data.get("time_to")
        instance.scheduled_date = date
        instance.scheduled_start_dt = datetime.datetime.combine(date, time_from)
        instance.scheduled_end_dt = datetime.datetime.combine(date, time_to)
        if commit:
            instance.save()
        return instance

    def clean_time_to(self):
        time_from = self.cleaned_data.get("time_from")
        time_to = self.cleaned_data.get("time_to")
        if time_to <= time_from:
            raise forms.ValidationError('"time to" should be later than "time from" value')
        return time_to