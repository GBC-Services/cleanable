"""
Add PlatformIntegration and NotificationPreference models
for the Cybernetic Command Center.
"""

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("governance", "0001_initial"),
    ]

    operations = [
        # ── PlatformIntegration ──────────────────────────────────────
        migrations.CreateModel(
            name="PlatformIntegration",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(max_length=80, unique=True),
                ),
                ("name", models.CharField(max_length=120)),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Human-readable explanation of what this integration does.",
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("proactive", "Proactive Intelligence"),
                            ("voice", "Voice Assistants"),
                            ("device", "Device Access"),
                        ],
                        default="proactive",
                        max_length=24,
                    ),
                ),
                (
                    "icon",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Lucide icon name for the UI.",
                        max_length=40,
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=False,
                        help_text="Master switch — when False, this integration is off platform-wide.",
                    ),
                ),
                (
                    "config",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Integration-specific configuration.",
                    ),
                ),
                (
                    "toggled_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "toggled_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="toggled_integrations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Platform Integration",
                "verbose_name_plural": "Platform Integrations",
                "ordering": ["category", "name"],
            },
        ),
        # ── NotificationPreference ───────────────────────────────────
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "event_slug",
                    models.CharField(
                        choices=[
                            ("booking_created", "Booking Created"),
                            ("booking_confirmed", "Booking Confirmed"),
                            ("booking_cancelled", "Booking Cancelled"),
                            ("job_assigned", "Job Assigned"),
                            ("job_started", "Job Started"),
                            ("job_completed", "Job Completed"),
                            ("qa_review_ready", "QA Review Ready"),
                            ("qa_passed", "QA Passed"),
                            ("qa_failed", "QA Failed"),
                            ("payout_ready", "Payout Ready"),
                            ("payout_sent", "Payout Sent"),
                            ("geofence_enter", "Geofence Enter"),
                            ("geofence_exit", "Geofence Exit"),
                            ("geofence_breach", "Geofence Breach"),
                            ("smart_lock_access", "Smart Lock Access"),
                            ("complaint_filed", "Complaint Filed"),
                            ("complaint_resolved", "Complaint Resolved"),
                            ("break_glass_activated", "Break-Glass Activated"),
                            ("system_alert", "System Alert"),
                        ],
                        db_index=True,
                        max_length=40,
                    ),
                ),
                (
                    "in_app",
                    models.BooleanField(
                        default=True,
                        help_text="Show in-app notification / toast.",
                    ),
                ),
                (
                    "sms",
                    models.BooleanField(
                        default=False,
                        help_text="Send SMS notification via Twilio.",
                    ),
                ),
                (
                    "email",
                    models.BooleanField(
                        default=True,
                        help_text="Send email notification.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Notification Preference",
                "verbose_name_plural": "Notification Preferences",
                "ordering": ["user", "event_slug"],
                "unique_together": {("user", "event_slug")},
                "indexes": [
                    models.Index(
                        fields=["user", "event_slug"],
                        name="idx_notifpref_user_event",
                    ),
                ],
            },
        ),
        # ── Seed PlatformIntegration data ────────────────────────────
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model(
                "governance", "PlatformIntegration"
            ).objects.bulk_create([
                apps.get_model("governance", "PlatformIntegration")(
                    slug="predictive_booking",
                    name="Predictive Booking",
                    description=(
                        "AI-driven booking suggestions based on holiday patterns, "
                        "local weather data, and historical cleaning frequency. "
                        "The system proactively recommends optimal cleaning times to Residents."
                    ),
                    category="proactive",
                    icon="brain",
                    is_enabled=False,
                    config={
                        "holiday_patterns": True,
                        "weather_triggers": True,
                        "suggestion_threshold": 0.7,
                        "lookback_days": 90,
                    },
                ),
                apps.get_model("governance", "PlatformIntegration")(
                    slug="alexa_voice_booking",
                    name="Alexa Voice Booking",
                    description=(
                        "Enable Amazon Alexa voice commands for booking management. "
                        "Residents can say 'Alexa, schedule a cleaning' to create, "
                        "reschedule, or cancel bookings via the Cleanable skill."
                    ),
                    category="voice",
                    icon="mic",
                    is_enabled=False,
                    config={
                        "skill_id": "",
                        "webhook_url": "",
                        "supported_intents": [
                            "CreateBooking", "CancelBooking",
                            "CheckStatus", "NextCleaning",
                        ],
                    },
                ),
                apps.get_model("governance", "PlatformIntegration")(
                    slug="homepod_siri_booking",
                    name="HomePod / Siri Booking",
                    description=(
                        "Enable Apple Siri and HomePod voice commands for booking. "
                        "Uses Siri Shortcuts and HomeKit integration for hands-free "
                        "cleaning management on Apple devices."
                    ),
                    category="voice",
                    icon="speaker",
                    is_enabled=False,
                    config={
                        "shortcut_id": "",
                        "homekit_bridge_enabled": False,
                        "supported_phrases": [
                            "Schedule a cleaning",
                            "When is my next cleaning",
                            "Cancel my cleaning",
                        ],
                    },
                ),
                apps.get_model("governance", "PlatformIntegration")(
                    slug="smart_lock_api",
                    name="Smart Lock API Access",
                    description=(
                        "Grant the platform API access to connected smart locks "
                        "(August, Yale, SmartThings). When enabled, the system "
                        "auto-generates time-bound access codes for Service Pros "
                        "on the day of their scheduled cleaning."
                    ),
                    category="device",
                    icon="lock",
                    is_enabled=False,
                    config={
                        "auto_generate_codes": True,
                        "code_validity_minutes": 120,
                        "notify_resident_on_access": True,
                        "revoke_on_job_complete": True,
                    },
                ),
            ], ignore_conflicts=True),
            reverse_code=migrations.RunPython.noop,
        ),
    ]
