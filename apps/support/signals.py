from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SupportTicket, SupportTicketStatusChange
from crequest.middleware import CrequestMiddleware


@receiver(post_save, sender=SupportTicket, dispatch_uid="support_ticket_post_save")
def support_ticket_post_save(sender, instance, created, **kwargs):
    if instance.status != instance._original_fields["status"]:
        request = CrequestMiddleware.get_request()
        user = request.user
        SupportTicketStatusChange.objects.create(support_ticket=instance, status=instance.status, user=user)
