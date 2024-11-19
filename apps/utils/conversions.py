import datetime
import calendar

from zoneinfo import ZoneInfo
from django.conf import settings
from datetime import datetime


def localize_timestamp(timestamp):
    print(1)
    local_tz = ZoneInfo(settings.TIME_ZONE)
    print(2)
    print(local_tz)
    print(type(local_tz))

    # Convert unix time to localtime
    if not timestamp:
        timestamp = datetime.now().timestamp()
        print(3)
        print(timestamp)
    localized_dt = datetime.fromtimestamp(timestamp,
                                          local_tz
                                          )
    print(localized_dt)
    return localized_dt


def convert_date_to_timestamp(val, is_in_miliseconds=False):
    """According to this thread https://stackoverflow.com/a/8778548,
    if we need to show a date as like it is UTC date to prevent its further
    transformations, some specific way of transferring to the unix timestamp should be used"""
    dt = datetime.datetime.combine(val, datetime.datetime.min.time())

    unixtime = int(calendar.timegm(dt.timetuple()))
    if is_in_miliseconds:
        unixtime *= 1000
    return unixtime


def convert_dt_to_timestamp(dt, is_in_miliseconds=False):
    """According to this thread https://stackoverflow.com/a/8778548,
        if we need to show a date as like it is UTC date to prevent its further
        transformations, some specific way of transferring to the unix timestamp should be used"""
    unixtime = int(calendar.timegm(dt.timetuple()))
    if is_in_miliseconds:
        unixtime *= 1000
    return unixtime
