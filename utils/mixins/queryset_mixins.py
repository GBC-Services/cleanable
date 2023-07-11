from bookings.models import Booking


class CleaningsMixin:

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_general_admin:
            return qs
        elif user.is_manager:
            return user.company.get_cleanings()
        elif user.is_cleaner:
            return user.get_cleanings()
        else:
            return self.model.objects.none()


class PlacesMixin:

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_general_admin:
            return qs
        elif user.is_client:
            return qs.filter(client=user)
        else:
            return self.model.objects.none()


class ClientMixin:

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_general_admin:
            return qs
        elif user.is_manager:
            client_ids = user.company.get_client_ids()
            return qs.filter(id__in=client_ids)
        elif user.is_client:
            return qs.filter(id=user.id)
        else:
            return self.model.objects.none()


class CompaniesMixin:

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_general_admin:
            return qs
        elif user.is_manager:
            return qs.filter(id=user.company.id)
        else:
            return self.model.objects.none()

    def get_object(self, queryset=None):
        user = self.request.user
        if user.is_manager:
            return user.company
        else:
            return super().get_object(queryset)


class BookingsMixin:

    def get_queryset(self):
        """Show bookings only to the general admin (all bookings) or a client (his own bookings).
        Company manager and cleaners will deal with "Cleaning" instance, because it can be more than cleaning for 1 booking:
        if a cleaning is remade or if it is a booking for a regular cleaning with many cleanings withing it
        (this could be implemented later)."""
        user = self.request.user
        qs = super().get_queryset().order_by("-id")
        if user.is_authenticated:
            if user.is_general_admin:
                return qs
            elif user.is_client:
                return qs.filter(client=user)
            else:
                return self.model.objects.none()
        else:
            if not user.is_authenticated and not getattr(self, "user_session", None) is None:
                return qs.filter(client__isnull=True, user_session=self.user_session)
            else:
                return self.model.objects.none()


class NonAuthBookingMixin:

    def get_booking(self):
        return self.user_session.booking_set.filter(client=None, status=Booking.STATUS_NEW).last()


class CleanerMixin:

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_general_admin:
            return qs
        else:
            return qs.filter(company=user.company)

    def get_object(self, queryset=None):
        user = self.request.user
        if user.is_cleaner:
            return user
        elif user.is_general_admin:
            return super().get_object(queryset=queryset)