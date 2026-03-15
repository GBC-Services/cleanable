"""
API URL Configuration
=====================

All endpoints are mounted under ``/api/v1/`` via the project root urlconf.

Router-registered viewsets
---------------------------
  admin/users/          — Platform Admin user management
  companies/            — read-only company listing
  cleanings/            — read-only cleaning records

ViewSet-as-view endpoints (manually wired for custom action routing)
----------------------------------------------------------------------
  locations/…           — geography hierarchy
  services/…            — service catalogue
  places/               — Resident CRUD for their places
  bookings/             — full booking lifecycle
  wallet/               — Service Pro digital wallet

IoT & Smart Home (under ``iot/``)
-----------------------------------
  iot/devices/…          — Connected smart-lock CRUD + OAuth
  iot/access-tokens/…    — Time-bound access codes
  iot/voice-links/…      — Voice-assistant platform links

Support & QA (under ``support/``)
-----------------------------------
  support/tickets/…      — AI-triaged support ticket CRUD
  support/verify/…       — Post-job spatial verification (QA)
  support/webhooks/…     — CF Worker callbacks (triage + vision)

Standalone views
-----------------
  webhooks/stripe/      — Stripe webhook receiver (no auth)
  webhooks/alexa/       — Alexa Skill webhook (no auth, validated)
  webhooks/siri/        — Siri Shortcuts webhook (Bearer JWT)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from . import views_domain
from apps.iot.views import AlexaWebhookView, SiriWebhookView

# ── Router ────────────────────────────────────────────────────────────

router = DefaultRouter()
router.register(r"admin/users", views.UserAdminViewSet, basename="admin-users")
router.register(r"companies", views_domain.CompanyViewSet, basename="companies")
router.register(r"cleanings", views_domain.CleaningViewSet, basename="cleanings")


# ── Location action URLs ──────────────────────────────────────────────

location_list = views_domain.LocationViewSet.as_view({"get": "list"})

location_countries = views_domain.LocationViewSet.as_view(
    {"get": "countries"}
)
location_states = views_domain.LocationViewSet.as_view({"get": "states"})
location_cities = views_domain.LocationViewSet.as_view({"get": "cities"})
location_zip_codes = views_domain.LocationViewSet.as_view(
    {"get": "zip_codes"}
)
location_regions = views_domain.LocationViewSet.as_view(
    {"get": "regions"}
)

# ── Service action URLs ───────────────────────────────────────────────

service_list = views_domain.ServiceViewSet.as_view(
    {"get": "list_services"}
)
service_fees = views_domain.ServiceViewSet.as_view({"get": "fees"})
service_apartment_plans = views_domain.ServiceViewSet.as_view(
    {"get": "apartment_plans"}
)
service_cleaning_types = views_domain.ServiceViewSet.as_view(
    {"get": "cleaning_types"}
)

# ── Place URLs ────────────────────────────────────────────────────────

place_list_create = views_domain.PlaceViewSet.as_view(
    {"get": "list", "post": "create"}
)
place_detail = views_domain.PlaceViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update"}
)

# ── Booking URLs ──────────────────────────────────────────────────────

booking_list_create = views_domain.BookingViewSet.as_view(
    {"get": "list", "post": "create"}
)
booking_detail = views_domain.BookingViewSet.as_view(
    {"get": "retrieve"}
)
booking_cancel = views_domain.BookingViewSet.as_view(
    {"post": "cancel"}
)
booking_modify = views_domain.BookingViewSet.as_view(
    {"patch": "modify"}
)

# ── Wallet URLs ───────────────────────────────────────────────────────

wallet_dashboard = views_domain.WalletViewSet.as_view(
    {"get": "list"}
)
wallet_payout = views_domain.WalletViewSet.as_view(
    {"post": "payout"}
)
wallet_transactions = views_domain.WalletViewSet.as_view(
    {"get": "transactions"}
)


urlpatterns = [
    # ── Health ────────────────────────────────────────────────────────
    path("health/", views.HealthCheckView.as_view(), name="api-health"),

    # ── Auth ──────────────────────────────────────────────────────────
    path("auth/register/", views.RegisterView.as_view(), name="api-register"),
    path("auth/login/", views.LoginView.as_view(), name="api-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="api-logout"),
    path("auth/token/", views.CustomTokenObtainPairView.as_view(), name="api-token"),
    path(
        "auth/token/refresh/",
        views.CustomTokenRefreshView.as_view(),
        name="api-token-refresh",
    ),
    path("auth/me/", views.MeView.as_view(), name="api-me"),

    # ── Locations ─────────────────────────────────────────────────────
    path("locations/countries/", location_countries, name="locations-countries"),
    path("locations/states/", location_states, name="locations-states"),
    path("locations/cities/", location_cities, name="locations-cities"),
    path("locations/zip-codes/", location_zip_codes, name="locations-zip-codes"),
    path("locations/regions/", location_regions, name="locations-regions"),

    # ── Services ──────────────────────────────────────────────────────
    path("services/list/", service_list, name="services-list"),
    path("services/fees/", service_fees, name="services-fees"),
    path(
        "services/apartment-plans/",
        service_apartment_plans,
        name="services-apartment-plans",
    ),
    path(
        "services/cleaning-types/",
        service_cleaning_types,
        name="services-cleaning-types",
    ),

    # ── Places ────────────────────────────────────────────────────────
    path("places/", place_list_create, name="places-list-create"),
    path("places/<int:pk>/", place_detail, name="places-detail"),

    # ── Bookings ──────────────────────────────────────────────────────
    path("bookings/", booking_list_create, name="bookings-list-create"),
    path("bookings/<int:pk>/", booking_detail, name="bookings-detail"),
    path("bookings/<int:pk>/cancel/", booking_cancel, name="bookings-cancel"),
    path("bookings/<int:pk>/modify/", booking_modify, name="bookings-modify"),

    # ── Wallet ────────────────────────────────────────────────────────
    path("wallet/", wallet_dashboard, name="wallet-dashboard"),
    path("wallet/payout/", wallet_payout, name="wallet-payout"),
    path("wallet/transactions/", wallet_transactions, name="wallet-transactions"),

    # ── Webhooks ──────────────────────────────────────────────────────
    path(
        "webhooks/stripe/",
        views_domain.StripeWebhookView.as_view(),
        name="webhooks-stripe",
    ),
    path(
        "webhooks/alexa/",
        AlexaWebhookView.as_view(),
        name="webhooks-alexa",
    ),
    path(
        "webhooks/siri/",
        SiriWebhookView.as_view(),
        name="webhooks-siri",
    ),

    # ── IoT & Smart Home ──────────────────────────────────────────────
    path("iot/", include("apps.iot.urls")),

    # ── Support & QA ──────────────────────────────────────────────────
    path("support/", include("apps.support.api_urls")),

    # ── Router (admin, companies, cleanings, etc.) ────────────────────
    path("", include(router.urls)),
]
