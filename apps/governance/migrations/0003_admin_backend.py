"""
Phase 3: Admin Backend — Secret Vault, Permission Matrix, User Security

Creates:
  - SecretVault: Encrypted API key storage with scoped permissions,
    environment toggles, rotation, and revocation.
  - RolePermissionMatrix: Global role × permission grid.
  - UserSecurityAction: Immutable log of password resets, MFA changes,
    and account lock/unlock actions.

Seeds:
  - Default RolePermissionMatrix entries for all 7 roles × 14 permissions.
"""

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def seed_permission_matrix(apps, schema_editor):
    """
    Seed the default permission matrix based on role design.

    Roles (value → name):
      10 = Resident
      20 = Platform Admin
      30 = Agency Owner
      40 = Service Pro
      50 = Support Architect
      60 = QA Inspector
      70 = Fiscal Auditor
    """
    RolePermissionMatrix = apps.get_model("governance", "RolePermissionMatrix")

    # Default permission grants per role
    defaults = {
        10: {  # Resident
            "manage_bookings": True,
            "view_all_bookings": False,
            "manage_service_pros": False,
            "access_reports": False,
            "manage_iot": False,
            "view_audit_logs": False,
            "manage_feature_toggles": False,
            "manage_break_glass": False,
            "manage_payroll": False,
            "manage_complaints": False,
            "manage_qa": False,
            "manage_vault": False,
            "manage_users": False,
            "access_command_palette": False,
        },
        20: {  # Platform Admin — all permissions
            "manage_bookings": True,
            "view_all_bookings": True,
            "manage_service_pros": True,
            "access_reports": True,
            "manage_iot": True,
            "view_audit_logs": True,
            "manage_feature_toggles": True,
            "manage_break_glass": True,
            "manage_payroll": True,
            "manage_complaints": True,
            "manage_qa": True,
            "manage_vault": True,
            "manage_users": True,
            "access_command_palette": True,
        },
        30: {  # Agency Owner
            "manage_bookings": True,
            "view_all_bookings": True,
            "manage_service_pros": True,
            "access_reports": True,
            "manage_iot": False,
            "view_audit_logs": False,
            "manage_feature_toggles": False,
            "manage_break_glass": False,
            "manage_payroll": True,
            "manage_complaints": True,
            "manage_qa": True,
            "manage_vault": False,
            "manage_users": False,
            "access_command_palette": False,
        },
        40: {  # Service Pro
            "manage_bookings": False,
            "view_all_bookings": False,
            "manage_service_pros": False,
            "access_reports": False,
            "manage_iot": False,
            "view_audit_logs": False,
            "manage_feature_toggles": False,
            "manage_break_glass": False,
            "manage_payroll": False,
            "manage_complaints": False,
            "manage_qa": False,
            "manage_vault": False,
            "manage_users": False,
            "access_command_palette": False,
        },
        50: {  # Support Architect
            "manage_bookings": True,
            "view_all_bookings": True,
            "manage_service_pros": False,
            "access_reports": True,
            "manage_iot": False,
            "view_audit_logs": False,
            "manage_feature_toggles": False,
            "manage_break_glass": True,
            "manage_payroll": False,
            "manage_complaints": True,
            "manage_qa": False,
            "manage_vault": False,
            "manage_users": False,
            "access_command_palette": False,
        },
        60: {  # QA Inspector
            "manage_bookings": False,
            "view_all_bookings": True,
            "manage_service_pros": False,
            "access_reports": True,
            "manage_iot": False,
            "view_audit_logs": False,
            "manage_feature_toggles": False,
            "manage_break_glass": False,
            "manage_payroll": False,
            "manage_complaints": False,
            "manage_qa": True,
            "manage_vault": False,
            "manage_users": False,
            "access_command_palette": False,
        },
        70: {  # Fiscal Auditor
            "manage_bookings": False,
            "view_all_bookings": True,
            "manage_service_pros": False,
            "access_reports": True,
            "manage_iot": False,
            "view_audit_logs": True,
            "manage_feature_toggles": False,
            "manage_break_glass": False,
            "manage_payroll": True,
            "manage_complaints": False,
            "manage_qa": False,
            "manage_vault": False,
            "manage_users": False,
            "access_command_palette": False,
        },
    }

    entries = []
    for role, perms in defaults.items():
        for perm, granted in perms.items():
            entries.append(
                RolePermissionMatrix(
                    role=role,
                    permission=perm,
                    is_granted=granted,
                )
            )
    RolePermissionMatrix.objects.bulk_create(entries, ignore_conflicts=True)


def reverse_seed(apps, schema_editor):
    RolePermissionMatrix = apps.get_model("governance", "RolePermissionMatrix")
    RolePermissionMatrix.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("governance", "0002_command_center_models"),
    ]

    operations = [
        # ── New audit log action choices (alter existing field) ────────
        migrations.AlterField(
            model_name="governanceauditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("feature_toggled", "System Feature Toggled"),
                    ("privacy_updated", "Privacy Preferences Updated"),
                    ("break_glass_requested", "Break-Glass Requested"),
                    ("break_glass_activated", "Break-Glass Activated"),
                    ("break_glass_revoked", "Break-Glass Revoked"),
                    ("break_glass_expired", "Break-Glass Expired"),
                    ("override_applied", "Privacy Override Applied"),
                    ("override_reverted", "Privacy Override Reverted"),
                    ("emergency_access_revocation", "Emergency Access Revocation"),
                    ("emergency_lockout", "Emergency Lockout"),
                    ("vault_secret_created", "Vault Secret Created"),
                    ("vault_secret_rotated", "Vault Secret Rotated"),
                    ("vault_secret_revoked", "Vault Secret Revoked"),
                    ("permission_updated", "Permission Updated"),
                    ("password_force_reset", "Password Force Reset"),
                    ("mfa_managed", "MFA Managed"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),

        # ── SecretVault ───────────────────────────────────────────────
        migrations.CreateModel(
            name="SecretVault",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(help_text="Human-readable name (e.g. 'Stripe Live Key', 'Twilio SID').", max_length=120)),
                ("provider", models.CharField(choices=[("stripe", "Stripe"), ("mapbox", "Mapbox"), ("twilio", "Twilio"), ("smart_lock", "Smart Lock Provider"), ("cloudflare", "Cloudflare"), ("sendgrid", "SendGrid"), ("custom", "Custom")], max_length=24)),
                ("scope", models.CharField(choices=[("read", "Read Only"), ("write", "Write Only"), ("full", "Full Access")], default="full", max_length=12)),
                ("environment", models.CharField(choices=[("sandbox", "Sandbox"), ("production", "Production")], default="sandbox", max_length=16)),
                ("status", models.CharField(choices=[("active", "Active"), ("rotated", "Rotated"), ("revoked", "Revoked"), ("expired", "Expired")], default="active", max_length=12)),
                ("encrypted_value", models.TextField(help_text="The API key or secret value (encrypted at rest).")),
                ("key_prefix", models.CharField(blank=True, default="", help_text="First few chars of the key for identification.", max_length=12)),
                ("key_hint", models.CharField(blank=True, default="", help_text="Last 4 chars of the key for UI display.", max_length=8)),
                ("auto_rotate", models.BooleanField(default=False, help_text="Enable automatic rotation on schedule.")),
                ("rotation_interval_days", models.PositiveIntegerField(default=90, help_text="Days between automatic rotations.")),
                ("last_rotated_at", models.DateTimeField(blank=True, null=True)),
                ("next_rotation_at", models.DateTimeField(blank=True, null=True)),
                ("rotation_count", models.PositiveIntegerField(default=0)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoke_reason", models.TextField(blank=True, default="")),
                ("notes", models.TextField(blank=True, default="", help_text="Internal notes about this key.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vault_secrets_created", to=settings.AUTH_USER_MODEL)),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vault_secrets_revoked", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Secret Vault Entry",
                "verbose_name_plural": "Secret Vault Entries",
                "ordering": ["provider", "label"],
            },
        ),
        migrations.AddIndex(
            model_name="secretvault",
            index=models.Index(fields=["provider", "environment", "status"], name="idx_vault_provider_env"),
        ),
        migrations.AddIndex(
            model_name="secretvault",
            index=models.Index(fields=["status"], name="idx_vault_status"),
        ),
        migrations.AddIndex(
            model_name="secretvault",
            index=models.Index(fields=["next_rotation_at"], name="idx_vault_next_rotation"),
        ),

        # ── RolePermissionMatrix ──────────────────────────────────────
        migrations.CreateModel(
            name="RolePermissionMatrix",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.PositiveIntegerField(help_text="Role integer matching User.ROLES (10, 20, 30, etc.).")),
                ("permission", models.CharField(choices=[("manage_bookings", "Manage Bookings"), ("view_all_bookings", "View All Bookings"), ("manage_service_pros", "Manage Service Pros"), ("access_reports", "Access Reports"), ("manage_iot", "Manage IoT"), ("view_audit_logs", "View Audit Logs"), ("manage_feature_toggles", "Manage Feature Toggles"), ("manage_break_glass", "Manage Break-Glass"), ("manage_payroll", "Manage Payroll"), ("manage_complaints", "Manage Complaints"), ("manage_qa", "Manage QA"), ("manage_vault", "Manage Vault"), ("manage_users", "Manage Users"), ("access_command_palette", "Access Command Palette")], max_length=40)),
                ("is_granted", models.BooleanField(default=True, help_text="Whether this permission is granted to the role.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="permission_matrix_changes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Role Permission Matrix Entry",
                "verbose_name_plural": "Role Permission Matrix Entries",
                "ordering": ["role", "permission"],
                "unique_together": {("role", "permission")},
            },
        ),
        migrations.AddIndex(
            model_name="rolepermissionmatrix",
            index=models.Index(fields=["role", "permission"], name="idx_rpm_role_perm"),
        ),
        migrations.AddIndex(
            model_name="rolepermissionmatrix",
            index=models.Index(fields=["role"], name="idx_rpm_role"),
        ),

        # ── UserSecurityAction ────────────────────────────────────────
        migrations.CreateModel(
            name="UserSecurityAction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(choices=[("password_force_reset", "Password Force Reset"), ("mfa_enroll", "MFA Enrollment"), ("mfa_revoke", "MFA Revocation"), ("account_lock", "Account Locked"), ("account_unlock", "Account Unlocked")], max_length=32)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed")], default="completed", max_length=12)),
                ("reason", models.TextField(blank=True, default="", help_text="Justification for the action.")),
                ("metadata", models.JSONField(blank=True, default=dict, help_text="Additional context.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("admin", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="security_actions_performed", to=settings.AUTH_USER_MODEL)),
                ("target_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="security_actions_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "User Security Action",
                "verbose_name_plural": "User Security Actions",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="usersecurityaction",
            index=models.Index(fields=["target_user", "-created_at"], name="idx_secaction_target"),
        ),
        migrations.AddIndex(
            model_name="usersecurityaction",
            index=models.Index(fields=["admin", "-created_at"], name="idx_secaction_admin"),
        ),
        migrations.AddIndex(
            model_name="usersecurityaction",
            index=models.Index(fields=["action"], name="idx_secaction_action"),
        ),

        # ── Seed default permission matrix ────────────────────────────
        migrations.RunPython(seed_permission_matrix, reverse_seed),
    ]
