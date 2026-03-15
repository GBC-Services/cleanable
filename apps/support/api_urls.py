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

Complaints (Resolution Pipeline):
  GET/POST  complaints/                  — list / create (Resident submits)
  GET       complaints/stats/            — dashboard stats
  GET/PATCH complaints/<uuid>/           — detail / update
  POST      complaints/<uuid>/acknowledge/ — Support Architect acknowledges
  POST      complaints/<uuid>/refund/    — execute refund (partial/full)
  POST      complaints/<uuid>/redo/      — schedule re-cleaning
  POST      complaints/<uuid>/blacklist/ — cancel & blacklist agency
  POST      complaints/<uuid>/note/      — add internal note
  GET       complaints/<uuid>/notifications/ — notification log

Blacklist:
  GET       blacklist/                   — list all blacklisted agencies

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
from apps.support.resolution_views import (
    AddNoteView,
    BlacklistListView,
    CancelBlacklistView,
    ComplaintAcknowledgeView,
    ComplaintDetailView,
    ComplaintListCreateView,
    ComplaintNotificationsView,
    ComplaintStatsView,
    RefundView,
    ScheduleRedoView,
)

urlpatterns = [
    # ── Tickets ───────────────────────────────────────────────────────
    path("tickets/", TicketListCreateView.as_view(), name="support-tickets"),
    path("tickets/stats/", TicketStatsView.as_view(), name="support-tickets-stats"),
    path("tickets/<uuid:uuid>/", TicketDetailView.as_view(), name="support-ticket-detail"),
    path("tickets/<uuid:uuid>/resolve/", TicketResolveView.as_view(), name="support-ticket-resolve"),
    path("tickets/<uuid:uuid>/messages/", TicketMessageCreateView.as_view(), name="support-ticket-messages"),

    # ── Complaints (Resolution Pipeline) ──────────────────────────────
    path("complaints/", ComplaintListCreateView.as_view(), name="support-complaints"),
    path("complaints/stats/", ComplaintStatsView.as_view(), name="support-complaints-stats"),
    path("complaints/<uuid:uuid>/", ComplaintDetailView.as_view(), name="support-complaint-detail"),
    path("complaints/<uuid:uuid>/acknowledge/", ComplaintAcknowledgeView.as_view(), name="support-complaint-acknowledge"),
    path("complaints/<uuid:uuid>/refund/", RefundView.as_view(), name="support-complaint-refund"),
    path("complaints/<uuid:uuid>/redo/", ScheduleRedoView.as_view(), name="support-complaint-redo"),
    path("complaints/<uuid:uuid>/blacklist/", CancelBlacklistView.as_view(), name="support-complaint-blacklist"),
    path("complaints/<uuid:uuid>/note/", AddNoteView.as_view(), name="support-complaint-note"),
    path("complaints/<uuid:uuid>/notifications/", ComplaintNotificationsView.as_view(), name="support-complaint-notifications"),

    # ── Blacklist ──────────────────────────────────────────────────────
    path("blacklist/", BlacklistListView.as_view(), name="support-blacklist"),

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
