"""
Onboarding & Contracting Models
==================================

Autonomous Service Pro registration, Agency fuzzy-matching,
geofence-based service areas, and digitally-signed contract generation.

Architecture::

    ┌──────────────────────────────────────────────────────────────┐
    │  Service Pro types agency name at registration               │
    │  → Fuzzy match against Company.name (SequenceMatcher ≥ 0.75) │
    │  → Match found: create ManagerApprovalRequest                │
    │  → WebSocket push to Agency Owner for real-time approval     │
    └──────────────────────┬───────────────────────────────────────┘
                           │ approved
    ┌──────────────────────▼───────────────────────────────────────┐
    │  AgencyServiceArea (MultiPolygon GeoJSON)                    │
    │  Drawn by Agency Owner on Mapbox geofence editor             │
    │  Used for spatial booking assignment — Resident location     │
    │  must fall within the MultiPolygon for job routing            │
    └──────────────────────┬───────────────────────────────────────┘
                           │ areas + pricing snapshot
    ┌──────────────────────▼───────────────────────────────────────┐
    │  AgencyContract (auto-generated PDF)                         │
    │  Contains geofence map, pricing table, terms                 │
    │  Locked until digitally signed by all parties                 │
    └──────────────────────┬───────────────────────────────────────┘
                           │ each signer
    ┌──────────────────────▼───────────────────────────────────────┐
    │  ContractSignature (per-party)                               │
    │  Captures signer identity, IP, timestamp, signature hash     │
    └──────────────────────────────────────────────────────────────┘
"""

import hashlib
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. ManagerApprovalRequest — WebSocket-driven approval queue
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ManagerApprovalRequest(models.Model):
    """
    Created when a Service Pro registers and fuzzy-matches an existing
    Agency.  The Agency Owner receives a real-time WebSocket notification
    to approve or reject the request.

    Status flow:  pending → approved | rejected | expired
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_EXPIRED, "Expired"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    service_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approval_requests",
        help_text="The Service Pro requesting to join the agency.",
    )
    agency = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="approval_requests",
        help_text="The matched agency (Company) being requested.",
    )
    typed_agency_name = models.CharField(
        max_length=256,
        help_text="The exact string the Service Pro typed at registration.",
    )
    match_score = models.FloatField(
        help_text="SequenceMatcher ratio (0.0 – 1.0) of typed name vs actual."
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reviewed_approvals",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    expires_at = models.DateTimeField(
        help_text="Auto-expire after 72 hours if not acted on.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["agency", "status"], name="idx_approval_agency_status"),
            models.Index(fields=["service_pro"], name="idx_approval_service_pro"),
        ]

    def __str__(self):
        return (
            f"ApprovalRequest({self.service_pro} → {self.agency.name}, "
            f"score={self.match_score:.2f}, status={self.status})"
        )

    @property
    def is_expired(self):
        return (
            self.status == self.STATUS_PENDING
            and timezone.now() >= self.expires_at
        )

    def approve(self, reviewer):
        """Mark approved and link the Service Pro to the agency."""
        self.status = self.STATUS_APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        # Link Service Pro to company
        self.service_pro.company = self.agency
        self.service_pro.save(update_fields=["company"])

    def reject(self, reviewer, reason=""):
        self.status = self.STATUS_REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=[
            "status", "reviewed_by", "reviewed_at",
            "rejection_reason", "updated_at",
        ])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. AgencyServiceArea — Geofence MultiPolygon
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgencyServiceArea(models.Model):
    """
    A named geographic service area drawn by the Agency Owner on a
    Mapbox geofence editor.  Stored as GeoJSON MultiPolygon coordinates.

    Used for spatial booking assignment: a Resident's location must
    fall within one of the agency's service areas for job routing.
    """

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    agency = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="service_areas",
    )
    name = models.CharField(
        max_length=128,
        help_text="Human-readable area name, e.g. 'Downtown Houston'",
    )
    geojson = models.JSONField(
        help_text=(
            "GeoJSON Feature with geometry.type='MultiPolygon'. "
            "Coordinates are [lng, lat] arrays."
        ),
    )
    color = models.CharField(
        max_length=7, default="#01696F",
        help_text="Hex color for rendering the geofence on the map.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["agency", "is_active"], name="idx_area_agency_active"),
        ]

    def __str__(self):
        return f"{self.agency.name} – {self.name}"

    @staticmethod
    def point_in_polygon(point_lng, point_lat, polygon_coords):
        """
        Ray-casting algorithm — checks if a point falls inside a polygon ring.
        polygon_coords: list of [lng, lat] pairs forming a closed ring.
        """
        n = len(polygon_coords)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon_coords[i]
            xj, yj = polygon_coords[j]
            if ((yi > point_lat) != (yj > point_lat)) and (
                point_lng < (xj - xi) * (point_lat - yi) / (yj - yi) + xi
            ):
                inside = not inside
            j = i
        return inside

    def contains_point(self, lng, lat):
        """
        Check if a [lng, lat] point falls within this service area's
        MultiPolygon geometry.
        """
        geom = self.geojson.get("geometry", self.geojson)
        geom_type = geom.get("type", "")
        coords = geom.get("coordinates", [])

        if geom_type == "MultiPolygon":
            for polygon in coords:
                # polygon[0] is the outer ring
                if self.point_in_polygon(lng, lat, polygon[0]):
                    return True
        elif geom_type == "Polygon":
            if coords and self.point_in_polygon(lng, lat, coords[0]):
                return True
        return False

    @classmethod
    def find_agencies_for_location(cls, lng, lat):
        """
        Return queryset of Company IDs whose active service areas
        contain the given point.
        """
        matching_agency_ids = set()
        for area in cls.objects.filter(is_active=True).select_related("agency"):
            if area.contains_point(lng, lat):
                matching_agency_ids.add(area.agency_id)
        return matching_agency_ids


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. AgencyContract — Auto-generated binding agreement
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgencyContract(models.Model):
    """
    Auto-generated legally-binding contract between the platform and an
    Agency.  Contains the agreed service areas (geofence snapshots) and
    a pricing table snapshot at the time of signing.

    Access to the PDF is gated until ALL required parties have signed.
    """

    STATUS_DRAFT = "draft"
    STATUS_PENDING_SIGNATURES = "pending_signatures"
    STATUS_FULLY_SIGNED = "fully_signed"
    STATUS_EXPIRED = "expired"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PENDING_SIGNATURES, "Pending Signatures"),
        (STATUS_FULLY_SIGNED, "Fully Signed"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_REVOKED, "Revoked"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    agency = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    version = models.PositiveIntegerField(
        default=1,
        help_text="Contract version number — increments on renegotiation.",
    )
    status = models.CharField(
        max_length=24, choices=STATUS_CHOICES, default=STATUS_DRAFT,
        db_index=True,
    )

    # ── Snapshot Data (frozen at contract generation time) ────────────
    service_areas_snapshot = models.JSONField(
        help_text="Array of AgencyServiceArea GeoJSON objects at signing time.",
    )
    pricing_snapshot = models.JSONField(
        help_text="Pricing table snapshot — service fees at contract generation.",
    )
    terms_text = models.TextField(
        help_text="Full contract terms as Markdown or plain text.",
    )

    # ── PDF ───────────────────────────────────────────────────────────
    pdf_file = models.FileField(
        upload_to="contracts/pdfs/%Y/%m/",
        blank=True, null=True,
        help_text="Generated PDF. Null until first generation.",
    )
    pdf_generated_at = models.DateTimeField(null=True, blank=True)
    document_hash = models.CharField(
        max_length=64, blank=True, default="",
        help_text="SHA-256 hash of the generated PDF for tamper detection.",
    )

    # ── Signing Requirements ─────────────────────────────────────────
    required_signers = models.JSONField(
        default=list,
        help_text=(
            "List of signer descriptors: "
            "[{'role': 'agency_owner', 'user_id': 42}, "
            "{'role': 'platform_admin', 'user_id': null}]"
        ),
    )

    # ── Timestamps ───────────────────────────────────────────────────
    effective_date = models.DateField(
        null=True, blank=True,
        help_text="Date the contract becomes effective (after all signatures).",
    )
    expiry_date = models.DateField(
        null=True, blank=True,
        help_text="Contract expiration date.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_contracts",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("agency", "version")]
        indexes = [
            models.Index(fields=["agency", "status"], name="idx_contract_agency_status"),
        ]

    def __str__(self):
        return f"Contract {self.agency.name} v{self.version} ({self.status})"

    @property
    def is_fully_signed(self):
        """Check if all required signers have signed."""
        if not self.required_signers:
            return False
        signed_count = self.signatures.filter(is_valid=True).count()
        return signed_count >= len(self.required_signers)

    @property
    def is_accessible(self):
        """PDF is only accessible once all parties have signed."""
        return self.status == self.STATUS_FULLY_SIGNED

    def check_and_finalize(self):
        """
        Called after each signature.  If all required signers have
        signed, transition to fully_signed and set effective date.
        """
        if self.is_fully_signed and self.status == self.STATUS_PENDING_SIGNATURES:
            self.status = self.STATUS_FULLY_SIGNED
            self.effective_date = timezone.now().date()
            self.save(update_fields=["status", "effective_date", "updated_at"])
            return True
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. ContractSignature — Per-party digital signature
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ContractSignature(models.Model):
    """
    Captures a single party's digital signature on a contract.
    Includes signer identity, IP address, timestamp, and a
    cryptographic hash binding the signature to the document version.
    """

    ROLE_AGENCY_OWNER = "agency_owner"
    ROLE_PLATFORM_ADMIN = "platform_admin"
    ROLE_CHOICES = [
        (ROLE_AGENCY_OWNER, "Agency Owner"),
        (ROLE_PLATFORM_ADMIN, "Platform Admin"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    contract = models.ForeignKey(
        AgencyContract,
        on_delete=models.CASCADE,
        related_name="signatures",
    )
    signer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contract_signatures",
    )
    signer_role = models.CharField(max_length=24, choices=ROLE_CHOICES)
    signer_full_name = models.CharField(
        max_length=256,
        help_text="Full legal name as typed by the signer.",
    )
    signer_email = models.EmailField()

    # ── Signature Data ───────────────────────────────────────────────
    signature_hash = models.CharField(
        max_length=64,
        help_text="SHA-256(document_hash + signer_email + timestamp).",
    )
    ip_address = models.GenericIPAddressField(
        help_text="IP address at time of signing.",
    )
    user_agent = models.TextField(
        blank=True, default="",
        help_text="Browser user agent string at signing.",
    )

    is_valid = models.BooleanField(default=True)
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["signed_at"]
        unique_together = [("contract", "signer_role")]

    def __str__(self):
        return f"Signature by {self.signer_full_name} ({self.signer_role}) on {self.contract}"

    def save(self, *args, **kwargs):
        if not self.signature_hash:
            # Generate binding hash
            raw = f"{self.contract.document_hash}:{self.signer_email}:{self.signed_at or timezone.now().isoformat()}"
            self.signature_hash = hashlib.sha256(raw.encode()).hexdigest()
        super().save(*args, **kwargs)
