"""Onboarding WebSocket URL routing."""

from django.urls import re_path
from apps.onboarding import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/onboarding/approvals/(?P<agency_id>\d+)/$",
        consumers.AgencyApprovalConsumer.as_asgi(),
    ),
    re_path(
        r"ws/onboarding/notifications/$",
        consumers.ServiceProNotificationConsumer.as_asgi(),
    ),
]
