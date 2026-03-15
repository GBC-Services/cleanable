"""
Support & QA — API URL Configuration
======================================

Mounted at ``/api/v1/support/`` via the project API root.

Tickets:
  GET/POST  tickets/                     — list / create
  GET/PATCH tickets/<uuid>/              — detail / update
  POST      tickets/<uuid>/resolve/      — one-click resolve
  POST      tickets/<uuid>/messages/     — add message
  GET       tickets/stats/               — dashboard stats

Verification (QA):
  GET/POST  verify/                      — list / upload
  GET       verify/<uuid>/               — detail
  POST      verify/<uuid>/review/        — manual review

Privacy / GDPR:
  POST      purge-media/                 — GDPR purge all media for a Resident

Webhooks (CF Worker callbacks):
  POST      webhooks/triage/             — AI triage callback
  POST      webhooks/verify/             — vision QA callback
"""

from django.urls import path

from apps.support.api_views import (
    PurgeMediaView,
    TicketDetailView,
    TicketListCreateView,
    TicketMessageCreateView,
    TicketResolveView,
    TicketStatsView,
    TriageWebhookView,
    VerificationDetailView,
    VerificationListCreateView,
    VerificationReviewView,
    VerifyWebhookView,
)

urlpatterns = [
    # ── Tickets ───────────────────────────────────────────────────────
    path("tickets/", TicketListCreateView.as_view(), name="support-tickets"),
    path("tickets/stats/", TicketStatsView.as_view(), name="support-tickets-stats"),
    path("tickets/<uuid:uuid>/", TicketDetailView.as_view(), name="support-ticket-detail"),
    path("tickets/<uuid:uuid>/resolve/", TicketResolveView.as_view(), name="support-ticket-resolve"),
    path("tickets/<uuid:uuid>/messages/", TicketMessageCreateView.as_view(), name="support-ticket-messages"),

    # ── Verification (QA) ─────────────────────────────────────────────
    path("verify/", VerificationListCreateView.as_view(), name="support-verify-list"),
    path("verify/<uuid:uuid>/", VerificationDetailView.as_view(), name="support-verify-detail"),
    path("verify/<uuid:uuid>/review/", VerificationReviewView.as_view(), name="support-verify-review"),

    # ── Privacy / GDPR ────────────────────────────────────────────────
    path("purge-media/", PurgeMediaView.as_view(), name="support-purge-media"),

    # ── Webhooks (CF Worker callbacks) ────────────────────────────────
    path("webhooks/triage/", TriageWebhookView.as_view(), name="support-webhook-triage"),
    path("webhooks/verify/", VerifyWebhookView.as_view(), name="support-webhook-verify"),
]
