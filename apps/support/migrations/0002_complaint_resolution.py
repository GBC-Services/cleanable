"""
Migration: Complaint Resolution Pipeline
==========================================

Adds Complaint, ResolutionAction, AgencyBlacklist, and
ComplaintNotification models to the support app.
"""

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("support", "0001_initial"),
        ("bookings", "0001_initial"),
        ("cleanings", "0001_initial"),
        ("companies", "0001_initial"),
    ]

    operations = [
        # ── Complaint ─────────────────────────────────────────────────
        migrations.CreateModel(
            name="Complaint",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("scenario", models.CharField(choices=[
                    ("incomplete_clean", "Incomplete Clean"),
                    ("no_show", "No-Show"),
                    ("damage_reported", "Damage Reported"),
                    ("late_arrival", "Late Arrival"),
                ], max_length=32)),
                ("description", models.TextField(help_text="Resident's description of the issue.")),
                ("urgency", models.PositiveIntegerField(choices=[
                    (10, "Low"), (20, "Medium"), (30, "High"), (40, "Critical"),
                ], default=20)),
                ("status", models.CharField(choices=[
                    ("open", "Open"),
                    ("acknowledged", "Acknowledged"),
                    ("investigating", "Investigating"),
                    ("resolved", "Resolved"),
                    ("closed", "Closed"),
                ], default="open", max_length=16)),
                ("escalated_at", models.DateTimeField(blank=True, null=True, default=None)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True, default=None)),
                ("resolved_at", models.DateTimeField(blank=True, null=True, default=None)),
                ("evidence_photos", models.JSONField(blank=True, null=True, default=None)),
                ("resident", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="complaints_filed",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("booking", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="complaints",
                    to="bookings.booking",
                )),
                ("cleaning", models.ForeignKey(
                    blank=True, null=True, default=None,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="complaints",
                    to="cleanings.cleaning",
                )),
                ("company", models.ForeignKey(
                    blank=True, null=True, default=None,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="complaints_against",
                    to="companies.company",
                )),
                ("assigned_to", models.ForeignKey(
                    blank=True, null=True, default=None,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="complaints_assigned",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("support_ticket", models.OneToOneField(
                    blank=True, null=True, default=None,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="complaint",
                    to="support.supportticket",
                )),
            ],
            options={"ordering": ["-created"]},
        ),

        # ── ResolutionAction ──────────────────────────────────────────
        migrations.CreateModel(
            name="ResolutionAction",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("action_type", models.CharField(choices=[
                    ("refund_partial", "Partial Refund"),
                    ("refund_full", "Full Refund"),
                    ("schedule_redo", "Schedule Re-do"),
                    ("cancel_blacklist", "Cancel & Blacklist"),
                    ("note", "Internal Note"),
                ], max_length=20)),
                ("execution_status", models.CharField(choices=[
                    ("pending", "Pending"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ], default="pending", max_length=12)),
                ("notes", models.TextField(blank=True, default="")),
                ("refund_amount", models.DecimalField(
                    blank=True, null=True, default=None,
                    decimal_places=2, max_digits=10,
                )),
                ("stripe_refund_id", models.CharField(
                    blank=True, null=True, default=None, max_length=128,
                )),
                ("reassigned_bookings_count", models.PositiveIntegerField(default=0)),
                ("notifications_sent", models.JSONField(blank=True, null=True, default=None)),
                ("executed_at", models.DateTimeField(blank=True, null=True, default=None)),
                ("complaint", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="resolution_actions",
                    to="support.complaint",
                )),
                ("performed_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="resolution_actions_taken",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("redo_cleaning", models.ForeignKey(
                    blank=True, null=True, default=None,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="redo_resolution",
                    to="cleanings.cleaning",
                )),
                ("redo_assigned_company", models.ForeignKey(
                    blank=True, null=True, default=None,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="redo_assignments",
                    to="companies.company",
                )),
                ("blacklisted_company", models.ForeignKey(
                    blank=True, null=True, default=None,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="blacklist_actions",
                    to="companies.company",
                )),
            ],
            options={"ordering": ["-created"]},
        ),

        # ── AgencyBlacklist ───────────────────────────────────────────
        migrations.CreateModel(
            name="AgencyBlacklist",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("reason", models.TextField(blank=True, default="")),
                ("blacklisted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("resident", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="agency_blacklist",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="blacklisted_by_residents",
                    to="companies.company",
                )),
                ("complaint", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="blacklist_entries",
                    to="support.complaint",
                )),
            ],
            options={
                "ordering": ["-blacklisted_at"],
                "unique_together": {("resident", "company")},
            },
        ),

        # ── ComplaintNotification ─────────────────────────────────────
        migrations.CreateModel(
            name="ComplaintNotification",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("channel", models.CharField(choices=[
                    ("sms", "SMS"),
                    ("push", "Push Notification"),
                    ("email", "Email"),
                    ("in_app", "In-App"),
                ], max_length=8)),
                ("status", models.CharField(choices=[
                    ("pending", "Pending"),
                    ("sent", "Sent"),
                    ("failed", "Failed"),
                ], default="pending", max_length=8)),
                ("message_body", models.TextField()),
                ("sent_at", models.DateTimeField(blank=True, null=True, default=None)),
                ("error_detail", models.TextField(blank=True, default="")),
                ("complaint", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notifications",
                    to="support.complaint",
                )),
                ("resolution_action", models.ForeignKey(
                    blank=True, null=True, default=None,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="notifications",
                    to="support.resolutionaction",
                )),
                ("recipient", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="complaint_notifications_received",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created"]},
        ),
    ]
