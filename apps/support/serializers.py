"""
Support & QA Serializers
========================

DRF serializers for the support ticket pipeline, spatial
verification QA flow, and GDPR media purge.
"""

from rest_framework import serializers

from apps.support.models import (
    Category,
    JobVerification,
    SupportTicket,
    SupportTicketMessage,
    SupportTicketStatusChange,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Nested / Read Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "uuid", "name", "slug"]
        read_only_fields = fields


class TicketMessageSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicketMessage
        fields = [
            "id", "uuid", "text", "user", "user_name",
            "created", "updated",
        ]
        read_only_fields = ["id", "uuid", "user", "user_name", "created", "updated"]

    def get_user_name(self, obj):
        u = obj.user
        return f"{u.first_name} {u.last_name}".strip() or u.email


class TicketStatusChangeSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicketStatusChange
        fields = ["id", "uuid", "status", "status_display", "user", "user_name", "created"]
        read_only_fields = fields

    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Support Ticket Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SupportTicketListSerializer(serializers.ModelSerializer):
    """Lean serializer for list views — no nested messages."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    user_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            "id", "uuid", "subject", "text",
            "status", "status_display",
            "priority", "priority_display",
            "sentiment", "sentiment_score",
            "ai_category", "ai_summary",
            "user", "user_name",
            "assigned_to", "assigned_to_name",
            "category", "category_name",
            "booking",
            "ai_triaged_at", "resolved_at",
            "created", "updated",
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        u = obj.user
        return f"{u.first_name} {u.last_name}".strip() or u.email

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            u = obj.assigned_to
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None


class SupportTicketDetailSerializer(SupportTicketListSerializer):
    """Full detail serializer with messages and status history."""

    messages = TicketMessageSerializer(many=True, read_only=True)
    status_changes = TicketStatusChangeSerializer(many=True, read_only=True)

    class Meta(SupportTicketListSerializer.Meta):
        fields = SupportTicketListSerializer.Meta.fields + [
            "comments", "resolution_notes",
            "ai_suggested_response", "ai_triaged_at",
            "messages", "status_changes",
        ]


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    """Create a new support ticket (for any authenticated user)."""

    class Meta:
        model = SupportTicket
        fields = ["subject", "text", "category", "booking"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class SupportTicketUpdateSerializer(serializers.ModelSerializer):
    """Update ticket — Support Architect can change status, priority, assign."""

    class Meta:
        model = SupportTicket
        fields = [
            "status", "priority", "assigned_to",
            "comments", "resolution_notes",
        ]


class TicketMessageCreateSerializer(serializers.ModelSerializer):
    """Add a message to a ticket thread."""

    class Meta:
        model = SupportTicketMessage
        fields = ["text"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data["support_ticket"] = self.context["ticket"]
        return super().create(validated_data)


class TicketResolveSerializer(serializers.Serializer):
    """One-click resolve with optional notes."""

    resolution_notes = serializers.CharField(required=False, allow_blank=True, default="")


class TicketAITriageSerializer(serializers.Serializer):
    """Read-only — AI triage results sent back from CF Worker webhook."""

    ticket_id = serializers.IntegerField()
    sentiment = serializers.CharField()
    sentiment_score = serializers.FloatField()
    priority = serializers.IntegerField()
    ai_category = serializers.CharField()
    ai_summary = serializers.CharField()
    ai_suggested_response = serializers.CharField()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Job Verification Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class JobVerificationListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    service_pro_name = serializers.SerializerMethodField()
    booking_uuid = serializers.UUIDField(source="booking.uuid", read_only=True)

    class Meta:
        model = JobVerification
        fields = [
            "id", "uuid", "booking", "booking_uuid",
            "service_pro", "service_pro_name",
            "media_type", "media_file",
            "status", "status_display",
            "cleanliness_score", "ai_summary",
            "issues_detected", "analyzed_at",
            "privacy_scrubbed", "ai_opt_out",
            "reviewed_by", "reviewer_notes", "reviewed_at",
            "created", "updated",
        ]
        read_only_fields = fields

    def get_service_pro_name(self, obj):
        u = obj.service_pro
        return f"{u.first_name} {u.last_name}".strip() or u.email


class JobVerificationDetailSerializer(JobVerificationListSerializer):
    class Meta(JobVerificationListSerializer.Meta):
        fields = JobVerificationListSerializer.Meta.fields + [
            "ai_analysis", "privacy_metadata", "r2_key",
        ]


class JobVerificationUploadSerializer(serializers.ModelSerializer):
    """Service Pro uploads a post-job photo/video."""

    class Meta:
        model = JobVerification
        fields = ["booking", "media_file", "media_type"]

    def validate_media_type(self, value):
        if value not in ("image", "video"):
            raise serializers.ValidationError("Must be 'image' or 'video'.")
        return value

    def create(self, validated_data):
        validated_data["service_pro"] = self.context["request"].user
        return super().create(validated_data)


class JobVerificationReviewSerializer(serializers.Serializer):
    """QA Inspector manual review override."""

    status = serializers.ChoiceField(
        choices=[
            (JobVerification.STATUS_APPROVED, "Approved"),
            (JobVerification.STATUS_REJECTED, "Rejected"),
        ],
    )
    reviewer_notes = serializers.CharField(required=False, allow_blank=True, default="")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GDPR Purge Media Serializer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PurgeMediaSerializer(serializers.Serializer):
    """
    Request body for the GDPR 'Right to be Forgotten' media purge.
    Requires the target Resident's user ID and a justification reason.
    """

    resident_id = serializers.IntegerField(
        help_text="The user ID of the Resident whose media should be purged.",
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="GDPR Right to be Forgotten",
        help_text="Justification for the purge (e.g., 'GDPR erasure request #1234').",
    )
