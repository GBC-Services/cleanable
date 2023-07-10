from django.conf import settings
from cleaners.models import SchedulePeriod


class ScheduleMixin:
    next_week = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        period = self.get_period()
        context["period"] = period
        context["time_slots"] = settings.TIME_SLOTS
        context["days"] = period.get_or_create_cleaner_schedule_data(user)
        return context

    def get_period(self):
        period_uuid = self.request.GET.get("period")
        if period_uuid:
            """Get any existing schedule period"""
            schedule_period = SchedulePeriod.objects.get(uuid=period_uuid)
        else:
            """Get or create a schedule period for the current or for the next week only"""
            schedule_period = SchedulePeriod().get_or_create_period(next_week=self.next_week)
        return schedule_period
