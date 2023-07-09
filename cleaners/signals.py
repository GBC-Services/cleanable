from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import SchedulePeriod


@receiver(post_save, sender=SchedulePeriod, dispatch_uid='schedule_period_post_save')
def schedule_period_post_save(sender, instance, created, **kwargs):
    if created:
        instance.create_schedule_time_slots()