"""
Onboarding & Contracting — DRF API Views
==========================================

Endpoints:
  POST   /api/v1/onboarding/fuzzy-match/         — Fuzzy match agency name
  POST   /api/v1/onboarding/request-approval/     — Submit join request to agency
  GET    /api/v1/onboarding/approval-requests/     — List pending requests (Agency Owner)
  POST   /api/v1/onboarding/approval-requests/<uuid>/action/ — Approve/reject

  GET    /api/v1/onboarding/service-areas/         — List agency service areas
  POST   /api/v1/onboarding/service-areas/         — Create service area (geofence)
  GET    /api/v1/onboarding/service-areas/<uuid>/  — Detail
  PATCH  /api/v1/onboarding/service-areas/<uuid>/  — Update
  DELETE /api/v1/onboarding/service-areas/<uuid>/  — Soft-delete

  POST   /api/v1/onboarding/contracts/generate/    — Generate contract PDF
  GET    /api/v1/onboarding/contracts/             — List contracts
  GET    /api/v1/onboarding/contracts/<uuid>/      — Detail (gated until signed)
  POST   /api/v1/onboarding/contracts/<uuid>/sign/ — Digitally sign

  POST   /api/v1/onboarding/check-coverage/        — Check if location is covered
"""

import hashlib
import io
import json
import logging
from datetime import timedelta
from difflib import SequenceMatcher

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import (
    IsAgencyOwner,
    IsPlatformAdmin,
    IsServicePro,
    IsStaff,
)
from apps.companies.models import Company
from apps.onboarding.models import (
    AgencyContract,
    AgencyServiceArea,
    ContractSignature,
    ManagerApprovalRequest,
)
from apps.onboarding.serializers import (
    AgencyContractDetailSerializer,
    AgencyContractListSerializer,
    AgencyFuzzyMatchSerializer,
    AgencyMatchResultSerializer,
    AgencyServiceAreaSerializer,
    ApprovalActionSerializer,
    ContractSignInputSerializer,
    ContractSignatureSerializer,
    GenerateContractSerializer,
    ManagerApprovalRequestSerializer,
)
from apps.onboarding.pdf_generator import generate_contract_pdf

logger = logging.getLogger(__name__)

FUZZY_MATCH_THRESHOLD = 0.75


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. Fuzzy Match Agency Name
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FuzzyMatchAgencyView(APIView):
    """
    POST /api/v1/onboarding/fuzzy-match/

    Accepts { "agency_name": "..." } and returns ranked fuzzy matches
    against existing Company records.
    """
    permission_classes = [permissions.IsAuthenticated & IsServicePro]

    def post(self, request):
        serializer = AgencyFuzzyMatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        typed_name = serializer.validated_data["agency_name"].strip()

        companies = Company.objects.filter(is_active=True).values("id", "name", "uuid")
        matches = []

        for company in companies:
            score = SequenceMatcher(
                None,
                typed_name.lower(),
                (company["name"] or "").lower(),
            ).ratio()

            if score >= FUZZY_MATCH_THRESHOLD:
                matches.append({
                    "agency_id": company["id"],
                    "agency_name": company["name"],
                    "match_score": round(score, 4),
                    "uuid": company["uuid"],
                })

        matches.sort(key=lambda m: m["match_score"], reverse=True)
        return Response(
            AgencyMatchResultSerializer(matches[:5], many=True).data,
            status=status.HTTP_200_OK,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. Request Approval to Join Agency
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RequestApprovalView(APIView):
    """
    POST /api/v1/onboarding/request-approval/

    Body: { "agency_id": 42, "typed_agency_name": "Acme Clean", "match_score": 0.89 }
    Creates a ManagerApprovalRequest and pushes a WebSocket event
    to the Agency Owner.
    """
    permission_classes = [permissions.IsAuthenticated & IsServicePro]

    def post(self, request):
        agency_id = request.data.get("agency_id")
        typed_name = request.data.get("typed_agency_name", "")
        match_score = request.data.get("match_score", 0.0)

        try:
            agency = Company.objects.get(id=agency_id, is_active=True)
        except Company.DoesNotExist:
            return Response(
                {"error": "Agency not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check for existing pending request
        existing = ManagerApprovalRequest.objects.filter(
            service_pro=request.user,
            agency=agency,
            status=ManagerApprovalRequest.STATUS_PENDING,
        ).first()
        if existing:
            return Response(
                {"error": "You already have a pending request for this agency.",
                 "request_uuid": str(existing.uuid)},
                status=status.HTTP_409_CONFLICT,
            )

        approval = ManagerApprovalRequest.objects.create(
            service_pro=request.user,
            agency=agency,
            typed_agency_name=typed_name,
            match_score=match_score,
            expires_at=timezone.now() + timedelta(hours=72),
        )

        # ── WebSocket push to Agency Owner(s) ─────────────────────────
        _notify_agency_owners(agency, approval)

        return Response(
            ManagerApprovalRequestSerializer(approval).data,
            status=status.HTTP_201_CREATED,
        )


def _notify_agency_owners(agency, approval):
    """
    Push a WebSocket message to all Agency Owners of the matched company.
    Uses Django Channels' channel layer (async_to_sync).
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning("No channel layer configured — skipping WS notification.")
            return

        group_name = f"agency_{agency.id}_approvals"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "approval.request",
                "data": {
                    "uuid": str(approval.uuid),
                    "service_pro_name": approval.service_pro.get_full_name() or approval.service_pro.email,
                    "service_pro_email": approval.service_pro.email,
                    "typed_agency_name": approval.typed_agency_name,
                    "match_score": approval.match_score,
                    "created_at": approval.created_at.isoformat(),
                    "expires_at": approval.expires_at.isoformat(),
                },
            },
        )
        logger.info(f"WS approval notification sent to group {group_name}")
    except ImportError:
        logger.warning("Django Channels not installed — skipping WS notification.")
    except Exception as e:
        logger.error(f"Failed to send WS approval notification: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. Agency Owner — Approval Queue
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ApprovalRequestListView(generics.ListAPIView):
    """
    GET /api/v1/onboarding/approval-requests/

    Lists approval requests for the authenticated Agency Owner's company.
    Supports ?status=pending|approved|rejected filter.
    """
    serializer_class = ManagerApprovalRequestSerializer
    permission_classes = [permissions.IsAuthenticated & (IsAgencyOwner | IsPlatformAdmin)]

    def get_queryset(self):
        qs = ManagerApprovalRequest.objects.select_related(
            "service_pro", "agency", "reviewed_by"
        )
        if self.request.user.role == self.request.user.ROLE_AGENCY_OWNER:
            qs = qs.filter(agency=self.request.user.company)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class ApprovalActionView(APIView):
    """
    POST /api/v1/onboarding/approval-requests/<uuid>/action/

    Body: { "action": "approve" | "reject", "rejection_reason": "..." }
    """
    permission_classes = [permissions.IsAuthenticated & (IsAgencyOwner | IsPlatformAdmin)]

    def post(self, request, uuid):
        try:
            approval = ManagerApprovalRequest.objects.select_related(
                "service_pro", "agency"
            ).get(uuid=uuid)
        except ManagerApprovalRequest.DoesNotExist:
            return Response(
                {"error": "Approval request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify ownership (Agency Owner must belong to the same company)
        if (
            request.user.role == request.user.ROLE_AGENCY_OWNER
            and request.user.company_id != approval.agency_id
        ):
            return Response(
                {"error": "Not authorized for this agency."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if approval.status != ManagerApprovalRequest.STATUS_PENDING:
            return Response(
                {"error": f"Request already {approval.status}."},
                status=status.HTTP_409_CONFLICT,
            )

        if approval.is_expired:
            approval.status = ManagerApprovalRequest.STATUS_EXPIRED
            approval.save(update_fields=["status", "updated_at"])
            return Response(
                {"error": "Request has expired."},
                status=status.HTTP_410_GONE,
            )

        serializer = ApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        if action == "approve":
            approval.approve(request.user)
        else:
            approval.reject(
                request.user,
                serializer.validated_data.get("rejection_reason", ""),
            )

        # Notify the Service Pro via WebSocket
        _notify_service_pro(approval)

        return Response(
            ManagerApprovalRequestSerializer(approval).data,
            status=status.HTTP_200_OK,
        )


def _notify_service_pro(approval):
    """Push approval/rejection result to the Service Pro's WS channel."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        group_name = f"user_{approval.service_pro_id}_notifications"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "approval.result",
                "data": {
                    "uuid": str(approval.uuid),
                    "agency_name": approval.agency.name,
                    "status": approval.status,
                    "rejection_reason": approval.rejection_reason,
                },
            },
        )
    except Exception as e:
        logger.error(f"Failed to send WS notification to Service Pro: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. Agency Service Areas (Geofence CRUD)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ServiceAreaListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/onboarding/service-areas/

    Agency Owners manage their service area geofences.
    """
    serializer_class = AgencyServiceAreaSerializer
    permission_classes = [permissions.IsAuthenticated & (IsAgencyOwner | IsPlatformAdmin)]

    def get_queryset(self):
        qs = AgencyServiceArea.objects.select_related("agency")
        if self.request.user.role == self.request.user.ROLE_AGENCY_OWNER:
            qs = qs.filter(agency=self.request.user.company)
        return qs

    def perform_create(self, serializer):
        serializer.save(agency=self.request.user.company)


class ServiceAreaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/v1/onboarding/service-areas/<uuid>/
    """
    serializer_class = AgencyServiceAreaSerializer
    permission_classes = [permissions.IsAuthenticated & (IsAgencyOwner | IsPlatformAdmin)]
    lookup_field = "uuid"

    def get_queryset(self):
        qs = AgencyServiceArea.objects.select_related("agency")
        if self.request.user.role == self.request.user.ROLE_AGENCY_OWNER:
            qs = qs.filter(agency=self.request.user.company)
        return qs

    def perform_destroy(self, instance):
        # Soft delete — deactivate instead of removing
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  5. Coverage Check — Point-in-Polygon
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CheckCoverageView(APIView):
    """
    POST /api/v1/onboarding/check-coverage/

    Body: { "lng": -95.3698, "lat": 29.7604 }
    Returns agencies whose service areas cover the given point.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        lng = request.data.get("lng")
        lat = request.data.get("lat")

        if lng is None or lat is None:
            return Response(
                {"error": "Both 'lng' and 'lat' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            lng, lat = float(lng), float(lat)
        except (TypeError, ValueError):
            return Response(
                {"error": "lng and lat must be numeric."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        matching_ids = AgencyServiceArea.find_agencies_for_location(lng, lat)

        agencies = Company.objects.filter(id__in=matching_ids, is_active=True).values(
            "id", "name", "uuid"
        )

        return Response(
            {
                "covered": len(agencies) > 0,
                "agencies": list(agencies),
                "location": {"lng": lng, "lat": lat},
            },
            status=status.HTTP_200_OK,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  6. Contract Generation + Signing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ContractGenerateView(APIView):
    """
    POST /api/v1/onboarding/contracts/generate/

    Generates a legally binding contract PDF with the agency's current
    service areas and pricing snapshot.  Returns the contract record.
    """
    permission_classes = [permissions.IsAuthenticated & (IsAgencyOwner | IsPlatformAdmin)]

    def post(self, request):
        serializer = GenerateContractSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        agency_id = serializer.validated_data["agency_id"]
        expiry_months = serializer.validated_data["expiry_months"]

        try:
            agency = Company.objects.get(id=agency_id, is_active=True)
        except Company.DoesNotExist:
            return Response(
                {"error": "Agency not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify ownership
        if (
            request.user.role == request.user.ROLE_AGENCY_OWNER
            and request.user.company_id != agency_id
        ):
            return Response(
                {"error": "Not authorized for this agency."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Snapshot current service areas ─────────────────────────────
        areas = AgencyServiceArea.objects.filter(
            agency=agency, is_active=True
        )
        areas_snapshot = []
        for area in areas:
            areas_snapshot.append({
                "name": area.name,
                "geojson": area.geojson,
                "color": area.color,
            })

        if not areas_snapshot:
            return Response(
                {"error": "Agency must have at least one service area defined."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Snapshot current pricing ───────────────────────────────────
        from apps.services.models import ServiceFeesSnapshot
        latest_snapshot = ServiceFeesSnapshot.objects.order_by("-created").first()
        pricing_data = {}
        if latest_snapshot:
            fees = latest_snapshot.get_fees()
            pricing_data = {
                "snapshot_date": str(latest_snapshot.created),
                "fees": [
                    {
                        "service_name": str(fee.service),
                        "client_fee": str(fee.client_fee),
                        "subcontractor_fee": str(fee.subcontractor_fee),
                    }
                    for fee in fees
                ],
            }

        # ── Calculate version ─────────────────────────────────────────
        latest_version = (
            AgencyContract.objects.filter(agency=agency)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        ) or 0
        new_version = latest_version + 1

        # ── Generate terms ────────────────────────────────────────────
        terms = _generate_terms_text(agency, areas_snapshot, pricing_data)

        # ── Create contract record ────────────────────────────────────
        now = timezone.now()
        contract = AgencyContract.objects.create(
            agency=agency,
            version=new_version,
            status=AgencyContract.STATUS_PENDING_SIGNATURES,
            service_areas_snapshot=areas_snapshot,
            pricing_snapshot=pricing_data,
            terms_text=terms,
            required_signers=[
                {"role": "agency_owner", "user_id": None},
                {"role": "platform_admin", "user_id": None},
            ],
            expiry_date=(now + timedelta(days=30 * expiry_months)).date(),
            created_by=request.user,
        )

        # ── Generate PDF ──────────────────────────────────────────────
        try:
            pdf_bytes = generate_contract_pdf(contract, agency, areas_snapshot, pricing_data)
            doc_hash = hashlib.sha256(pdf_bytes).hexdigest()
            filename = f"cleanable_contract_{agency.name.replace(' ', '_')}_v{new_version}.pdf"

            contract.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
            contract.document_hash = doc_hash
            contract.pdf_generated_at = now
            contract.save(update_fields=[
                "pdf_file", "document_hash", "pdf_generated_at", "updated_at",
            ])
        except Exception as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            # Contract still exists, PDF can be regenerated

        return Response(
            AgencyContractDetailSerializer(contract).data,
            status=status.HTTP_201_CREATED,
        )


def _generate_terms_text(agency, areas, pricing):
    """Generate the contract terms as Markdown text."""
    area_names = ", ".join(a["name"] for a in areas)
    fee_lines = ""
    if pricing.get("fees"):
        for fee in pricing["fees"]:
            fee_lines += f"  - {fee['service_name']}: Client ${fee['client_fee']}, Subcontractor ${fee['subcontractor_fee']}\n"

    return f"""# SERVICE AGREEMENT

## Between Cleanable Platform ("Platform") and {agency.name} ("Agency")

### 1. SCOPE OF SERVICES
The Agency agrees to provide cleaning and maintenance services within the
agreed-upon Service Areas as defined in this contract.

### 2. SERVICE AREAS
The Agency is authorized to accept and fulfill bookings from Residents
whose property locations fall within the following geographic boundaries:

**Designated Areas:** {area_names}

The exact boundaries are defined by the MultiPolygon geofence coordinates
attached to this contract as Appendix A. The Platform will only route
bookings to the Agency when the Resident's property coordinates fall
within these boundaries.

### 3. PRICING
The following pricing schedule applies at the time of contract execution:

{fee_lines}
Pricing is subject to periodic review. Changes require a contract amendment
signed by both parties.

### 4. ASSIGNMENT & EXCLUSIVITY
The Platform may assign bookings to any Agency whose service area covers
the Resident's location. This agreement does not grant geographic
exclusivity unless explicitly stated in a separate addendum.

### 5. QUALITY STANDARDS
The Agency agrees to maintain quality standards as measured by the
Platform's AI-driven QA scoring system. Consistent scores below the
Platform minimum may result in contract review.

### 6. DATA HANDLING & PRIVACY
Both parties agree to handle all personal data in compliance with
applicable privacy laws (GDPR, CCPA) and the Platform's Privacy Policy.
Verification media is subject to the Platform's automated privacy
detection and GDPR purge capabilities.

### 7. TERM & TERMINATION
This agreement is effective upon digital signature by all parties and
remains in effect until the Expiry Date unless terminated earlier by
either party with 30 days written notice.

### 8. DIGITAL SIGNATURES
Both parties acknowledge that digital signatures applied through the
Platform are legally binding under the ESIGN Act and UETA. Each
signature is cryptographically bound to the document via SHA-256 hash
and timestamped with the signer's IP address.

### 9. GOVERNING LAW
This agreement shall be governed by the laws of the State of Texas.

---
*Generated by Cleanable Platform on {timezone.now().strftime('%B %d, %Y at %I:%M %p %Z')}*
"""


class ContractListView(generics.ListAPIView):
    """GET /api/v1/onboarding/contracts/"""
    serializer_class = AgencyContractListSerializer
    permission_classes = [permissions.IsAuthenticated & (IsAgencyOwner | IsPlatformAdmin)]

    def get_queryset(self):
        qs = AgencyContract.objects.select_related("agency")
        if self.request.user.role == self.request.user.ROLE_AGENCY_OWNER:
            qs = qs.filter(agency=self.request.user.company)
        return qs


class ContractDetailView(generics.RetrieveAPIView):
    """GET /api/v1/onboarding/contracts/<uuid>/"""
    serializer_class = AgencyContractDetailSerializer
    permission_classes = [permissions.IsAuthenticated & (IsAgencyOwner | IsPlatformAdmin)]
    lookup_field = "uuid"

    def get_queryset(self):
        qs = AgencyContract.objects.select_related("agency").prefetch_related("signatures")
        if self.request.user.role == self.request.user.ROLE_AGENCY_OWNER:
            qs = qs.filter(agency=self.request.user.company)
        return qs


class ContractSignView(APIView):
    """
    POST /api/v1/onboarding/contracts/<uuid>/sign/

    Body: { "signer_full_name": "Jane Doe", "signer_role": "agency_owner" }
    Creates a ContractSignature and checks if contract is now fully signed.
    """
    permission_classes = [permissions.IsAuthenticated & (IsAgencyOwner | IsPlatformAdmin)]

    def post(self, request, uuid):
        try:
            contract = AgencyContract.objects.get(uuid=uuid)
        except AgencyContract.DoesNotExist:
            return Response(
                {"error": "Contract not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if contract.status not in (
            AgencyContract.STATUS_PENDING_SIGNATURES,
            AgencyContract.STATUS_DRAFT,
        ):
            return Response(
                {"error": f"Contract is {contract.status}, cannot sign."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ContractSignInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        signer_role = serializer.validated_data["signer_role"]

        # Verify the signer's actual role matches what they claim
        if signer_role == ContractSignature.ROLE_AGENCY_OWNER:
            if request.user.role != request.user.ROLE_AGENCY_OWNER:
                return Response(
                    {"error": "Only Agency Owners can sign as agency_owner."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if request.user.company_id != contract.agency_id:
                return Response(
                    {"error": "Not authorized for this agency's contract."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif signer_role == ContractSignature.ROLE_PLATFORM_ADMIN:
            if not (request.user.is_superuser and request.user.role == request.user.ROLE_PLATFORM_ADMIN):
                return Response(
                    {"error": "Only Platform Admins can sign as platform_admin."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Check if this role already signed
        if contract.signatures.filter(signer_role=signer_role, is_valid=True).exists():
            return Response(
                {"error": f"A {signer_role} has already signed this contract."},
                status=status.HTTP_409_CONFLICT,
            )

        # Get client IP
        ip = _get_client_ip(request)

        signature = ContractSignature.objects.create(
            contract=contract,
            signer=request.user,
            signer_role=signer_role,
            signer_full_name=serializer.validated_data["signer_full_name"],
            signer_email=request.user.email,
            ip_address=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        # Check if fully signed
        finalized = contract.check_and_finalize()

        return Response(
            {
                "signature": ContractSignatureSerializer(signature).data,
                "contract_status": contract.status,
                "is_fully_signed": finalized,
            },
            status=status.HTTP_201_CREATED,
        )


def _get_client_ip(request):
    """Extract real client IP, respecting proxy headers."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")
