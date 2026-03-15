"""
Governance models: SystemFeatureToggle, PrivacyPreferences,
BreakGlassSession, GovernanceAuditLog.

Includes resident_ai_processing_opt_out field for AI opt-out.
"""

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemFeatureToggle",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True, default="")),
                ("category", models.CharField(choices=[("location", "Location Services"), ("iot", "IoT & Smart Home"), ("media", "Media & Recording"), ("ai", "AI & Machine Learning"), ("communications", "Communications"), ("security", "Security & Escalation")], default="security", max_length=24)),
                ("severity", models.CharField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")], default="medium", max_length=12)),
                ("is_enabled", models.BooleanField(default=False)),
                ("toggled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("toggled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="toggled_features", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "System Feature Toggle",
                "verbose_name_plural": "System Feature Toggles",
                "ordering": ["category", "name"],
            },
        ),
        migrations.CreateModel(
            name="PrivacyPreferences",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("allow_email_notifications", models.BooleanField(default=True)),
                ("allow_push_notifications", models.BooleanField(default=True)),
                ("allow_sms_notifications", models.BooleanField(default=False)),
                ("allow_analytics_tracking", models.BooleanField(default=False)),
                ("profile_visibility", models.CharField(choices=[("private", "Private"), ("company", "Company Only"), ("public", "Public")], default="private", max_length=16)),
                ("resident_share_address_with_pro", models.BooleanField(default=False)),
                ("resident_allow_gps_tracking", models.BooleanField(default=False)),
                ("resident_allow_iot_access", models.BooleanField(default=False)),
                ("resident_allow_spatial_video", models.BooleanField(default=False)),
                ("resident_allow_ai_scoring", models.BooleanField(default=False)),
                ("resident_share_booking_history", models.BooleanField(default=False)),
                ("resident_ai_processing_opt_out", models.BooleanField(default=False, help_text="When True, Service Pro verification videos bypass Cloudflare AI analysis entirely and are routed to a human QA Inspector or Agency Owner for manual approval.")),
                ("pro_allow_live_gps_tracking", models.BooleanField(default=False)),
                ("pro_allow_route_recording", models.BooleanField(default=False)),
                ("pro_allow_availability_broadcast", models.BooleanField(default=True)),
                ("pro_allow_performance_analytics", models.BooleanField(default=False)),
                ("pro_allow_client_reviews_public", models.BooleanField(default=True)),
                ("pro_allow_photo_verification", models.BooleanField(default=True)),
                ("is_overridden", models.BooleanField(default=False)),
                ("overridden_at", models.DateTimeField(blank=True, null=True)),
                ("override_reason", models.TextField(blank=True, default="")),
                ("override_expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("overridden_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="privacy_overrides_applied", to=settings.AUTH_USER_MODEL)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="privacy_preferences", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Privacy Preferences",
                "verbose_name_plural": "Privacy Preferences",
                "indexes": [
                    models.Index(fields=["user"], name="idx_privacy_user"),
                    models.Index(fields=["is_overridden"], name="idx_privacy_overridden"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BreakGlassSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "Pending Activation"), ("active", "Active"), ("expired", "Expired"), ("revoked", "Revoked")], default="pending", max_length=16)),
                ("reason", models.TextField()),
                ("escalation_reference", models.CharField(blank=True, default="", max_length=128)),
                ("overrides_applied", models.JSONField(blank=True, default=dict)),
                ("requested_duration_minutes", models.PositiveIntegerField(default=60)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("initiated_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="break_glass_initiated", to=settings.AUTH_USER_MODEL)),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="break_glass_revoked", to=settings.AUTH_USER_MODEL)),
                ("target_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="break_glass_targeted", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Break-Glass Session",
                "verbose_name_plural": "Break-Glass Sessions",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "expires_at"], name="idx_bg_status_expiry"),
                    models.Index(fields=["target_user", "status"], name="idx_bg_target_status"),
                    models.Index(fields=["initiated_by"], name="idx_bg_initiator"),
                ],
            },
        ),
        migrations.CreateModel(
            name="GovernanceAuditLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("actor_email", models.EmailField(blank=True, default="", max_length=254)),
                ("actor_role", models.PositiveIntegerField(blank=True, null=True)),
                ("action", models.CharField(choices=[("feature_toggled", "System Feature Toggled"), ("privacy_updated", "Privacy Preferences Updated"), ("break_glass_requested", "Break-Glass Requested"), ("break_glass_activated", "Break-Glass Activated"), ("break_glass_revoked", "Break-Glass Revoked"), ("break_glass_expired", "Break-Glass Expired"), ("override_applied", "Privacy Override Applied"), ("override_reverted", "Privacy Override Reverted"), ("emergency_access_revocation", "Emergency Access Revocation"), ("emergency_lockout", "Emergency Lockout")], db_index=True, max_length=32)),
                ("severity", models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical")], default="info", max_length=12)),
                ("description", models.TextField()),
                ("target_user_email", models.EmailField(blank=True, default="", max_length=254)),
                ("changes", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("timestamp", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="governance_audit_logs", to=settings.AUTH_USER_MODEL)),
                ("related_break_glass", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to="governance.breakglasssession")),
                ("related_feature_toggle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to="governance.systemfeaturetoggle")),
                ("target_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="governance_audit_targeted", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Governance Audit Log",
                "verbose_name_plural": "Governance Audit Logs",
                "ordering": ["-timestamp"],
                "indexes": [
                    models.Index(fields=["action", "timestamp"], name="idx_audit_action_ts"),
                    models.Index(fields=["actor", "timestamp"], name="idx_audit_actor_ts"),
                    models.Index(fields=["target_user", "timestamp"], name="idx_audit_target_ts"),
                    models.Index(fields=["severity"], name="idx_audit_severity"),
                ],
            },
        ),
    ]
