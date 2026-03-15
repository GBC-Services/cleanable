"""
Initial migration for the Onboarding & Contracting app.

Creates:
  - ManagerApprovalRequest
  - AgencyServiceArea
  - AgencyContract
  - ContractSignature
"""

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0001_initial"),
    ]

    operations = [
        # ── ManagerApprovalRequest ────────────────────────────────────
        migrations.CreateModel(
            name="ManagerApprovalRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("typed_agency_name", models.CharField(help_text="The exact string the Service Pro typed at registration.", max_length=256)),
                ("match_score", models.FloatField(help_text="SequenceMatcher ratio (0.0 – 1.0) of typed name vs actual.")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("expired", "Expired")], db_index=True, default="pending", max_length=16)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True, default="")),
                ("expires_at", models.DateTimeField(help_text="Auto-expire after 72 hours if not acted on.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("agency", models.ForeignKey(help_text="The matched agency (Company) being requested.", on_delete=django.db.models.deletion.CASCADE, related_name="approval_requests", to="companies.company")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_approvals", to=settings.AUTH_USER_MODEL)),
                ("service_pro", models.ForeignKey(help_text="The Service Pro requesting to join the agency.", on_delete=django.db.models.deletion.CASCADE, related_name="approval_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="managerapprovalrequest",
            index=models.Index(fields=["agency", "status"], name="idx_approval_agency_status"),
        ),
        migrations.AddIndex(
            model_name="managerapprovalrequest",
            index=models.Index(fields=["service_pro"], name="idx_approval_service_pro"),
        ),

        # ── AgencyServiceArea ─────────────────────────────────────────
        migrations.CreateModel(
            name="AgencyServiceArea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(help_text="Human-readable area name, e.g. 'Downtown Houston'", max_length=128)),
                ("geojson", models.JSONField(help_text="GeoJSON Feature with geometry.type='MultiPolygon'. Coordinates are [lng, lat] arrays.")),
                ("color", models.CharField(default="#01696F", help_text="Hex color for rendering the geofence on the map.", max_length=7)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("agency", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_areas", to="companies.company")),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddIndex(
            model_name="agencyservicearea",
            index=models.Index(fields=["agency", "is_active"], name="idx_area_agency_active"),
        ),

        # ── AgencyContract ────────────────────────────────────────────
        migrations.CreateModel(
            name="AgencyContract",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("version", models.PositiveIntegerField(default=1, help_text="Contract version number — increments on renegotiation.")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("pending_signatures", "Pending Signatures"), ("fully_signed", "Fully Signed"), ("expired", "Expired"), ("revoked", "Revoked")], db_index=True, default="draft", max_length=24)),
                ("service_areas_snapshot", models.JSONField(help_text="Array of AgencyServiceArea GeoJSON objects at signing time.")),
                ("pricing_snapshot", models.JSONField(help_text="Pricing table snapshot — service fees at contract generation.")),
                ("terms_text", models.TextField(help_text="Full contract terms as Markdown or plain text.")),
                ("pdf_file", models.FileField(blank=True, help_text="Generated PDF. Null until first generation.", null=True, upload_to="contracts/pdfs/%Y/%m/")),
                ("pdf_generated_at", models.DateTimeField(blank=True, null=True)),
                ("document_hash", models.CharField(blank=True, default="", help_text="SHA-256 hash of the generated PDF for tamper detection.", max_length=64)),
                ("required_signers", models.JSONField(default=list, help_text="List of signer descriptors.")),
                ("effective_date", models.DateField(blank=True, help_text="Date the contract becomes effective (after all signatures).", null=True)),
                ("expiry_date", models.DateField(blank=True, help_text="Contract expiration date.", null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("agency", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contracts", to="companies.company")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_contracts", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("agency", "version")},
            },
        ),
        migrations.AddIndex(
            model_name="agencycontract",
            index=models.Index(fields=["agency", "status"], name="idx_contract_agency_status"),
        ),

        # ── ContractSignature ─────────────────────────────────────────
        migrations.CreateModel(
            name="ContractSignature",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("signer_role", models.CharField(choices=[("agency_owner", "Agency Owner"), ("platform_admin", "Platform Admin")], max_length=24)),
                ("signer_full_name", models.CharField(help_text="Full legal name as typed by the signer.", max_length=256)),
                ("signer_email", models.EmailField(max_length=254)),
                ("signature_hash", models.CharField(help_text="SHA-256(document_hash + signer_email + timestamp).", max_length=64)),
                ("ip_address", models.GenericIPAddressField(help_text="IP address at time of signing.")),
                ("user_agent", models.TextField(blank=True, default="", help_text="Browser user agent string at signing.")),
                ("is_valid", models.BooleanField(default=True)),
                ("signed_at", models.DateTimeField(auto_now_add=True)),
                ("contract", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="signatures", to="onboarding.agencycontract")),
                ("signer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contract_signatures", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["signed_at"],
                "unique_together": {("contract", "signer_role")},
            },
        ),
    ]
