"""
Celery Application Configuration
==================================

Initializes the Celery app for the Cleanable platform.

Usage:
  • Worker:   ``celery -A cleaning worker -l INFO``
  • Beat:     ``celery -A cleaning beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler``
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cleaning.settings")

app = Celery("cleaning")

# Pull config from Django settings, prefixed with ``CELERY_``
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# ── Periodic Task Schedule (Celery Beat) ──────────────────────────────

app.conf.beat_schedule = {
    "scrub-old-gps-history-daily": {
        "task": "apps.iot.tasks.scrub_old_gps_history",
        "schedule": crontab(hour=3, minute=0),  # Run daily at 3:00 AM
        "args": (),
    },
}
