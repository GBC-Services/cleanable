from django.db import models
from utils.models import BaseModel, BaseDictModel
from bookings.models import Booking
from cleanings.models import Cleaning
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth import get_user_model
UserModel = get_user_model()


class NotificationTemplate(BaseDictModel):
    CHANNEL_SMS = 10
    CHANNEL_EMAIL = 20
    CHANNELS = (
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_EMAIL, "Email")
    )
    channel = models.PositiveIntegerField(choices=CHANNELS, blank=True, null=True, default=None)
    text = models.TextField()

    def send(self, user, booking=None, cleaning=None):
        email, phone = None, None
        if cleaning:
            booking = cleaning.booking
        if self.channel == self.CHANNEL_SMS:
            phone = user.phone
        elif self.channel == self.CHANNEL_EMAIL:
            email = user.email
        notification = Notification.objects.create(user=user, booking=booking, cleaning=cleaning, template=self, email=email, phone=phone)
        if self.channel == self.CHANNEL_SMS and phone:
            pass
        elif self.channel == self.CHANNEL_EMAIL and email:
            pass
        notification.is_send = True
        notification.save(force_update=True)
        return True

    def check_duplicate(self, cleaning):
        return Notification.objects.filter(template=self, cleaning=cleaning).exists()


class Notification(BaseModel):
    user = models.ForeignKey(UserModel, blank=True, null=True, default=None, on_delete=models.CASCADE)
    booking = models.ForeignKey(Booking, blank=True, null=True, default=None, on_delete=models.CASCADE)
    cleaning = models.ForeignKey(Cleaning, blank=True, null=True, default=None, on_delete=models.CASCADE)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE)
    email = models.EmailField(blank=True, null=True, default=None)
    phone = PhoneNumberField(blank=True, null=True, default=None)
    is_send = models.BooleanField(default=False)
