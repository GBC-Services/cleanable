"""
Initial migration for the Payroll & Fiscal Auditing app.

Creates:
  - ActivityStatement
  - PayrollCycle
  - TaxDocument
  - PaymentHold
"""

import uuid
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bookings", "0001_initial"),
        ("cleanings", "0001_initial"),
        ("companies", "0001_initial"),
    ]

    operations = [
        # ── PayrollCycle (must exist before ActivityStatement FK) ──────
        migrations.CreateModel(
            name="PayrollCycle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("status", models.CharField(choices=[("open", "Open"), ("processing", "Processing"), ("paid", "Paid"), ("held", "Held")], default="open", max_length=16)),
                ("total_jobs", models.PositiveIntegerField(default=0)),
                ("total_client_charged", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("total_agency_fees", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("total_pro_wages", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("total_platform_fees", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("total_tips", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("stripe_transfer_id", models.CharField(blank=True, default=None, help_text="Stripe Transfer ID (tr_…) for the agency payout.", max_length=64, null=True)),
                ("paid_at", models.DateTimeField(blank=True, default=None, null=True)),
                ("csv_file", models.FileField(blank=True, default=None, help_text="Master Job Summary CSV generated at cycle close.", null=True, upload_to="payroll/csv/")),
                ("agency", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payroll_cycles", to="companies.company")),
            ],
            options={
                "ordering": ["-period_end"],
                "unique_together": {("agency", "period_start", "period_end")},
            },
        ),
        migrations.AddIndex(
            model_name="payrollcycle",
            index=models.Index(fields=["agency", "status"], name="idx_cycle_agency_status"),
        ),

        # ── ActivityStatement ─────────────────────────────────────────
        migrations.CreateModel(
            name="ActivityStatement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("client_charged", models.DecimalField(decimal_places=2, default=Decimal("0.00"), help_text="Total amount charged to the Resident (booking.total_fee_final).", max_digits=10)),
                ("agency_fee", models.DecimalField(decimal_places=2, default=Decimal("0.00"), help_text="Agency's agreed pricing from their CompanyServiceFee snapshot.", max_digits=10)),
                ("pro_wage", models.DecimalField(decimal_places=2, default=Decimal("0.00"), help_text="Service Pro's wage for this job (set by agency).", max_digits=10)),
                ("platform_fee", models.DecimalField(decimal_places=2, default=Decimal("0.00"), help_text="Platform margin = client_charged − agency_fee.", max_digits=10)),
                ("tip_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), help_text="Tip from resident (passes through to Service Pro).", max_digits=10)),
                ("service_names", models.TextField(blank=True, default="", help_text="Comma-separated service names at time of job.")),
                ("scheduled_date", models.DateField(blank=True, help_text="The date the cleaning was scheduled for.", null=True)),
                ("completed_at", models.DateTimeField(blank=True, help_text="When the cleaning was marked completed.", null=True)),
                ("cleaning", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="activity_statement", to="cleanings.cleaning")),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activity_statements", to="bookings.booking")),
                ("agency", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activity_statements", to="companies.company")),
                ("service_pro", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activity_statements", to=settings.AUTH_USER_MODEL)),
                ("payroll_cycle", models.ForeignKey(blank=True, default=None, help_text="The payroll cycle this statement was batched into.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="line_items", to="payroll.payrollcycle")),
            ],
            options={
                "ordering": ["-completed_at", "-created"],
            },
        ),
        migrations.AddIndex(
            model_name="activitystatement",
            index=models.Index(fields=["agency", "completed_at"], name="idx_stmt_agency_date"),
        ),
        migrations.AddIndex(
            model_name="activitystatement",
            index=models.Index(fields=["service_pro", "completed_at"], name="idx_stmt_pro_date"),
        ),
        migrations.AddIndex(
            model_name="activitystatement",
            index=models.Index(fields=["payroll_cycle"], name="idx_stmt_cycle"),
        ),

        # ── TaxDocument ───────────────────────────────────────────────
        migrations.CreateModel(
            name="TaxDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("document_type", models.CharField(choices=[("w9", "W-9"), ("1099", "1099"), ("other", "Other")], default="w9", max_length=16)),
                ("file", models.FileField(upload_to="payroll/tax_documents/")),
                ("original_filename", models.CharField(blank=True, default="", max_length=255)),
                ("tax_year", models.PositiveIntegerField(help_text="The fiscal year this document applies to.")),
                ("status", models.CharField(choices=[("pending", "Pending Review"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=16)),
                ("notes", models.TextField(blank=True, default="")),
                ("reviewed_at", models.DateTimeField(blank=True, default=None, null=True)),
                ("agency", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tax_documents", to="companies.company")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="uploaded_tax_documents", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_tax_documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        migrations.AddIndex(
            model_name="taxdocument",
            index=models.Index(fields=["agency", "tax_year"], name="idx_taxdoc_agency_year"),
        ),

        # ── PaymentHold ───────────────────────────────────────────────
        migrations.CreateModel(
            name="PaymentHold",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("reason", models.TextField(help_text="Explanation of the anomaly or concern.")),
                ("status", models.CharField(choices=[("active", "Active Hold"), ("released", "Released"), ("escalated", "Escalated")], default="active", max_length=16)),
                ("released_at", models.DateTimeField(blank=True, default=None, null=True)),
                ("release_notes", models.TextField(blank=True, default="")),
                ("payroll_cycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="holds", to="payroll.payrollcycle")),
                ("placed_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="placed_payment_holds", to=settings.AUTH_USER_MODEL)),
                ("released_by", models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="released_payment_holds", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
    ]
