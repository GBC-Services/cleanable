"""
Payroll & Fiscal Auditing Models
=================================

Activity Statements — per-job ledger cross-referencing agency pricing with
Service Pro wages.

Payroll Cycles — end-of-period aggregation with CSV export and Stripe
Connect payout triggering.

Tax Documents — W-9 / 1099 upload and compliance storage for agencies.

Payment Holds — Fiscal Auditor override to pause payouts when anomalies
are detected.
"""

import uuid as _uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.utils.models import BaseModel


class ActivityStatement(BaseModel):
    """
    Generated automatically after every completed cleaning job.

    Cross-references:
      • Agency's agreed pricing  → ``agency_fee``  (from CompanyServiceFee)
      • Service Pro's set wage   → ``pro_wage``    (stored at assignment time)
      • Platform margin          → ``platform_fee`` = agency_fee − pro_wage
    """

    cleaning = models.OneToOneField(
        "cleanings.Cleaning",
        on_delete=models.CASCADE,
        related_name="activity_statement",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="activity_statements",
    )
    agency = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="activity_statements",
    )
    service_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_statements",
    )

    # ── Financial snapshot at job completion ───────────────────────────
    client_charged = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Total amount charged to the Resident (booking.total_fee_final).",
    )
    agency_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Agency's agreed pricing from their CompanyServiceFee snapshot.",
    )
    pro_wage = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Service Pro's wage for this job (set by agency).",
    )
    platform_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Platform margin = client_charged − agency_fee.",
    )
    tip_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Tip from resident (passes through to Service Pro).",
    )

    # ── Service snapshot ──────────────────────────────────────────────
    service_names = models.TextField(
        blank=True, default="",
        help_text="Comma-separated service names at time of job.",
    )
    scheduled_date = models.DateField(
        blank=True, null=True,
        help_text="The date the cleaning was scheduled for.",
    )
    completed_at = models.DateTimeField(
        blank=True, null=True,
        help_text="When the cleaning was marked completed.",
    )

    # ── Payroll linkage ───────────────────────────────────────────────
    payroll_cycle = models.ForeignKey(
        "PayrollCycle",
        blank=True, null=True, default=None,
        on_delete=models.SET_NULL,
        related_name="line_items",
        help_text="The payroll cycle this statement was batched into.",
    )

    class Meta:
        ordering = ["-completed_at", "-created"]
        indexes = [
            models.Index(fields=["agency", "completed_at"],
                         name="idx_stmt_agency_date"),
            models.Index(fields=["service_pro", "completed_at"],
                         name="idx_stmt_pro_date"),
            models.Index(fields=["payroll_cycle"],
                         name="idx_stmt_cycle"),
        ]

    def __str__(self):
        return (
            f"ActivityStatement #{self.pk} — "
            f"{self.agency} → {self.service_pro} "
            f"(${self.agency_fee})"
        )


class PayrollCycle(BaseModel):
    """
    End-of-period aggregation per agency.

    Status flow:  open → processing → paid | held
    """

    STATUS_OPEN = "open"
    STATUS_PROCESSING = "processing"
    STATUS_PAID = "paid"
    STATUS_HELD = "held"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PAID, "Paid"),
        (STATUS_HELD, "Held"),
    ]

    agency = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="payroll_cycles",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )

    # ── Aggregated totals (computed at cycle close) ───────────────────
    total_jobs = models.PositiveIntegerField(default=0)
    total_client_charged = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    total_agency_fees = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    total_pro_wages = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    total_platform_fees = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    total_tips = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )

    # ── Stripe payout ─────────────────────────────────────────────────
    stripe_transfer_id = models.CharField(
        max_length=64, blank=True, null=True, default=None,
        help_text="Stripe Transfer ID (tr_…) for the agency payout.",
    )
    paid_at = models.DateTimeField(blank=True, null=True, default=None)

    # ── CSV export ────────────────────────────────────────────────────
    csv_file = models.FileField(
        upload_to="payroll/csv/", blank=True, null=True, default=None,
        help_text="Master Job Summary CSV generated at cycle close.",
    )

    class Meta:
        ordering = ["-period_end"]
        unique_together = [("agency", "period_start", "period_end")]
        indexes = [
            models.Index(fields=["agency", "status"],
                         name="idx_cycle_agency_status"),
        ]

    def __str__(self):
        return (
            f"PayrollCycle {self.period_start}–{self.period_end} "
            f"({self.agency}) [{self.status}]"
        )


class TaxDocument(BaseModel):
    """
    W-9 / 1099 / other compliance documents uploaded by agencies.
    """

    DOC_TYPE_W9 = "w9"
    DOC_TYPE_1099 = "1099"
    DOC_TYPE_OTHER = "other"
    DOC_TYPE_CHOICES = [
        (DOC_TYPE_W9, "W-9"),
        (DOC_TYPE_1099, "1099"),
        (DOC_TYPE_OTHER, "Other"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    agency = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="tax_documents",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_tax_documents",
    )
    document_type = models.CharField(
        max_length=16, choices=DOC_TYPE_CHOICES, default=DOC_TYPE_W9,
    )
    file = models.FileField(upload_to="payroll/tax_documents/")
    original_filename = models.CharField(max_length=255, blank=True, default="")
    tax_year = models.PositiveIntegerField(
        help_text="The fiscal year this document applies to.",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True, null=True, default=None,
        on_delete=models.SET_NULL,
        related_name="reviewed_tax_documents",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True, default=None)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["agency", "tax_year"],
                         name="idx_taxdoc_agency_year"),
        ]

    def __str__(self):
        return (
            f"{self.get_document_type_display()} — "
            f"{self.agency} ({self.tax_year})"
        )


class PaymentHold(BaseModel):
    """
    Fiscal Auditor override — pauses an agency's payout when anomalies
    are detected.  The Auditor can later release or escalate.
    """

    STATUS_ACTIVE = "active"
    STATUS_RELEASED = "released"
    STATUS_ESCALATED = "escalated"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active Hold"),
        (STATUS_RELEASED, "Released"),
        (STATUS_ESCALATED, "Escalated"),
    ]

    payroll_cycle = models.ForeignKey(
        PayrollCycle,
        on_delete=models.CASCADE,
        related_name="holds",
    )
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="placed_payment_holds",
    )
    reason = models.TextField(
        help_text="Explanation of the anomaly or concern.",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True, null=True, default=None,
        on_delete=models.SET_NULL,
        related_name="released_payment_holds",
    )
    released_at = models.DateTimeField(blank=True, null=True, default=None)
    release_notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return (
            f"Hold on {self.payroll_cycle} by {self.placed_by} "
            f"[{self.status}]"
        )
