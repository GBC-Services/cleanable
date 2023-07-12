from .models import Cleaning, CleaningStatusChange
from django.db.models.signals import post_save
from django.dispatch import receiver
from notifications.utils import ProcessNotification


@receiver(post_save, sender=Cleaning, dispatch_uid='cleaning_post_save')
def cleaning_post_save(sender, instance, created, **kwargs):
    if created or instance.status != instance._original_fields.get("status"):
        CleaningStatusChange.objects.create(cleaning=instance, status=instance.status)
        if instance.status == instance.STATUS_COMPLETED:
            instance.booking.status = instance.booking.STATUS_COMPLETED
            instance.booking.save(force_update=True)

        """A client can cancel only a booking, not a cleaning? At least now it is in bookings.signals"""
        if instance.status == instance.STATUS_CANCELLED_BY_COMPANY:
            instance.booking.status = instance.booking.STATUS_CANCELLED_BY_COMPANY
            instance.booking.save(force_update=True)
        elif instance.status == instance.STATUS_CANCELLED_BY_SERVICE:
            instance.booking.status = instance.booking.STATUS_CANCELLED_BY_SERVICE
            instance.booking.save(force_update=True)

        ProcessNotification().send_if_needed(cleaning=instance)



