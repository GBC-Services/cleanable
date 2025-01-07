from django.urls import reverse, reverse_lazy
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.http import JsonResponse
from apps.clients.models import Place
from apps.companies.models import Company
from apps.locations.models import ZipCode, RegionZipCode
from .models import DiscountCode, BookingZipCodeSearch, Booking
from .forms import (BookingForm, LimitedBookingForm, PlacesForm, PublicBookingZipCodeForm,
                    PublicBookingServicesSelectionForm,
                    PublicBookingDateTimeForm, PublicBookingAddressForm)
from .mixins.views import UserSessionMixin, CheckoutViewMixin
from apps.services.models import ServiceFee
from apps.cleanings.models import Cleaning
from apps.utils.mixins.access_mixins import (ClientAccessMixin, ClientOrNotAuthAccessMixin,
                                             GeneralAdminOrClientOrSupportAgentAccessMixin,
                                             GeneralAdminAccessMixin, GeneralAdminOrClientAccessMixin)
from apps.utils.mixins.queryset_mixins import BookingsMixin, NonAuthBookingMixin
from datetime import datetime

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class BookingsView(LoginRequiredMixin, GeneralAdminOrClientAccessMixin, BookingsMixin, generic.ListView):
    template_name = "bookings/bookings.html"
    model = Booking

    def get_queryset(self):
        return super().get_queryset().filter(place__isnull=False)


class BookingView(LoginRequiredMixin, GeneralAdminOrClientOrSupportAgentAccessMixin, BookingsMixin, generic.DetailView):
    model = Booking
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_template_names(self):
        user = self.request.user
        if user.is_general_admin or user.is_support_agent:
            return "bookings/booking_for_general_admin.html"
        elif user.is_client:
            return "bookings/booking_for_client.html"


class BookingCreateUpdateView(LoginRequiredMixin, SuccessMessageMixin, ClientAccessMixin, BookingsMixin,
                              generic.UpdateView):
    template_name = "bookings/booking_create_update.html"
    model = Booking
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Done!"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.place = self.get_place()
            if not self.place:
                return HttpResponseRedirect(reverse("place_selection"))

            """To prevent updating after if the booking was completed 
            and the score for the cleaner has been already given"""
            object = self.get_object()
            if not object is None and object.status == object.STATUS_COMPLETED and object.score_for_cleaner:
                return HttpResponseForbidden()

        return super().dispatch(request, *args, **kwargs)

    def get_place(self):
        place = None
        object = self.get_object()
        if object:
            place = object.place
        else:
            place_uuid = self.kwargs.get("place_uuid")
            if place_uuid:
                try:
                    place = Place.objects.get(uuid=place_uuid, client=self.request.user)
                except Place.DoesNotExist:
                    pass
        return place

    def get_object(self, queryset=None):
        try:
            self.object = super().get_object(queryset)
            return self.object
        except AttributeError:
            return None

    def get_form_class(self):
        if not self.object or self.object.status == self.object.STATUS_NEW:
            form_class = BookingForm
        else:
            form_class = LimitedBookingForm
        return form_class

    def form_valid(self, form):
        print(form)
        user = self.request.user

        current_object = self.get_object()
        print(f"current object: {current_object}")

        object = form.save(commit=False)
        if not current_object:
            object.client = user
            object.place_type = self.place.type
            object.place = self.place
        object.save()

        if not current_object:
            form.save_m2m()

            """Saving services"""
            services = form.cleaned_data.get("services")
            object.update_services(services)

        if not current_object:
            return HttpResponseRedirect(reverse("checkout", kwargs=dict(uuid=object.uuid)))
        else:
            return HttpResponseRedirect(object.get_absolute_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if not self.object or self.object.status == self.object.STATUS_NEW:
            kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        object = self.get_object()
        if object:
            initial["date"] = object.scheduled_start_dt.date()
            initial["time_from"] = object.scheduled_start_dt.time()
            initial["time_to"] = object.scheduled_end_dt.time()
        initial["place"] = self.place
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["place"] = self.place
        return context


class BookingCancelView(LoginRequiredMixin, ClientAccessMixin, BookingsMixin, generic.DetailView):
    template_name = "bookings/booking_for_client.html"
    model = Booking
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get(self, *args, **kwargs):
        self.get_object().cancel()
        return HttpResponseRedirect(reverse("bookings"))


class BookingCleaningAssignView(LoginRequiredMixin, GeneralAdminAccessMixin, BookingsMixin, generic.DetailView):
    model = Booking
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_company(self):
        return Company.objects.get(uuid=self.kwargs.get("company_uuid"))

    def get(self, *args, **kwargs):
        booking = self.get_object()
        cleaning = booking.get_last_cleaning()
        if not cleaning:
            cleaning = booking.create_cleaning()
        if not cleaning.status == cleaning.PAYMENT_STATUS_FULLY_PAID:
            messages.error(self.request, "Not assigned! This booking is not paid!")
        else:
            company = self.get_company()
            if not cleaning.company:
                cleaning.company = company
                cleaning.save(force_update=True)
            else:
                messages.error(self.request, "This booking is already assigned and active in another company!")
        return HttpResponseRedirect(booking.get_absolute_url())


class SendSpecialRequestForCleaningView(LoginRequiredMixin, GeneralAdminAccessMixin, BookingsMixin, generic.DetailView):
    model = Booking
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_company(self):
        return Company.objects.get(uuid=self.kwargs.get("company_uuid"))

    def get(self, *args, **kwargs):
        booking = self.get_object()
        if not booking.special_request:
            messages.error(self.request, "Special request is missing!")
            return HttpResponseRedirect(booking.get_absolute_url())
        company = self.get_company()
        if not Cleaning.objects.filter(booking=booking, status__lte=Cleaning.STATUS_NOT_COMPLETED).exists():
            booking.send_special_request_for_cleaning(company)
        else:
            messages.error(self.request, "Cleaning already exists!")
        return HttpResponseRedirect(booking.get_absolute_url())


class NewBookingPlaceSelectionView(LoginRequiredMixin, generic.TemplateView, generic.FormView):
    template_name = "bookings/new_booking_place_selection.html"
    form_class = PlacesForm

    def get_success_url(self, place_uuid):
        return reverse("booking_for_place_create", kwargs=dict(place_uuid=place_uuid))

    def get_form_kwargs(self):
        context = super().get_form_kwargs()
        context["user"] = self.request.user
        return context

    def form_valid(self, form):
        place = form.cleaned_data["place"]
        if place:
            return HttpResponseRedirect(self.get_success_url(place.uuid))
        else:
            super().form_valid(form)


class CheckoutView(LoginRequiredMixin, ClientAccessMixin, BookingsMixin, CheckoutViewMixin):
    pass


class SuccessfulPaymentView(ClientOrNotAuthAccessMixin, BookingsMixin, generic.DetailView, UserSessionMixin):
    template_name = "bookings/successful_payment.html"
    model = Booking
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            self.user_session = self.get_user_session()
            if not self.user_session:
                return HttpResponseRedirect(reverse("public_booking_step_1"))
        return super().dispatch(request, *args, **kwargs)

    def get(self, *args, **kwargs):
        obj = self.get_object()
        if not obj.payment_status == obj.PAYMENT_STATUS_FULLY_PAID:
            data = self.request.GET
            if data:
                payment_intent_id = data.get("payment_intent")
                payment_intent_client_secret = data.get("payment_intent_client_secret")
                payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                if payment_intent_id == obj.stripe_payment_intent_id \
                        and payment_intent_client_secret == payment_intent["client_secret"]:

                    obj.mark_paid(payment_intent)

        return super().get(*args, **kwargs)


class StripeReceiptView(LoginRequiredMixin, GeneralAdminOrClientAccessMixin, BookingsMixin, generic.DetailView):
    model = Booking
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get(self, *args, **kwargs):
        return HttpResponseRedirect(self.get_object().get_stripe_invoice_url())


class DiscountCodeForBookingView(generic.DetailView):

    def post(self, *args, **kwargs):
        discount_code = DiscountCode.objects.filter(is_active=True).last()
        text = f"<div class='h5'>Are you sure you want to leave the page?</div>"
        if discount_code:
            discount = f"{discount_code.value}%" if discount_code.is_percentage else f"{discount_code.value} USD"
            text += f"<br>Wait! Here is {discount} discount code: <b>{discount_code.code}</b>"
        return JsonResponse(dict(text=text))


class PublicBookingZipCodeView(generic.TemplateView, generic.FormView, UserSessionMixin):
    template_name = "bookings/not_auth_booking/zip_selection.html"
    form_class = PublicBookingZipCodeForm
    success_url = reverse_lazy("public_booking_step_2")

    def form_valid(self, form):
        zip_code = form.cleaned_data.get("zip_code")
        user_session = self.get_or_create_user_session()

        """Just for statistical purposes to see what zip codes where searched"""
        booking_zip_code_search = BookingZipCodeSearch.objects.create(zip_code=zip_code, user_session=user_session)
        try:
            region_zip_code = RegionZipCode.objects.get(zip_code=zip_code, is_active=True)
            if region_zip_code.region.get_fees_last_snapshot():
                booking_zip_code_search.is_service_available = True
                booking_zip_code_search.save(force_update=True)
                url = f"{self.get_success_url()}?zip_code={zip_code}"
                return HttpResponseRedirect(url)
            else:
                form.add_error("zip_code", "This area is out of the coverage at this moment, "
                                           "but it will be covered soon")
                return self.form_invalid(form)
        except RegionZipCode.DoesNotExist:
            form.add_error("zip_code", "This area is out of the coverage at this moment.")
            return self.form_invalid(form)


class PublicBookingServicesView(generic.TemplateView, generic.FormView, UserSessionMixin):
    template_name = "bookings/not_auth_booking/services_selection.html"
    form_class = PublicBookingServicesSelectionForm

    def dispatch(self, request, *args, **kwargs):
        self.user_session = self.get_user_session()
        if not self.user_session:
            return HttpResponseRedirect(reverse("public_booking_step_1"))
        zip_code = self.request.GET.get("zip_code")
        if not zip_code:
            return HttpResponseRedirect(reverse("public_booking_step_1"))
        self.service_fees = ZipCode.objects.get(value=zip_code).get_service_fees()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("public_booking_step_3")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["extra_service_fees"] = self.service_fees.filter(service__is_chore=True)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["service_fees"] = self.service_fees
        return kwargs

    def form_valid(self, form):
        cleaned_data = form.cleaned_data
        place_type = cleaned_data.get("place_type")
        area_size = cleaned_data.get("area_size")
        object, _ = Booking.objects.update_or_create(client=None, user_session=self.user_session,
                                                     status=Booking.STATUS_NEW,
                                                     payment_status=Booking.PAYMENT_STATUS_NOT_PAID,
                                                     defaults=dict(place_type=place_type, area_size=area_size))

        """Saving services"""
        base_service = form.cleaned_data.get("base_service")
        extra_services = self.get_selected_services(cleaned_data)

        if not base_service is None:
            base_service_fee = ServiceFee.objects.filter(uuid=base_service.uuid)
        else:
            base_service_fee = ServiceFee.objects.none()

        services = base_service_fee | extra_services
        if services.count() == 0:
            form.add_error(None, "You need to select at least 1 service to make a booking")
            return self.form_invalid(form)
        object.update_services(services)
        return super().form_valid(form)

    def get_selected_services(self, cleaned_data):
        service_fees_uuids = [str(item) for item in self.service_fees.values_list("uuid", flat=True)]
        selected_service_fees = list()
        for k, v in cleaned_data.items():
            if v == "Yes":
                if k.startswith("extra_service_"):
                    extra_service_fee_uuid = k.split("extra_service_")[1]
                    if extra_service_fee_uuid in service_fees_uuids:
                        selected_service_fees.append(extra_service_fee_uuid)
        selected_services = ServiceFee.objects.filter(uuid__in=selected_service_fees)
        return selected_services


class PublicBookingDateAndTimeView(generic.UpdateView, UserSessionMixin, NonAuthBookingMixin):
    template_name = "bookings/not_auth_booking/date_and_time_saving.html"
    form_class = PublicBookingDateTimeForm

    def dispatch(self, request, *args, **kwargs):
        self.user_session = self.get_user_session()
        if not self.user_session:
            return HttpResponseRedirect(reverse("public_booking_step_1"))
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.get_booking()

    def get_success_url(self):
        return reverse("public_booking_step_4")


class PublicBookingAddressView(generic.CreateView, UserSessionMixin, NonAuthBookingMixin):
    template_name = "bookings/not_auth_booking/address_saving.html"
    model = Place
    form_class = PublicBookingAddressForm

    def dispatch(self, request, *args, **kwargs):
        self.user_session = self.get_user_session()
        if not self.user_session:
            return HttpResponseRedirect(reverse("public_booking_step_1"))
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("public_booking_step_5")

    def get_initial(self):
        initial = super().get_initial()
        booking = self.get_booking()
        last_place = Place.objects.filter(user_session=self.user_session, type=booking.place_type).last()
        if not last_place is None:
            initial["city"] = last_place.city.name
            initial["state"] = last_place.state.name
            initial["zip_code"] = last_place.zip_code.value
        return initial

    def form_valid(self, form):
        """Preventing duplicating of the place object, 
        if the object with the same address already exists for the user_session"""
        booking = self.get_booking()
        cleaned_data = form.cleaned_data
        try:
            object = Place.objects.get(user_session=self.user_session, type=booking.place_type,
                                       address=cleaned_data.get("address"),
                                       apartment_nmb=cleaned_data.get("apartment_nmb"),
                                       state=cleaned_data.get("state"),
                                       city=cleaned_data.get("city"),
                                       zip_code=cleaned_data.get("zip_code"),
                                       client=None)
        except Place.DoesNotExist:
            object = form.save(commit=False)
            object.area_size = booking.area_size
            object.type = booking.place_type
            object.user_session = self.user_session
            object.save()

        booking.place = object
        booking.save(force_update=True)
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["mapbox_token"] = settings.MAPBOX_TOKEN
        context["step3"] = True
        return context


class PublicBookingCheckoutView(UserSessionMixin, CheckoutViewMixin, NonAuthBookingMixin):

    def dispatch(self, request, *args, **kwargs):
        self.user_session = self.get_user_session()
        if not self.user_session:
            return HttpResponseRedirect(reverse("public_booking_step_1"))
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.get_booking()


class ServicesForPropertyTypeView(UserSessionMixin, NonAuthBookingMixin, generic.View):

    def post(self, *args, **kwargs):
        response_data = dict()
        data = self.request.POST
        zip_code = data.get("zip_code")
        zip_code = ZipCode.objects.get(value=zip_code)
        """ToDo: to add a custom constraint for RegionZipCode to allow only one zip code 
        for a region with is_active=True"""
        try:
            region = RegionZipCode.objects.get(is_active=True, zip_code=zip_code).region
            place_type = data.get("place_type")
            base_services = None
            if int(place_type) == Place.PLACE_TYPE_APARTMENT:
                base_services = region.get_fixed_fee_and_extra_service_fees().filter(service__is_chore=False)
            elif int(place_type) == Place.PLACE_TYPE_HOUSE:
                base_services = region.get_area_based_and_extra_service_fees().filter(service__is_chore=False)

            if base_services:
                response_data["base_services"] = [dict(id=item.id, name=item.__str__(), fee=item.client_fee,
                                                       is_area_based_fee=item.service.is_area_based_fee)
                                                   for item in base_services.iterator()]
        except RegionZipCode.DoesNotExist:
            pass
        return JsonResponse(response_data)

