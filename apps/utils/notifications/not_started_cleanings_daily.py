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


if __name__ == "__main__":
    date = timezone.now() - datetime.timedelta(days=1)
    qs_kwargs = {"scheduled_start_dt__date": date}
    NotStartedCleanings().launch(qs_kwargs, date)
