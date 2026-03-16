"""
Governance API Views
====================

Endpoints for:
  - Platform Admin: manage feature toggles, read audit logs
  - All users: read/update own privacy preferences
  - Support Architects: request and manage break-glass sessions
  - Break-glass overrides: apply/revert privacy overrides
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from .models import (
    BreakGlassSession,
    GovernanceAuditLog,
    NotificationPreference,
    PlatformIntegration,
    PrivacyPreferences,
    SystemFeatureToggle,
)
from .permissions import (
    BreakGlassOverride,
    CanManageFeatureToggles,
    CanManageOwnPrivacy,
    CanReadAuditLogs,
    CanRevokeBreakGlass,
    HasBreakGlassAccess,
)
from .serializers import (
    BreakGlassOverrideSerializer,
    BreakGlassRequestSerializer,
    BreakGlassSessionSerializer,
    GovernanceAuditLogSerializer,
    LifecycleEventSerializer,
    NotificationPreferenceBulkUpdateSerializer,
    NotificationPreferenceSerializer,
    PlatformIntegrationListSerializer,
    PlatformIntegrationSerializer,
    PrivacyPreferencesAdminSerializer,
    PrivacyPreferencesSerializer,
    SystemFeatureToggleListSerializer,
    SystemFeatureToggleSerializer,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. SystemFeatureToggle — Platform Admin Only
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FeatureToggleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/v1/governance/features/         — list all toggles
    GET  /api/v1/governance/features/{slug}/   — detail
    PATCH /api/v1/governance/features/{slug}/  — toggle is_enabled

    Platform Admin only.  Feature slugs are seeded via migration;
    admins can only flip ``is_enabled``, not create or delete.
    """

    permission_classes = [permissions.IsAuthenticated, CanManageFeatureToggles]
    lookup_field = "slug"

    def get_queryset(self):
        qs = SystemFeatureToggle.objects.all()
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return SystemFeatureToggleListSerializer
        return SystemFeatureToggleSerializer

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, slug=None):
        """
        POST /api/v1/governance/features/{slug}/toggle/
        Flips the current state (enabled ↔ disabled).
        """
        instance = self.get_object()
        instance.is_enabled = not instance.is_enabled
        instance.toggled_by = request.user
        instance.toggled_at = timezone.now()
        instance.save(update_fields=[
            "is_enabled", "toggled_by", "toggled_at", "updated_at",
        ])
        return Response(SystemFeatureToggleSerializer(instance).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. PrivacyPreferences — Self-Service + Admin
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MyPrivacyView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/governance/privacy/me/   — read own preferences
    PATCH /api/v1/governance/privacy/me/  — update own preferences

    Auto-creates PrivacyPreferences on first access.
    Fields are role-filtered by the serializer.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PrivacyPreferencesSerializer

    def get_object(self):
        prefs, _ = PrivacyPreferences.objects.get_or_create(
            user=self.request.user,
        )
        return prefs


class PrivacyAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/governance/privacy/admin/         — list all users' prefs
    GET /api/v1/governance/privacy/admin/{id}/     — detail

    Platform Admin only.  Read-only access to all user privacy prefs.
    """

    permission_classes = [permissions.IsAuthenticated, CanManageFeatureToggles]
    serializer_class = PrivacyPreferencesAdminSerializer
    queryset = PrivacyPreferences.objects.select_related("user").all()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. Break-Glass Sessions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class BreakGlassViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST /api/v1/governance/break-glass/           — request new session
    GET  /api/v1/governance/break-glass/            — list sessions
    GET  /api/v1/governance/break-glass/{id}/       — session detail
    POST /api/v1/governance/break-glass/{id}/activate/
    POST /api/v1/governance/break-glass/{id}/revoke/
    POST /api/v1/governance/break-glass/{id}/apply-override/
    """

    def get_permissions(self):
        if self.action in ("create", "activate", "apply_override"):
            return [permissions.IsAuthenticated(), HasBreakGlassAccess()]
        if self.action == "revoke":
            return [permissions.IsAuthenticated(), CanRevokeBreakGlass()]
        # list/retrieve: Support Architects + Platform Admins
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = BreakGlassSession.objects.select_related(
            "initiated_by", "target_user", "revoked_by",
        )
        # Support Architects see only their own sessions
        if user.role == User.ROLE_SUPPORT_ARCHITECT:
            return qs.filter(initiated_by=user)
        # Platform Admins see all
        if user.role == User.ROLE_PLATFORM_ADMIN and user.is_superuser:
            return qs.all()
        return qs.none()

    def get_serializer_class(self):
        if self.action == "create":
            return BreakGlassRequestSerializer
        if self.action == "apply_override":
            return BreakGlassOverrideSerializer
        return BreakGlassSessionSerializer

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Activate a pending break-glass session."""
        session = self.get_object()
        try:
            session.activate()
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(BreakGlassSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """Early-terminate an active break-glass session."""
        session = self.get_object()
        self.check_object_permissions(request, session)
        try:
            session.revoke(revoked_by_user=request.user)
            # Revert any overrides on the target user's privacy
            try:
                prefs = session.target_user.privacy_preferences
                if prefs.is_overridden:
                    prefs.revert_override()
            except PrivacyPreferences.DoesNotExist:
                pass
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(BreakGlassSessionSerializer(session).data)

    @action(detail=True, methods=["post"], url_path="apply-override")
    def apply_override(self, request, pk=None):
        """
        Apply privacy overrides during an active break-glass session.

        Payload: {"session_id": "...", "overrides": {"field": true}}
        """
        session = self.get_object()

        if not session.is_active:
            return Response(
                {"detail": "Session is no longer active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BreakGlassOverrideSerializer(data={
            "session_id": str(session.id),
            "overrides": request.data.get("overrides", {}),
        })
        serializer.is_valid(raise_exception=True)

        overrides = serializer.validated_data["overrides"]

        # Get or create the target user's privacy prefs
        prefs, _ = PrivacyPreferences.objects.get_or_create(
            user=session.target_user,
        )

        # Record original values before override
        original_values = {}
        for field_name, new_value in overrides.items():
            original_values[field_name] = {
                "original": getattr(prefs, field_name, None),
                "overridden_to": new_value,
            }
            setattr(prefs, field_name, new_value)

        # Mark as overridden
        prefs.is_overridden = True
        prefs.overridden_by = request.user
        prefs.overridden_at = timezone.now()
        prefs.override_reason = session.reason
        prefs.override_expires_at = session.expires_at
        prefs._changed_by = request.user
        prefs.save()

        # Store the override snapshot on the session
        session.overrides_applied = original_values
        session.save(update_fields=["overrides_applied", "updated_at"])

        return Response({
            "detail": "Privacy overrides applied.",
            "overrides_applied": original_values,
            "expires_at": session.expires_at,
        })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. GovernanceAuditLog — Platform Admin Read-Only
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/governance/audit-logs/        — list all audit entries
    GET /api/v1/governance/audit-logs/{id}/    — detail

    Platform Admin only.  Supports filtering:
      - ?action=feature_toggled
      - ?severity=critical
      - ?actor_email=admin@example.com
      - ?since=2026-01-01T00:00:00Z
    """

    permission_classes = [permissions.IsAuthenticated, CanReadAuditLogs]
    serializer_class = GovernanceAuditLogSerializer

    def get_queryset(self):
        qs = GovernanceAuditLog.objects.all()

        action_filter = self.request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)

        severity_filter = self.request.query_params.get("severity")
        if severity_filter:
            qs = qs.filter(severity=severity_filter)

        actor_email = self.request.query_params.get("actor_email")
        if actor_email:
            qs = qs.filter(actor_email__icontains=actor_email)

        since = self.request.query_params.get("since")
        if since:
            qs = qs.filter(timestamp__gte=since)

        return qs


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  5. PlatformIntegration — Cybernetic Command Center
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PlatformIntegrationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET   /api/v1/governance/integrations/            — list all integrations
    GET   /api/v1/governance/integrations/{slug}/     — detail
    PATCH /api/v1/governance/integrations/{slug}/     — update is_enabled / config
    POST  /api/v1/governance/integrations/{slug}/toggle/ — flip state

    Platform Admin only.  Integration slugs are seeded via migration.
    """

    permission_classes = [permissions.IsAuthenticated, CanManageFeatureToggles]
    lookup_field = "slug"

    def get_queryset(self):
        qs = PlatformIntegration.objects.all()
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return PlatformIntegrationListSerializer
        return PlatformIntegrationSerializer

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, slug=None):
        """
        POST /api/v1/governance/integrations/{slug}/toggle/
        Flips the current state (enabled ↔ disabled).
        """
        instance = self.get_object()
        instance.is_enabled = not instance.is_enabled
        instance.toggled_by = request.user
        instance.toggled_at = timezone.now()
        instance.save(update_fields=[
            "is_enabled", "toggled_by", "toggled_at", "updated_at",
        ])
        return Response(PlatformIntegrationSerializer(instance).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  6. NotificationPreference — Per-User Notification Matrix
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MyNotificationPreferencesView(APIView):
    """
    GET  /api/v1/governance/notifications/me/
         — list current user's notification matrix (auto-seeds defaults)
    PUT  /api/v1/governance/notifications/me/
         — bulk-update the entire matrix

    All authenticated users.  Each user manages their own matrix.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        prefs = NotificationPreference.get_or_create_defaults(request.user)
        serializer = NotificationPreferenceSerializer(prefs, many=True)
        return Response(serializer.data)

    def put(self, request):
        bulk_serializer = NotificationPreferenceBulkUpdateSerializer(
            data=request.data,
        )
        bulk_serializer.is_valid(raise_exception=True)

        items = bulk_serializer.validated_data["preferences"]

        # Ensure defaults exist first
        NotificationPreference.get_or_create_defaults(request.user)

        updated = []
        for item in items:
            slug = item["event_slug"]
            update_fields = {}
            for channel in ("in_app", "sms", "email"):
                if channel in item:
                    update_fields[channel] = item[channel]

            if update_fields:
                NotificationPreference.objects.filter(
                    user=request.user, event_slug=slug,
                ).update(**update_fields)
                updated.append(slug)

        # Return the full updated matrix
        prefs = NotificationPreference.objects.filter(user=request.user)
        serializer = NotificationPreferenceSerializer(prefs, many=True)
        return Response({
            "updated_count": len(updated),
            "preferences": serializer.data,
        })


class LifecycleEventsView(APIView):
    """
    GET /api/v1/governance/notifications/events/
        — list all lifecycle event definitions (for building the UI grid)

    Public for all authenticated users.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        events = NotificationPreference.get_event_choices_list()
        serializer = LifecycleEventSerializer(events, many=True)
        return Response(serializer.data)
