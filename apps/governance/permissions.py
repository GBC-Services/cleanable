"""
Governance Permission Classes
==============================

Phase 2 RBAC extensions for privacy controls and break-glass escalation.

Key classes:
  - ``CanManageFeatureToggles``  — Platform Admin only
  - ``CanReadAuditLogs``         — Platform Admin only
  - ``CanManageOwnPrivacy``      — Users managing their own prefs
  - ``HasBreakGlassAccess``      — Support Architects with active BG
  - ``BreakGlassOverride``       — Temporary override permission
  - ``IsFeatureEnabled``         — Factory for global feature gates

Usage in viewsets::

    # Only Platform Admin can flip kill-switches
    class FeatureToggleViewSet(viewsets.ModelViewSet):
        permission_classes = [IsAuthenticated, CanManageFeatureToggles]

    # Support Architect with active break-glass can override privacy
    class PrivacyOverrideView(APIView):
        permission_classes = [IsAuthenticated, HasBreakGlassAccess]
"""

from django.utils import timezone
from rest_framework.permissions import BasePermission

from apps.users.models import User


class CanManageFeatureToggles(BasePermission):
    """
    Only Platform Admins (superuser + role=20) can create, update,
    or toggle system feature switches.
    """
    message = "Only Platform Admins can manage system feature toggles."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
            and request.user.role == User.ROLE_PLATFORM_ADMIN
        )


class CanReadAuditLogs(BasePermission):
    """
    Only Platform Admins can read the governance audit trail.
    No role — not even Support Architect — can access audit data.
    """
    message = "Only Platform Admins can access governance audit logs."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
            and request.user.role == User.ROLE_PLATFORM_ADMIN
        )


class CanManageOwnPrivacy(BasePermission):
    """
    Users can read and update their own privacy preferences.
    The serializer enforces which fields are writable per role.
    """
    message = "You can only manage your own privacy preferences."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # obj is a PrivacyPreferences instance
        return obj.user_id == request.user.id


class HasBreakGlassAccess(BasePermission):
    """
    Support Architects (role=50) who can initiate break-glass sessions.
    The global ``break_glass_enabled`` toggle must be active.
    """
    message = (
        "Break-glass access requires Support Architect role "
        "and the break-glass system must be globally enabled."
    )

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role != User.ROLE_SUPPORT_ARCHITECT:
            return False

        # Check global kill-switch
        from apps.governance.models import SystemFeatureToggle
        return SystemFeatureToggle.is_feature_active("break_glass_enabled")


class BreakGlassOverride(BasePermission):
    """
    Grants temporary permission to override a target user's privacy
    preferences during an active break-glass session.

    This is the most sensitive permission in the system.  It checks:
      1. Caller is a Support Architect
      2. Break-glass is globally enabled
      3. An active (non-expired) BreakGlassSession exists where
         ``initiated_by == request.user`` and
         ``target_user == the object's user``

    Attach to object-level permission checks on PrivacyPreferences.
    """
    message = "No active break-glass session found for this target user."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.role in (
            User.ROLE_SUPPORT_ARCHITECT,
            User.ROLE_PLATFORM_ADMIN,
        )

    def has_object_permission(self, request, view, obj):
        """
        obj: PrivacyPreferences instance.
        Check for an active BG session linking request.user → obj.user.
        """
        # Platform Admins can always override (superuser governance)
        if (
            request.user.is_superuser
            and request.user.role == User.ROLE_PLATFORM_ADMIN
        ):
            return True

        from apps.governance.models import BreakGlassSession

        return BreakGlassSession.objects.filter(
            initiated_by=request.user,
            target_user=obj.user,
            status=BreakGlassSession.STATUS_ACTIVE,
            expires_at__gt=timezone.now(),
        ).exists()


class CanRevokeBreakGlass(BasePermission):
    """
    Only Platform Admins or the initiating Support Architect can
    revoke (early-terminate) a break-glass session.
    """
    message = "Only Platform Admins or the session initiator can revoke."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # obj is a BreakGlassSession
        if (
            request.user.is_superuser
            and request.user.role == User.ROLE_PLATFORM_ADMIN
        ):
            return True
        return obj.initiated_by_id == request.user.id


def is_feature_enabled(feature_slug: str) -> type:
    """
    Factory that returns a permission class gating access behind
    a specific SystemFeatureToggle.

    Usage::

        class GPSTrackingView(APIView):
            permission_classes = [
                IsAuthenticated,
                is_feature_enabled("global_gps_enabled"),
            ]
    """

    class _FeatureGate(BasePermission):
        message = f"The '{feature_slug}' feature is currently disabled."

        def has_permission(self, request, view):
            from apps.governance.models import SystemFeatureToggle
            return SystemFeatureToggle.is_feature_active(feature_slug)

    _FeatureGate.__name__ = f"IsFeatureEnabled_{feature_slug}"
    _FeatureGate.__qualname__ = f"IsFeatureEnabled_{feature_slug}"
    return _FeatureGate
