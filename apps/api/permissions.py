"""
Role-Based Access Control (RBAC) Permission Classes
====================================================

Strict, composable DRF permissions that map directly to the six
platform roles defined in ``apps.users.models.User``.

Design Principles:
  1. Every permission class is *deny-by-default*.
  2. ``has_permission`` gates list/create; ``has_object_permission``
     gates retrieve/update/destroy.
  3. Role checks use the integer constants from User, never raw ints.
  4. Compound permissions use ``|`` (OR) or ``&`` (AND) operators built
     into DRF's BasePermission so viewsets can compose freely:

         permission_classes = [IsAuthenticated & (IsResident | IsPlatformAdmin)]
"""

from rest_framework.permissions import BasePermission

from apps.users.models import User


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Single-Role Permissions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class IsResident(BasePermission):
    """Grant access to users with the Resident role (end-customer)."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_RESIDENT
        )


class IsServicePro(BasePermission):
    """Grant access to Service Pros (field cleaners/technicians)."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_SERVICE_PRO
        )


class IsAgencyOwner(BasePermission):
    """Grant access to Agency Owners (cleaning company managers)."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_AGENCY_OWNER
        )


class IsQAInspector(BasePermission):
    """Grant access to QA Inspectors."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_QA_INSPECTOR
        )


class IsSupportArchitect(BasePermission):
    """Grant access to Support Architects (customer support/success)."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_SUPPORT_ARCHITECT
        )


class IsPlatformAdmin(BasePermission):
    """Grant access to Platform Admins (superusers)."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
            and request.user.role == User.ROLE_PLATFORM_ADMIN
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Compound / Convenience Permissions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class IsStaff(BasePermission):
    """
    Any internal staff member: Agency Owner, QA Inspector,
    Support Architect, or Platform Admin.
    """
    STAFF_ROLES = frozenset({
        User.ROLE_AGENCY_OWNER,
        User.ROLE_QA_INSPECTOR,
        User.ROLE_SUPPORT_ARCHITECT,
        User.ROLE_PLATFORM_ADMIN,
    })

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self.STAFF_ROLES
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: the requesting user must either be the
    object's owner (``obj.user`` or ``obj.client``) or a Platform Admin.

    Views should call ``self.check_object_permissions(request, obj)``
    to trigger ``has_object_permission``.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Try common owner FK names
        owner = getattr(obj, "user", None) or getattr(obj, "client", None)
        if owner and owner.pk == request.user.pk:
            return True
        return (
            request.user.is_superuser
            and request.user.role == User.ROLE_PLATFORM_ADMIN
        )


class IsCompanyMember(BasePermission):
    """
    Object-level: the requesting user belongs to the same company as
    the object.  Works on any model that has a ``company`` FK.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.company_id is not None
        )

    def has_object_permission(self, request, view, obj):
        obj_company = getattr(obj, "company_id", None)
        return obj_company is not None and obj_company == request.user.company_id


class ReadOnly(BasePermission):
    """Allow only safe HTTP methods (GET, HEAD, OPTIONS)."""
    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def has_permission(self, request, view):
        return request.method in self.SAFE_METHODS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Role Hierarchy Helper
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def has_any_role(user, *roles) -> bool:
    """
    Utility for ad-hoc role checks outside of DRF views.

        if has_any_role(request.user, User.ROLE_PLATFORM_ADMIN, User.ROLE_QA_INSPECTOR):
            ...
    """
    return user.is_authenticated and user.role in roles
