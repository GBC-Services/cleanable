"""
Governance URL Configuration
=============================

Mounted at ``/api/v1/governance/`` via the project root urlconf.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"features", views.FeatureToggleViewSet, basename="feature-toggles")
router.register(r"break-glass", views.BreakGlassViewSet, basename="break-glass")
router.register(r"audit-logs", views.AuditLogViewSet, basename="audit-logs")
router.register(r"privacy/admin", views.PrivacyAdminViewSet, basename="privacy-admin")
router.register(r"integrations", views.PlatformIntegrationViewSet, basename="integrations")
router.register(r"vault", views.SecretVaultViewSet, basename="vault")

urlpatterns = [
    # Self-service privacy
    path("privacy/me/", views.MyPrivacyView.as_view(), name="privacy-me"),

    # Notification matrix — per-user
    path(
        "notifications/me/",
        views.MyNotificationPreferencesView.as_view(),
        name="notification-prefs-me",
    ),
    # Lifecycle event definitions (for building the notification grid)
    path(
        "notifications/events/",
        views.LifecycleEventsView.as_view(),
        name="lifecycle-events",
    ),

    # Role Permission Matrix
    path(
        "permissions/matrix/",
        views.RolePermissionMatrixView.as_view(),
        name="permissions-matrix",
    ),

    # User Security Management
    path(
        "user-security/",
        views.UserSecurityView.as_view(),
        name="user-security-list",
    ),
    path(
        "user-security/action/",
        views.UserSecurityActionView.as_view(),
        name="user-security-action",
    ),
    path(
        "user-security/history/",
        views.UserSecurityHistoryView.as_view(),
        name="user-security-history",
    ),

    # Command Palette Search
    path(
        "command-palette/search/",
        views.CommandPaletteSearchView.as_view(),
        name="command-palette-search",
    ),

    # Router-registered endpoints
    path("", include(router.urls)),
]
