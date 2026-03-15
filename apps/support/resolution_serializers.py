"""
Resolution Pipeline — DRF Serializers
=======================================

Serializers for the Complaint → Resolution → Notification flow.
"""

from rest_framework import serializers

from apps.support.resolution_models import (
    AgencyBlacklist,
    Complaint,
    ComplaintNotification,
    ResolutionAction,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Notification Serializer (nested read-only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplaintNotificationSerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(
        source="get_channel_display", read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True,
    )
    recipient_name = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintNotification
        fields = [
            "id", "uuid", "channel", "channel_display",
            "status", "status_display",
            "recipient", "recipient_name",
            "message_body", "sent_at", "error_detail",
            "created",
        ]
        read_only_fields = fields

    def get_recipient_name(self, obj):
        u = obj.recipient
        return f"{u.first_name} {u.last_name}".strip() or u.email


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Resolution Action Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ResolutionActionListSerializer(serializers.ModelSerializer):
    action_type_display = serializers.CharField(
        source="get_action_type_display", read_only=True,
    )
    execution_status_display = serializers.CharField(
        source="get_execution_status_display", read_only=True,
    )
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ResolutionAction
        fields = [
            "id", "uuid",
            "action_type", "action_type_display",
            "execution_status", "execution_status_display",
            "performed_by", "performed_by_name",
            "notes",
            "refund_amount", "stripe_refund_id",
            "redo_cleaning", "redo_assigned_company",
            "blacklisted_company", "reassigned_bookings_count",
            "executed_at", "created",
        ]
        read_only_fields = fields

    def get_performed_by_name(self, obj):
        u = obj.performed_by
        return f"{u.first_name} {u.last_name}".strip() or u.email


class ResolutionActionDetailSerializer(ResolutionActionListSerializer):
    notifications = ComplaintNotificationSerializer(many=True, read_only=True)

    class Meta(ResolutionActionListSerializer.Meta):
        fields = ResolutionActionListSerializer.Meta.fields + [
            "notifications",
        ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Complaint Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplaintListSerializer(serializers.ModelSerializer):
    scenario_display = serializers.CharField(
        source="get_scenario_display", read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True,
    )
    urgency_display = serializers.CharField(
        source="get_urgency_display", read_only=True,
    )
    resident_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    booking_short_id = serializers.IntegerField(
        source="booking.short_id", read_only=True,
    )
    actions_count = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = [
            "id", "uuid",
            "scenario", "scenario_display",
            "status", "status_display",
            "urgency", "urgency_display",
            "description",
            "resident", "resident_name",
            "booking", "booking_short_id",
            "cleaning",
            "company", "company_name",
            "assigned_to", "assigned_to_name",
            "escalated_at", "acknowledged_at", "resolved_at",
            "evidence_photos",
            "actions_count",
            "created", "updated",
        ]
        read_only_fields = fields

    def get_resident_name(self, obj):
        u = obj.resident
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            u = obj.assigned_to
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None

    def get_actions_count(self, obj):
        return obj.resolution_actions.count()


class ComplaintDetailSerializer(ComplaintListSerializer):
    resolution_actions = ResolutionActionDetailSerializer(
        many=True, read_only=True,
    )
    notifications = ComplaintNotificationSerializer(
        many=True, read_only=True,
    )

    class Meta(ComplaintListSerializer.Meta):
        fields = ComplaintListSerializer.Meta.fields + [
            "resolution_actions",
            "notifications",
        ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Complaint Create (Resident-facing)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplaintCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = [
            "booking", "cleaning", "scenario", "description",
            "evidence_photos",
        ]

    def validate_scenario(self, value):
        valid = [c[0] for c in Complaint.SCENARIO_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(
                f"Invalid scenario. Must be one of: {valid}"
            )
        return value

    def create(self, validated_data):
        validated_data["resident"] = self.context["request"].user
        return super().create(validated_data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Complaint Update (Support Architect)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplaintUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = ["status", "urgency", "assigned_to"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Resolution Action Input Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RefundInputSerializer(serializers.Serializer):
    refund_type = serializers.ChoiceField(
        choices=["refund_partial", "refund_full"],
    )
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True, default=None,
        help_text="Required for partial refund. USD amount.",
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, default="",
    )


class ScheduleRedoInputSerializer(serializers.Serializer):
    use_different_agency = serializers.BooleanField(
        required=False, default=False,
    )
    preferred_company_id = serializers.IntegerField(
        required=False, allow_null=True, default=None,
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, default="",
    )


class CancelBlacklistInputSerializer(serializers.Serializer):
    notes = serializers.CharField(
        required=False, allow_blank=True, default="",
    )


class AddNoteInputSerializer(serializers.Serializer):
    notes = serializers.CharField(required=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Agency Blacklist Serializer (read-only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgencyBlacklistSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    resident_name = serializers.SerializerMethodField()

    class Meta:
        model = AgencyBlacklist
        fields = [
            "id", "uuid",
            "resident", "resident_name",
            "company", "company_name",
            "complaint", "reason",
            "blacklisted_at", "created",
        ]
        read_only_fields = fields

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None

    def get_resident_name(self, obj):
        u = obj.resident
        return f"{u.first_name} {u.last_name}".strip() or u.email
