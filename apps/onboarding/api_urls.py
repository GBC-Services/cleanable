"""
Onboarding & Contracting — URL Configuration
================================================

Mounted under /api/v1/onboarding/ via the main API urlconf.
"""

from django.urls import path
from apps.onboarding import api_views

urlpatterns = [
    # ── Fuzzy Match & Approval ────────────────────────────────────────
    path(
        "fuzzy-match/",
        api_views.FuzzyMatchAgencyView.as_view(),
        name="onboarding-fuzzy-match",
    ),
    path(
        "request-approval/",
        api_views.RequestApprovalView.as_view(),
        name="onboarding-request-approval",
    ),
    path(
        "approval-requests/",
        api_views.ApprovalRequestListView.as_view(),
        name="onboarding-approval-list",
    ),
    path(
        "approval-requests/<uuid:uuid>/action/",
        api_views.ApprovalActionView.as_view(),
        name="onboarding-approval-action",
    ),

    # ── Service Areas (Geofence) ──────────────────────────────────────
    path(
        "service-areas/",
        api_views.ServiceAreaListCreateView.as_view(),
        name="onboarding-service-areas-list",
    ),
    path(
        "service-areas/<uuid:uuid>/",
        api_views.ServiceAreaDetailView.as_view(),
        name="onboarding-service-areas-detail",
    ),

    # ── Coverage Check ────────────────────────────────────────────────
    path(
        "check-coverage/",
        api_views.CheckCoverageView.as_view(),
        name="onboarding-check-coverage",
    ),

    # ── Contracts ─────────────────────────────────────────────────────
    path(
        "contracts/generate/",
        api_views.ContractGenerateView.as_view(),
        name="onboarding-contract-generate",
    ),
    path(
        "contracts/",
        api_views.ContractListView.as_view(),
        name="onboarding-contract-list",
    ),
    path(
        "contracts/<uuid:uuid>/",
        api_views.ContractDetailView.as_view(),
        name="onboarding-contract-detail",
    ),
    path(
        "contracts/<uuid:uuid>/sign/",
        api_views.ContractSignView.as_view(),
        name="onboarding-contract-sign",
    ),
]
