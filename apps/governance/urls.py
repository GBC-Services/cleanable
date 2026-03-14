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

urlpatterns = [
    # Self-service privacy
    path("privacy/me/", views.MyPrivacyView.as_view(), name="privacy-me"),

    # Router-registered endpoints
    path("", include(router.urls)),
]
