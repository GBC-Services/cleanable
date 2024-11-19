from django.db import models
from apps.utils.models import BaseModel, BaseDictModel
from apps.locations.models import Region
from apps.bookings.models import Booking
from django.urls import reverse, reverse_lazy
from crequest.middleware import CrequestMiddleware
from django.contrib.auth import get_user_model
UserModel = get_user_model()


class Category(BaseDictModel):
    pass


class SupportTicket(BaseModel):
    STATUS_NEW = 10
    STATUS_IN_WORK = 20
    STATUS_RESOLVED = 30
    STATUS_CANCELLED_BY_USER = 40

    STATUSES = (
        (STATUS_NEW, "New"),
        (STATUS_IN_WORK, "In work"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CANCELLED_BY_USER, "Cancelled by user")
    )
    booking = models.ForeignKey(Booking, blank=True, null=True, default=None, on_delete=models.CASCADE)
    subject = models.CharField(max_length=256, blank=True, null=True, default=None)
    category = models.ForeignKey(Category, null=True, default=None, on_delete=models.CASCADE)
    text = models.TextField()
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(UserModel, blank=True, null=True, default=None,
                                    on_delete=models.CASCADE, related_name="support_tickets_assigned")
    status = models.PositiveIntegerField(choices=STATUSES, default=STATUS_NEW)
    comments = models.TextField(blank=True, null=True, default=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._original_fields = {}
        for field in ["status"]:
            try:
                self._original_fields[field] = getattr(self, field)
            except:
                pass

    def __str__(self):
        return f"{self.subject}"

    def save(self, *args, **kwargs):
        request = CrequestMiddleware.get_request()
        if not self.pk:
            self.user = request.user
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("support_ticket", kwargs=dict(uuid=self.uuid))

    def get_messages(self):
        return self.supportticketmessage_set.filter(is_active=True).order_by("-id")


class SupportTicketStatusChange(BaseModel):
    support_ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE)
    status = models.PositiveIntegerField(choices=SupportTicket.STATUSES)
    user = models.ForeignKey(UserModel, null=True, default=None, on_delete=models.SET_NULL)


class SupportTicketMessage(BaseModel):
    support_ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE)
    text = models.TextField()
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
