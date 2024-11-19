from .models import Booking, BookingStatusChange
from apps.cleanings.models import Cleaning
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Booking, dispatch_uid='booking_post_save')
def booking_post_save(sender, instance, created, **kwargs):
    if instance.status != instance._original_fields["status"]:
        BookingStatusChange.objects.create(booking=instance, status=instance.status)
        if instance.status == instance.STATUS_CANCELLED_BY_SERVICE:
            for cleaning in instance.get_cleanings().filter(status__lt=Cleaning.STATUS_COMPLETED):
                cleaning.status = Cleaning.STATUS_CANCELLED_BY_SERVICE
                cleaning.save(force_update=True)
        if instance.status == instance.STATUS_CANCELLED_BY_CLIENT:
            for cleaning in instance.get_cleanings().filter(status__lt=Cleaning.STATUS_COMPLETED):
                cleaning.status = Cleaning.STATUS_CANCELLED_BY_CLIENT
                cleaning.save(force_update=True)