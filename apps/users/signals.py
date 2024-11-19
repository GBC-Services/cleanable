from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.account.signals import email_confirmed, user_logged_in
from django.db import transaction
from .models import User, UserSession
from apps.bookings.models import Booking
from apps.cleaners.models import CompanyCleanerInvite


@receiver(post_save, sender=User, dispatch_uid='user_post_save')
def user_post_save(sender, instance, created, **kwargs):
    pass

    """The code below moved to log in signal handler function"""
    # if created and instance.role == instance.ROLE_CLEANER:
    #     CompanyCleanerInvite.objects.filter(email=instance.email, company=instance.company, is_active=True, user__isnull=True)\
    #         .update(user=instance, is_active=False)


@receiver(user_logged_in)
def login_logger(request, user, **kwargs):

    CompanyCleanerInvite.objects.filter(email=user.email, company=user.company, is_active=True, user__isnull=True) \
        .update(user=user, is_active=False)

    if not request.session.session_key:
        request.session.create()
    session_id = request.session.session_key
    email = user.email
    booking_uuids = Booking.objects.filter(stripe_email__iexact=email, client__isnull=True)\
        .values_list("user_session__uuid", flat=True)

    """ToDo: session id part of Q will not work, because session id are changed with log in.
    If this is still needed, custom SESSION_ENGINE in settings could be a solution. Custom session class
    will update UserSession with a new key based on the old one.
    https://stackoverflow.com/questions/13978828/django-session-key-changing-upon-authentication
    """
    user_sessions = UserSession.objects.filter(Q(user__isnull=True, session_id=session_id) | Q(user__isnull=True, uuid__in=booking_uuids))
    for user_session in user_sessions.iterator():
        # print(f"user session: {user_session.id}")
        user_session.user = user
        user_session.save(force_update=True)
        user_session.booking_set.filter(client__isnull=True).update(client=user)
        user_session.place_set.filter(client__isnull=True).update(client=user)


@receiver(email_confirmed)
def email_confirmed_(request, email_address, **kwargs):
    """email address is the instance of django-allauth's model EmailAddress.
    Notification email sending can be put here to notify that there is a new sign up with a confirmed email address
    """
    print("email confirmed")

    # if not request.session.session_key:
    #     request.session.create()
    # session_id = request.session.session_key
    # print(f"session id: {session_id}")
    #
    # user = email_address.user
    # email = user.email
    # booking_uuids = Booking.objects.filter(stripe_email__iexact=email, client__isnull=True).values_list("user_session__uuid", flat=True)
    #
    # print(UserSession.objects.filter(user__isnull=True, session_id=session_id))

    # """ToDo: session id part of Q will not work, because session id are changed with log in.
    # If this is still needed, custom SESSION_ENGINE in settings could be a solution. Custom session class
    # will update UserSession with a new key based on the old one.
    # https://stackoverflow.com/questions/13978828/django-session-key-changing-upon-authentication
    # """
    # user_sessions = UserSession.objects.filter(Q(user__isnull=True, session_id=session_id) | Q(user__isnull=True, uuid__in=booking_uuids))
    # for user_session in user_sessions.iterator():
    #     print(f"user session: {user_session.id}")
    #     user_session.user = user
    #     user_session.save(force_update=True)
    #     user_session.booking_set.filter(client__isnull=True).update(client=user)
    #     user_session.place_set.filter(client__isnull=True).update(client=user)
