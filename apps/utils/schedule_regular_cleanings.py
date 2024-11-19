import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'cleaning.settings'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import django
django.setup()

import datetime

from apps.bookings.models import Booking
from apps.services.models import Service


class ScheduleRegularCleanings:
    """Backup method for scheduling cleanings.
    So far the other method for scheduling cleanings is used:
    they are scheduled when the previous cleaning is completed"""

    def launch(self):
        bookings = Booking.objects.filter(is_active=True, regularity_type=Service.REGULARITY_TYPE_REGULAR)
        for booking in bookings:
            print(booking)
            cleaning = booking.get_last_cleaning()
            if cleaning and cleaning.company:
                booking.create_cleaning(company=cleaning.company)


if __name__ == "__main__":
    ScheduleRegularCleanings().launch()
