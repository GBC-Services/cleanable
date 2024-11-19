from django.urls import include, path
from . import views


urlpatterns = [
    path('bookings', views.BookingsView.as_view(), name='bookings'),
    path('booking/view/<uuid>', views.BookingView.as_view(), name='booking'),
    path('booking/create', views.BookingCreateUpdateView.as_view(), name='booking_create'),
    path('booking-for-place/create/<place_uuid>', views.BookingCreateUpdateView.as_view(),
         name='booking_for_place_create'),
    path('booking/update/<uuid>', views.BookingCreateUpdateView.as_view(), name='booking_update'),
    path('booking/cancel/<uuid>', views.BookingCancelView.as_view(), name='booking_cancel'),
    path('booking/assign/<uuid>/<company_uuid>', views.BookingCleaningAssignView.as_view(), name='booking_assign'),
    path('send-special-request-for-cleaning/<uuid>/<company_uuid>', views.SendSpecialRequestForCleaningView.as_view(),
         name='send_special_request_for_cleaning'),

    path('place-selection', views.NewBookingPlaceSelectionView.as_view(), name='place_selection'),

    path('checkout/<uuid>', views.CheckoutView.as_view(), name='checkout'),
    path('successful-payment/<uuid>', views.SuccessfulPaymentView.as_view(), name='successful_payment'),
    path('stripe-reciept/<uuid>', views.StripeReceiptView.as_view(), name='stripe_receipt'),

    path('discount-code-for-booking/', views.DiscountCodeForBookingView.as_view(), name='discount_code_for_booking'),

    path('booking-process/check-service-coverage', views.PublicBookingZipCodeView.as_view(), name='public_booking_step_1'),
    path('booking-process/select-cleaning-services', views.PublicBookingServicesView.as_view(), name='public_booking_step_2'),
    path('booking-process/date-and-time-selection', views.PublicBookingDateAndTimeView.as_view(), name='public_booking_step_3'),
    path('booking-process/enter-address', views.PublicBookingAddressView.as_view(), name='public_booking_step_4'),
    path('booking-process/checkout', views.PublicBookingCheckoutView.as_view(), name='public_booking_step_5'),

    path('services-for-property-type', views.ServicesForPropertyTypeView.as_view(), name='services_for_property_type'),
]