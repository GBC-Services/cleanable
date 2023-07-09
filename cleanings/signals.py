from .models import Cleaning, CleaningStatusChange
from django.db.models.signals import post_save
from django.dispatch import receiver
from notifications.utils import ProcessNotification


@receiver(post_save, sender=Cleaning, dispatch_uid='cleaning_post_save')
def cleaning_post_save(sender, instance, created, **kwargs):
    if instance.status != instance._original_fields.get("status"):
        CleaningStatusChange.objects.create(cleaning=instance, status=instance.status)
        if instance.status == instance.STATUS_COMPLETED:
            instance.booking.status = instance.booking.STATUS_COMPLETED
            instance.booking.save(force_update=True)
        ProcessNotification().send_if_needed(cleaning=instance)



