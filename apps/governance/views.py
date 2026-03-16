"""
Governance API Views
====================

Endpoints for:
  - Platform Admin: manage feature toggles, read audit logs
  - All users: read/update own privacy preferences
  - Support Architects: request and manage break-glass sessions
  - Break-glass overrides: apply/revert privacy overrides
  - Vault: secret key management (Platform Admin only)
  - Permissions Matrix: role × permission grid (Platform Admin only)
  - User Security: force-reset, MFA management (Platform Admin only)
  - Command Palette: search endpoint for admin global search
"""

import secrets
import string

from django.db.models import Q
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
    RolePermissionMatrix,
    SecretVault,
    SystemFeatureToggle,
    UserSecurityAction,
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
    AdminUserListSerializer,
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
    RolePermissionMatrixBulkUpdateSerializer,
    RolePermissionMatrixSerializer,
    SecretVaultCreateSerializer,
    SecretVaultRevokeSerializer,
    SecretVaultRotateSerializer,
    SecretVaultSerializer,
    SystemFeatureToggleListSerializer,
    SystemFeatureToggleSerializer,
    UserSecurityActionCreateSerializer,
    UserSecurityActionSerializer,
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  7. SecretVault — API Key & Secret Management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SecretVaultViewSet(viewsets.ModelViewSet):
    """
    CRUD + rotate + revoke for secret vault entries.

    GET    /api/v1/governance/vault/              — list all secrets
    POST   /api/v1/governance/vault/              — create new secret
    GET    /api/v1/governance/vault/{id}/          — detail
    PATCH  /api/v1/governance/vault/{id}/          — update metadata
    DELETE /api/v1/governance/vault/{id}/          — hard delete
    POST   /api/v1/governance/vault/{id}/rotate/   — rotate to new value
    POST   /api/v1/governance/vault/{id}/revoke/   — immediately revoke

    Platform Admin only.
    """

    permission_classes = [permissions.IsAuthenticated, CanManageFeatureToggles]

    def get_queryset(self):
        qs = SecretVault.objects.select_related("created_by", "revoked_by")
        provider = self.request.query_params.get("provider")
        if provider:
            qs = qs.filter(provider=provider)
        env = self.request.query_params.get("environment")
        if env:
            qs = qs.filter(environment=env)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return SecretVaultCreateSerializer
        return SecretVaultSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        GovernanceAuditLog.log(
            action=GovernanceAuditLog.ACTION_VAULT_SECRET_CREATED,
            description=f"Created vault secret '{instance.label}' for {instance.provider} ({instance.environment})",
            actor=self.request.user,
            severity=GovernanceAuditLog.SEVERITY_WARNING,
            changes={
                "provider": instance.provider,
                "scope": instance.scope,
                "environment": instance.environment,
            },
        )

    @action(detail=True, methods=["post"])
    def rotate(self, request, pk=None):
        """Rotate a secret to a new value."""
        instance = self.get_object()

        if instance.status == SecretVault.STATUS_REVOKED:
            return Response(
                {"detail": "Cannot rotate a revoked secret."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SecretVaultRotateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_hint = instance.key_hint
        instance.rotate(serializer.validated_data["new_value"], user=request.user)

        GovernanceAuditLog.log(
            action=GovernanceAuditLog.ACTION_VAULT_SECRET_ROTATED,
            description=f"Rotated vault secret '{instance.label}' (rotation #{instance.rotation_count})",
            actor=request.user,
            severity=GovernanceAuditLog.SEVERITY_WARNING,
            changes={
                "old_hint": old_hint,
                "new_hint": instance.key_hint,
                "rotation_count": instance.rotation_count,
            },
        )

        return Response(SecretVaultSerializer(instance).data)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """Immediately revoke a secret."""
        instance = self.get_object()

        if instance.status == SecretVault.STATUS_REVOKED:
            return Response(
                {"detail": "Secret is already revoked."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SecretVaultRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance.revoke(
            user=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )

        GovernanceAuditLog.log(
            action=GovernanceAuditLog.ACTION_VAULT_SECRET_REVOKED,
            description=f"Revoked vault secret '{instance.label}' — {serializer.validated_data.get('reason', 'No reason provided')}",
            actor=request.user,
            severity=GovernanceAuditLog.SEVERITY_CRITICAL,
            changes={
                "provider": instance.provider,
                "environment": instance.environment,
                "reason": serializer.validated_data.get("reason", ""),
            },
        )

        return Response(SecretVaultSerializer(instance).data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  8. RolePermissionMatrix — Global Permission Grid
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RolePermissionMatrixView(APIView):
    """
    GET  /api/v1/governance/permissions/matrix/
         — full role × permission grid

    PUT  /api/v1/governance/permissions/matrix/
         — bulk update entries

    Platform Admin only.
    """

    permission_classes = [permissions.IsAuthenticated, CanManageFeatureToggles]

    def get(self, request):
        entries = RolePermissionMatrix.objects.all()
        serializer = RolePermissionMatrixSerializer(entries, many=True)

        # Also return metadata for building the grid UI
        roles = [{"value": r, "label": l} for r, l in User.ROLES]
        perms = [
            {"value": p, "label": l}
            for p, l in RolePermissionMatrix.PERMISSION_CHOICES
        ]

        return Response({
            "entries": serializer.data,
            "roles": roles,
            "permissions": perms,
            "matrix": RolePermissionMatrix.get_matrix(),
        })

    def put(self, request):
        serializer = RolePermissionMatrixBulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entries = serializer.validated_data["entries"]
        updated = []

        for item in entries:
            obj, created = RolePermissionMatrix.objects.update_or_create(
                role=item["role"],
                permission=item["permission"],
                defaults={
                    "is_granted": item.get("is_granted", True),
                    "updated_by": request.user,
                },
            )
            updated.append(obj)

            GovernanceAuditLog.log(
                action=GovernanceAuditLog.ACTION_PERMISSION_UPDATED,
                description=(
                    f"{'Granted' if obj.is_granted else 'Revoked'} "
                    f"'{obj.permission}' for role {obj.role}"
                ),
                actor=request.user,
                severity=GovernanceAuditLog.SEVERITY_WARNING,
                changes={
                    "role": obj.role,
                    "permission": obj.permission,
                    "is_granted": obj.is_granted,
                },
            )

        # Return updated matrix
        all_entries = RolePermissionMatrix.objects.all()
        return Response({
            "updated_count": len(updated),
            "entries": RolePermissionMatrixSerializer(all_entries, many=True).data,
            "matrix": RolePermissionMatrix.get_matrix(),
        })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  9. User Security — Force-Reset, MFA Management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class UserSecurityView(APIView):
    """
    GET  /api/v1/governance/user-security/
         — list all users with security status

    POST /api/v1/governance/user-security/action/
         — perform a security action (password reset, MFA manage, etc.)

    GET  /api/v1/governance/user-security/history/
         — list all security actions

    Platform Admin only.
    """

    permission_classes = [permissions.IsAuthenticated, CanManageFeatureToggles]

    def get(self, request):
        """List all users with security metadata."""
        qs = User.objects.all().order_by("-date_joined")

        # Filtering
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role=int(role))

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        serializer = AdminUserListSerializer(qs[:100], many=True)
        return Response(serializer.data)


class UserSecurityActionView(APIView):
    """
    POST /api/v1/governance/user-security/action/
         — perform a security action

    Platform Admin only.
    """

    permission_classes = [permissions.IsAuthenticated, CanManageFeatureToggles]

    def post(self, request):
        serializer = UserSecurityActionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user = User.objects.get(pk=serializer.validated_data["target_user_id"])
        action_type = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")

        metadata = {}

        if action_type == UserSecurityAction.ACTION_PASSWORD_FORCE_RESET:
            # Generate a temporary password
            temp_password = "".join(
                secrets.choice(string.ascii_letters + string.digits + "!@#$%")
                for _ in range(16)
            )
            target_user.set_password(temp_password)
            target_user.save(update_fields=["password"])
            metadata = {
                "temp_password": temp_password,
                "sent_to": target_user.email,
            }

        elif action_type == UserSecurityAction.ACTION_MFA_ENROLL:
            metadata = {"method": "totp", "status": "enrolled"}

        elif action_type == UserSecurityAction.ACTION_MFA_REVOKE:
            metadata = {"method": "totp", "status": "revoked"}

        elif action_type == UserSecurityAction.ACTION_ACCOUNT_LOCK:
            target_user.is_active = False
            target_user.save(update_fields=["is_active"])
            metadata = {"locked": True}

        elif action_type == UserSecurityAction.ACTION_ACCOUNT_UNLOCK:
            target_user.is_active = True
            target_user.save(update_fields=["is_active"])
            metadata = {"locked": False}

        # Log the action
        action_record = UserSecurityAction.objects.create(
            admin=request.user,
            target_user=target_user,
            action=action_type,
            status=UserSecurityAction.STATUS_COMPLETED,
            reason=reason,
            metadata=metadata,
        )

        # Also log to governance audit
        GovernanceAuditLog.log(
            action=(
                GovernanceAuditLog.ACTION_PASSWORD_FORCE_RESET
                if action_type == UserSecurityAction.ACTION_PASSWORD_FORCE_RESET
                else GovernanceAuditLog.ACTION_MFA_MANAGED
            ),
            description=f"{action_type} on {target_user.email} by {request.user.email}",
            actor=request.user,
            target_user=target_user,
            severity=GovernanceAuditLog.SEVERITY_CRITICAL,
            changes=metadata,
        )

        return Response(
            UserSecurityActionSerializer(action_record).data,
            status=status.HTTP_201_CREATED,
        )


class UserSecurityHistoryView(APIView):
    """
    GET /api/v1/governance/user-security/history/
        — list security action history

    Platform Admin only.
    """

    permission_classes = [permissions.IsAuthenticated, CanManageFeatureToggles]

    def get(self, request):
        qs = UserSecurityAction.objects.select_related(
            "admin", "target_user",
        ).all()

        target_user_id = request.query_params.get("target_user")
        if target_user_id:
            qs = qs.filter(target_user_id=target_user_id)

        action_filter = request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)

        serializer = UserSecurityActionSerializer(qs[:100], many=True)
        return Response(serializer.data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  10. Command Palette — Admin Global Search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CommandPaletteSearchView(APIView):
    """
    GET /api/v1/governance/command-palette/search/?q=...
        — search users, secrets, settings

    Platform Admin only.  Returns categorized results for the
    Cmd+K command palette.
    """

    permission_classes = [permissions.IsAuthenticated, CanManageFeatureToggles]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query or len(query) < 2:
            return Response({"results": []})

        results = []

        # Search users
        users = User.objects.filter(
            Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )[:5]
        for u in users:
            role_label = dict(User.ROLES).get(u.role, "Unknown")
            results.append({
                "type": "user",
                "id": u.id,
                "title": u.get_full_name() or u.email,
                "subtitle": f"{role_label} — {u.email}",
                "url": f"/platform-admin/user-security?user={u.id}",
            })

        # Search vault secrets
        secrets_qs = SecretVault.objects.filter(
            Q(label__icontains=query)
            | Q(provider__icontains=query)
        )[:5]
        for s in secrets_qs:
            results.append({
                "type": "vault",
                "id": str(s.id),
                "title": s.label,
                "subtitle": f"{s.get_provider_display()} — {s.get_environment_display()} — {s.get_status_display()}",
                "url": "/platform-admin/vault",
            })

        # Search feature toggles
        toggles = SystemFeatureToggle.objects.filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
        )[:5]
        for t in toggles:
            state = "Enabled" if t.is_enabled else "Disabled"
            results.append({
                "type": "feature",
                "id": str(t.id),
                "title": t.name,
                "subtitle": f"Feature Toggle — {state}",
                "url": "/platform-admin/governance",
            })

        # Search integrations
        integrations = PlatformIntegration.objects.filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
        )[:5]
        for i in integrations:
            state = "Enabled" if i.is_enabled else "Disabled"
            results.append({
                "type": "integration",
                "id": str(i.id),
                "title": i.name,
                "subtitle": f"Integration — {state}",
                "url": "/platform-admin/command-center",
            })

        # Admin navigation commands
        nav_commands = [
            {"title": "Vault", "subtitle": "Manage API keys and secrets", "url": "/platform-admin/vault"},
            {"title": "Permissions Matrix", "subtitle": "Role permission grid", "url": "/platform-admin/permissions"},
            {"title": "User Security", "subtitle": "Password resets, MFA, account locks", "url": "/platform-admin/user-security"},
            {"title": "Governance", "subtitle": "Feature toggles, privacy, break-glass", "url": "/platform-admin/governance"},
            {"title": "Command Center", "subtitle": "Integration toggles, notifications", "url": "/platform-admin/command-center"},
            {"title": "Dashboard", "subtitle": "Platform admin overview", "url": "/platform-admin"},
        ]
        for cmd in nav_commands:
            if query.lower() in cmd["title"].lower() or query.lower() in cmd["subtitle"].lower():
                results.append({
                    "type": "navigation",
                    "id": cmd["url"],
                    "title": cmd["title"],
                    "subtitle": cmd["subtitle"],
                    "url": cmd["url"],
                })

        return Response({"results": results[:20]})
