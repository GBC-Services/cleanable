"""
Payroll URL Configuration
==========================

All endpoints are mounted under ``/api/v1/payroll/``.

Activity Statements
  GET  statements/                  — list (filterable)
  GET  statements/<uuid>/           — detail

Payroll Cycles
  GET  cycles/                      — list (filterable)
  GET  cycles/<uuid>/               — detail with line items
  POST cycles/<uuid>/close/         — close cycle & generate CSV
  GET  cycles/<uuid>/csv/           — download CSV
  POST cycles/<uuid>/payout/        — trigger Stripe Connect transfer
  POST cycles/<uuid>/hold/          — place payment hold

Tax Documents
  GET  tax-documents/               — list (filterable)
  POST tax-documents/               — upload (agency owner)
  POST tax-documents/<uuid>/review/ — approve/reject (fiscal auditor)
  DEL  tax-documents/<uuid>/        — soft-delete

Payment Holds
  POST holds/<uuid>/release/        — release a hold

Dashboard
  GET  stats/                       — fiscal auditor KPIs
"""

from django.urls import path

from . import api_views

urlpatterns = [
    # ── Activity Statements ───────────────────────────────────────────
    path(
        "statements/",
        api_views.ActivityStatementListView.as_view(),
        name="payroll-statements",
    ),
    path(
        "statements/<uuid:uuid>/",
        api_views.ActivityStatementDetailView.as_view(),
        name="payroll-statement-detail",
    ),

    # ── Payroll Cycles ────────────────────────────────────────────────
    path(
        "cycles/",
        api_views.PayrollCycleListView.as_view(),
        name="payroll-cycles",
    ),
    path(
        "cycles/<uuid:uuid>/",
        api_views.PayrollCycleDetailView.as_view(),
        name="payroll-cycle-detail",
    ),
    path(
        "cycles/<uuid:uuid>/close/",
        api_views.PayrollCycleCloseView.as_view(),
        name="payroll-cycle-close",
    ),
    path(
        "cycles/<uuid:uuid>/csv/",
        api_views.PayrollCycleCSVDownloadView.as_view(),
        name="payroll-cycle-csv",
    ),
    path(
        "cycles/<uuid:uuid>/payout/",
        api_views.PayrollCyclePayoutView.as_view(),
        name="payroll-cycle-payout",
    ),

    # ── Payment Holds ─────────────────────────────────────────────────
    path(
        "cycles/<uuid:cycle_uuid>/hold/",
        api_views.PaymentHoldCreateView.as_view(),
        name="payroll-hold-create",
    ),
    path(
        "holds/<uuid:uuid>/release/",
        api_views.PaymentHoldReleaseView.as_view(),
        name="payroll-hold-release",
    ),

    # ── Tax Documents ─────────────────────────────────────────────────
    path(
        "tax-documents/",
        api_views.TaxDocumentListView.as_view(),
        name="payroll-tax-documents",
    ),
    path(
        "tax-documents/<uuid:uuid>/review/",
        api_views.TaxDocumentReviewView.as_view(),
        name="payroll-tax-document-review",
    ),
    path(
        "tax-documents/<uuid:uuid>/",
        api_views.TaxDocumentDeleteView.as_view(),
        name="payroll-tax-document-delete",
    ),

    # ── Dashboard Stats ───────────────────────────────────────────────
    path(
        "stats/",
        api_views.FiscalDashboardStatsView.as_view(),
        name="payroll-stats",
    ),
]
