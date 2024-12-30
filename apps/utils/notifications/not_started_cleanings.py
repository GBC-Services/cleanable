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


class NotStartedCleanings:

    def launch(self, qs_kwargs, date):
        current_site = Site.objects.get_current()
        domain = current_site.domain
        if settings.NOTIFICATION_EMAILS:
            cleanings = Cleaning.objects.filter(**qs_kwargs)
            if cleanings.exists():
                subject = "Daily Summary for delayed cleanings"
                link = f"{domain}{reverse('general-dashboard')}?date_from={date}"
                context = dict(cleanings_nmb=cleanings.count(), link=link)
                email_body = render_to_string("utils/notifications/not_started_cleanings.html", context)
                EmailsSending().send(subject=subject, email_body=email_body, to_emails=settings.NOTIFICATION_EMAILS)

