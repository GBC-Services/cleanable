"""
Payroll & Fiscal Auditing Serializers
======================================
"""

from rest_framework import serializers

from .models import ActivityStatement, PayrollCycle, TaxDocument, PaymentHold


# ── Activity Statement ────────────────────────────────────────────────

class ActivityStatementSerializer(serializers.ModelSerializer):
    service_pro_name = serializers.SerializerMethodField()
    service_pro_email = serializers.SerializerMethodField()
    agency_name = serializers.SerializerMethodField()
    booking_short_id = serializers.SerializerMethodField()

    class Meta:
        model = ActivityStatement
        fields = [
            "uuid",
            "cleaning",
            "booking",
            "booking_short_id",
            "agency",
            "agency_name",
            "service_pro",
            "service_pro_name",
            "service_pro_email",
            "client_charged",
            "agency_fee",
            "pro_wage",
            "platform_fee",
            "tip_amount",
            "service_names",
            "scheduled_date",
            "completed_at",
            "payroll_cycle",
            "created",
        ]
        read_only_fields = fields

    def get_service_pro_name(self, obj):
        return obj.service_pro.get_full_name() if obj.service_pro else ""

    def get_service_pro_email(self, obj):
        return obj.service_pro.email if obj.service_pro else ""

    def get_agency_name(self, obj):
        return obj.agency.name if obj.agency else ""

    def get_booking_short_id(self, obj):
        return obj.booking.short_id if obj.booking else None


# ── Payroll Cycle ─────────────────────────────────────────────────────

class PayrollCycleListSerializer(serializers.ModelSerializer):
    agency_name = serializers.SerializerMethodField()
    has_active_hold = serializers.SerializerMethodField()
    line_item_count = serializers.SerializerMethodField()

    class Meta:
        model = PayrollCycle
        fields = [
            "uuid",
            "agency",
            "agency_name",
            "period_start",
            "period_end",
            "status",
            "total_jobs",
            "total_client_charged",
            "total_agency_fees",
            "total_pro_wages",
            "total_platform_fees",
            "total_tips",
            "stripe_transfer_id",
            "paid_at",
            "has_active_hold",
            "line_item_count",
            "created",
        ]
        read_only_fields = fields

    def get_agency_name(self, obj):
        return obj.agency.name if obj.agency else ""

    def get_has_active_hold(self, obj):
        return obj.holds.filter(status=PaymentHold.STATUS_ACTIVE).exists()

    def get_line_item_count(self, obj):
        return obj.line_items.count()


class PayrollCycleDetailSerializer(PayrollCycleListSerializer):
    line_items = ActivityStatementSerializer(many=True, read_only=True)
    holds = serializers.SerializerMethodField()

    class Meta(PayrollCycleListSerializer.Meta):
        fields = PayrollCycleListSerializer.Meta.fields + [
            "line_items",
            "holds",
            "csv_file",
        ]

    def get_holds(self, obj):
        return PaymentHoldSerializer(
            obj.holds.all(), many=True
        ).data


# ── Tax Document ──────────────────────────────────────────────────────

class TaxDocumentSerializer(serializers.ModelSerializer):
    agency_name = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TaxDocument
        fields = [
            "uuid",
            "agency",
            "agency_name",
            "uploaded_by",
            "uploaded_by_name",
            "document_type",
            "file",
            "original_filename",
            "tax_year",
            "status",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "notes",
            "created",
        ]
        read_only_fields = [
            "uuid", "uploaded_by", "uploaded_by_name",
            "reviewed_by", "reviewed_by_name", "reviewed_at",
            "created", "agency_name",
        ]

    def get_agency_name(self, obj):
        return obj.agency.name if obj.agency else ""

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() if obj.uploaded_by else ""

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.get_full_name() if obj.reviewed_by else ""


class TaxDocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(
        choices=TaxDocument.DOC_TYPE_CHOICES,
    )
    file = serializers.FileField()
    tax_year = serializers.IntegerField(min_value=2020, max_value=2099)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class TaxDocumentReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            (TaxDocument.STATUS_APPROVED, "Approved"),
            (TaxDocument.STATUS_REJECTED, "Rejected"),
        ]
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")


# ── Payment Hold ──────────────────────────────────────────────────────

class PaymentHoldSerializer(serializers.ModelSerializer):
    placed_by_name = serializers.SerializerMethodField()
    released_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PaymentHold
        fields = [
            "uuid",
            "payroll_cycle",
            "placed_by",
            "placed_by_name",
            "reason",
            "status",
            "released_by",
            "released_by_name",
            "released_at",
            "release_notes",
            "created",
        ]
        read_only_fields = [
            "uuid", "placed_by", "placed_by_name",
            "released_by", "released_by_name", "released_at",
            "created",
        ]

    def get_placed_by_name(self, obj):
        return obj.placed_by.get_full_name() if obj.placed_by else ""

    def get_released_by_name(self, obj):
        return obj.released_by.get_full_name() if obj.released_by else ""


class PaymentHoldCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10)


class PaymentHoldReleaseSerializer(serializers.Serializer):
    release_notes = serializers.CharField(
        required=False, allow_blank=True, default="",
    )
