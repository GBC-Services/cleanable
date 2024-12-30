import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'cleaning.settings'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
import django
django.setup()

from django.utils import timezone
import datetime
from django.conf import settings
from .not_started_cleanings import NotStartedCleanings


if __name__ == "__main__":
    dt_from = timezone.now()-datetime.timedelta(minutes=settings.NOT_STARTED_ALERTING_PERIOD_MINUTES)
    qs_kwargs = {"scheduled_start_dt__gte": dt_from}
    NotStartedCleanings().launch(qs_kwargs, dt_from.date())
