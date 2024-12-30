from django.db import models
from apps.utils.models import BaseModel, BaseDictModel
from apps.bookings.models import Booking
from apps.cleanings.models import Cleaning
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth import get_user_model
UserModel = get_user_model()
from django.utils import timezone
from django.conf import settings
from twilio.rest import Client
from django import forms
from apps.utils.emails_sending import EmailsSending

client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


class NotificationTemplate(BaseDictModel):
    CHANNEL_SMS = 10
    CHANNEL_EMAIL = 20
    CHANNELS = (
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_EMAIL, "Email")
    )
    channel = models.PositiveIntegerField(choices=CHANNELS, blank=True, null=True, default=None)
    subject = models.CharField(max_length=128, null=True, default=None)
    text = models.TextField()

    def clean(self):
        super().clean()
        if self.channel == self.CHANNEL_SMS and len(self.text) > 12:
            forms.ValidationError("Sms text should not exceed 256 symbols")

    def send(self, user, booking=None, cleaning=None):
        email, phone = None, None
        if cleaning:
            booking = cleaning.booking
        print("send")
        print(self.channel == self.CHANNEL_SMS)
        print(self.channel == self.CHANNEL_EMAIL)
        print("===")

        if self.channel == self.CHANNEL_SMS:
            phone = user.phone
        elif self.channel == self.CHANNEL_EMAIL:
            email = user.email

        notification = Notification.objects.create(user=user, booking=booking, cleaning=cleaning, template=self,
                                                   email=email, phone=phone)
        is_send = False
        if self.channel == self.CHANNEL_SMS and phone:
            is_send = self.send_sms(phone)
        elif self.channel == self.CHANNEL_EMAIL and email:
            is_send = self.send_email(email)
        notification.is_send = is_send
        notification.save(force_update=True)
        return True

    def send_sms(self, phone):
        # message = client.messages.create(
        #     to=phone,
        #     from_=settings.TWILIO_PHONE_FROM,
        #     body=self.text
        # )
        print("sms sent")
        # print(message)
        # print(message.sid)
        return True

    def send_email(self, email):
        try:
            to_emails = [email]
            EmailsSending().send(self.subject, self.text, to_emails=to_emails)
            return True
        except:
            return False

    def check_duplicate(self, cleaning):
        cooloff_seconds = settings.DUPLICATED_NOTIFICATION_COOLOFF_SECONDS
        last_notification = Notification.objects.filter(cleaning=cleaning).last()
        if last_notification and last_notification.template == self \
                and (last_notification.created - timezone.now()).total_seconds() < cooloff_seconds:
            return True
        else:
            return False


class Notification(BaseModel):
    user = models.ForeignKey(UserModel, blank=True, null=True, default=None, on_delete=models.CASCADE)
    booking = models.ForeignKey(Booking, blank=True, null=True, default=None, on_delete=models.CASCADE)
    cleaning = models.ForeignKey(Cleaning, blank=True, null=True, default=None, on_delete=models.CASCADE)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE)
    email = models.EmailField(blank=True, null=True, default=None)
    phone = PhoneNumberField(blank=True, null=True, default=None)
    is_send = models.BooleanField(default=False)
