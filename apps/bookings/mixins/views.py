from apps.users.models import UserSession
from django.urls import reverse, reverse_lazy
from django.views import generic
from django.conf import settings
from apps.bookings.models import Booking
from apps.bookings.forms import DiscountCodeForm
from django.http import HttpResponseRedirect
from django.contrib.sites.models import Site
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.utils.conversions import localize_timestamp, convert_dt_to_timestamp
import datetime

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class UserSessionMixin:

    def get_session_id(self, force_update=False):
        if force_update or not self.request.session.session_key:
            self.request.session.create()
        session_id = self.request.session.session_key
        return session_id

    def get_or_create_user_session(self):
        user_session = self.get_user_session()
        if user_session is None or not user_session.user is None:
            force_update = True if not user_session is None and not user_session.user is None else False
            session_id = self.get_session_id(force_update=force_update)
            user_session = UserSession.objects.create(session_id=session_id)
        return user_session

    def get_user_session(self):
        session_id = self.get_session_id()
        try:
            user_session = UserSession.objects.get(session_id=session_id, user=None)
        except UserSession.DoesNotExist:
            user_session = None
        return user_session


class StripeMixins(generic.DetailView, generic.FormView):
    template_name = "bookings/checkout.html"
    model = Booking
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    form_class = DiscountCodeForm

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.paymeny_status == self.object.PAYMENT_STATUS_FULLY_PAID:
            return HttpResponseRedirect(self.object.get_successful_payment_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return self.request.META.get("HTTP_REFERER", "/")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.payment_intent = self.get_payment_intent()
        self.save_payment_intent_id(self.payment_intent["id"])
        context["stripe_public_key"] = settings.STRIPE_PUBLIC_KEY
        context["payment_intent_secret"] = self.payment_intent["client_secret"]
        context["successful_payment_url"] = self.get_successful_payment_full_url()
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        discount_code = data.get("discount_code")
        if discount_code:
            self.get_object().apply_discount_code(discount_code)
        return HttpResponseRedirect(self.request.META.get("HTTP_REFERER", "/"))

    def get_successful_payment_full_url(self):
        current_site = Site.objects.get_current()
        domain = current_site.domain
        url = self.get_object().get_successful_payment_url()
        url = f"{settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL}://{domain}{url}"
        return url

    def save_payment_intent_id(self, payment_intent_id):
        self.object.stripe_payment_intent_id = payment_intent_id
        self.object.save(force_update=True)
        return True


class CheckoutViewMixin(StripeMixins):

    def get_payment_intent(self):
        booking = self.get_object()
        user = self.request.user
        if booking.stripe_customer_id:
            customer_id = booking.stripe_customer_id
        elif user.is_authenticated:
            customer = stripe.Customer.create(email=user.email)
            customer_id = customer["id"]
        else:
            customer_id = None

        intent = stripe.PaymentIntent.create(customer=customer_id,
                                             amount=int(float(booking.total_fee_final)*100),
                                             currency="usd",
                                             automatic_payment_methods={
                                                "enabled": True,
                                             })
        return intent
