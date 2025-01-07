import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'cleaning.settings'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
import django
django.setup()

from django.utils import timezone
import datetime
from django.conf import settings
from apps.utils.notifications.not_started_cleanings import NotStartedCleanings


from django.utils import timezone
import datetime
from django.conf import settings
from apps.cleanings.models import Cleaning
from apps.utils.emails_sending import EmailsSending
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.urls import reverse, reverse_lazy


class NotStartedCleaningsDailySummary:
    days_nmb = 0

    def launch(self):
        report_date = (timezone.now() - datetime.timedelta(days=self.days_nmb)).date()
        kwargs = dict(scheduled_start_dt__date=report_date, is_delayed=True)

        current_site = Site.objects.get_current()
        domain = current_site.domain

        if settings.NOTIFICATION_EMAILS:
            cleanings = Cleaning.objects.filter(**kwargs)
            if cleanings.exists():
                subject = "Daily summary for not started cleanings"
                link = f"{domain}{reverse('general_cleanings_dashboard')}?date_from={report_date}"
                context = dict(report_date=report_date, cleanings_nmb=cleanings.count(), link=link)
                email_body = render_to_string("utils/notifications/not_started_cleanings_daily_summary.html", context)
                EmailsSending().send(subject=subject, email_body=email_body, to_emails=settings.NOTIFICATION_EMAILS)


if __name__ == "__main__":
    NotStartedCleaningsDailySummary().launch()
