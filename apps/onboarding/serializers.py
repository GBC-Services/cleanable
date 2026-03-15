"""
Onboarding & Contracting — DRF Serializers
=============================================
"""

from rest_framework import serializers
from apps.onboarding.models import (
    AgencyContract,
    AgencyServiceArea,
    ContractSignature,
    ManagerApprovalRequest,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Service Pro Registration — Fuzzy Match
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgencyFuzzyMatchSerializer(serializers.Serializer):
    """Input: Service Pro types their agency name."""
    agency_name = serializers.CharField(max_length=256)


class AgencyMatchResultSerializer(serializers.Serializer):
    """Output: fuzzy match results."""
    agency_id = serializers.IntegerField()
    agency_name = serializers.CharField()
    match_score = serializers.FloatField()
    uuid = serializers.UUIDField()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Manager Approval Requests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ManagerApprovalRequestSerializer(serializers.ModelSerializer):
    service_pro_name = serializers.SerializerMethodField()
    service_pro_email = serializers.SerializerMethodField()
    agency_name = serializers.SerializerMethodField()

    class Meta:
        model = ManagerApprovalRequest
        fields = [
            "uuid", "service_pro", "service_pro_name", "service_pro_email",
            "agency", "agency_name", "typed_agency_name", "match_score",
            "status", "reviewed_by", "reviewed_at", "rejection_reason",
            "expires_at", "created_at",
        ]
        read_only_fields = [
            "uuid", "service_pro", "agency", "typed_agency_name",
            "match_score", "reviewed_by", "reviewed_at", "created_at",
        ]

    def get_service_pro_name(self, obj):
        return obj.service_pro.get_full_name() or obj.service_pro.email

    def get_service_pro_email(self, obj):
        return obj.service_pro.email

    def get_agency_name(self, obj):
        return obj.agency.name


class ApprovalActionSerializer(serializers.Serializer):
    """Input for approve/reject action."""
    action = serializers.ChoiceField(choices=["approve", "reject"])
    rejection_reason = serializers.CharField(required=False, default="")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Agency Service Areas (Geofence)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgencyServiceAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgencyServiceArea
        fields = [
            "uuid", "agency", "name", "geojson", "color",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["uuid", "agency", "created_at", "updated_at"]

    def validate_geojson(self, value):
        """Ensure valid GeoJSON with MultiPolygon or Polygon geometry."""
        geom = value.get("geometry", value)
        geom_type = geom.get("type", "")
        if geom_type not in ("Polygon", "MultiPolygon"):
            raise serializers.ValidationError(
                f"Geometry type must be Polygon or MultiPolygon, got '{geom_type}'."
            )
        coords = geom.get("coordinates", [])
        if not coords:
            raise serializers.ValidationError("Geometry coordinates cannot be empty.")
        return value


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Contracts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ContractSignatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractSignature
        fields = [
            "uuid", "signer_role", "signer_full_name", "signer_email",
            "signature_hash", "ip_address", "is_valid", "signed_at",
        ]
        read_only_fields = [
            "uuid", "signature_hash", "ip_address", "is_valid", "signed_at",
        ]


class AgencyContractListSerializer(serializers.ModelSerializer):
    agency_name = serializers.SerializerMethodField()
    signatures_count = serializers.SerializerMethodField()
    required_signatures_count = serializers.SerializerMethodField()

    class Meta:
        model = AgencyContract
        fields = [
            "uuid", "agency", "agency_name", "version", "status",
            "effective_date", "expiry_date", "created_at",
            "signatures_count", "required_signatures_count",
        ]

    def get_agency_name(self, obj):
        return obj.agency.name

    def get_signatures_count(self, obj):
        return obj.signatures.filter(is_valid=True).count()

    def get_required_signatures_count(self, obj):
        return len(obj.required_signers) if obj.required_signers else 0


class AgencyContractDetailSerializer(serializers.ModelSerializer):
    signatures = ContractSignatureSerializer(many=True, read_only=True)
    agency_name = serializers.SerializerMethodField()

    class Meta:
        model = AgencyContract
        fields = [
            "uuid", "agency", "agency_name", "version", "status",
            "service_areas_snapshot", "pricing_snapshot", "terms_text",
            "pdf_file", "pdf_generated_at", "document_hash",
            "required_signers", "effective_date", "expiry_date",
            "created_at", "updated_at", "signatures",
        ]

    def get_agency_name(self, obj):
        return obj.agency.name

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Gate PDF access: redact URL if not fully signed
        if not instance.is_accessible:
            data["pdf_file"] = None
            data["terms_text"] = "[Contract access restricted until all parties have signed]"
        return data


class ContractSignInputSerializer(serializers.Serializer):
    """Input for digitally signing a contract."""
    signer_full_name = serializers.CharField(max_length=256)
    signer_role = serializers.ChoiceField(choices=ContractSignature.ROLE_CHOICES)


class GenerateContractSerializer(serializers.Serializer):
    """Input for generating a new contract."""
    agency_id = serializers.IntegerField()
    expiry_months = serializers.IntegerField(default=12, min_value=1, max_value=60)
