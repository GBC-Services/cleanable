from .models import Cleaning, CleaningStatusChange
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.notifications.utils import ProcessNotification


@receiver(post_save, sender=Cleaning, dispatch_uid='cleaning_post_save')
def cleaning_post_save(sender, instance, created, **kwargs):
    if created and instance.booking.get_is_regular():
        instance.create_invoice()

    if instance.company and not instance._original_fields["company"]:
        booking = instance.booking
        booking.status = booking.STATUS_IN_WORK
        booking.save(force_update=True)

    if instance.payment_status != instance._original_fields["payment_status"]:
        booking = instance.booking
        booking.payment_status = instance.payment_status
        booking.save(force_update=True)

    if created or instance.status != instance._original_fields.get("status"):
        CleaningStatusChange.objects.create(cleaning=instance, status=instance.status)
        if instance.status == instance.STATUS_COMPLETED:
            if instance.booking.get_is_regular():
                instance.booking.create_cleaning()
            else:
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



