import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'cleaning.settings'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
import django
django.setup()

from django.utils import timezone
import datetime
from django.conf import settings
from apps.cleanings.models import Cleaning
from apps.utils.emails_sending import EmailsSending
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.urls import reverse, reverse_lazy
from django.db import transaction


class NotStartedCleanings:

    def __init__(self):
        current_site = Site.objects.get_current()
        self.domain = current_site.domain

    def launch(self):
        dt_from = timezone.now()-datetime.timedelta(minutes=settings.NOT_STARTED_ALERTING_PERIOD_MINUTES)
        kwargs = dict(scheduled_start_dt__date=dt_from.date(), scheduled_start_dt__lte=dt_from,
                      real_start_dt__isnull=True)
        if settings.NOTIFICATION_EMAILS:
            cleanings = Cleaning.objects.filter(**kwargs)
            if cleanings.exists():
                with transaction.atomic():
                    cleanings.update(is_delayed=True)
                    subject = "Not started cleanings alert"
                    link = f"{self.domain}{reverse('general_cleanings_dashboard')}?date_from={dt_from.strftime('%m/%d/%Y')}"
                    context = dict(interval_dt=dt_from, cleanings_nmb=cleanings.count(), link=link)
                    email_body = render_to_string("utils/notifications/not_started_cleanings.html", context)
                    EmailsSending().send(subject=subject, email_body=email_body, to_emails=settings.NOTIFICATION_EMAILS)


if __name__ == "__main__":
    NotStartedCleanings().launch()
