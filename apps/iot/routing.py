"""
WebSocket URL Routing
======================

Maps WebSocket paths to Django Channels consumers.

Paths:
  /ws/gps-tracking/{booking_uuid}/  → GPSTrackingConsumer
  /ws/alerts/                       → AlertConsumer
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/gps-tracking/(?P<booking_uuid>[^/]+)/$",
        consumers.GPSTrackingConsumer.as_asgi(),
    ),
    re_path(
        r"ws/alerts/$",
        consumers.AlertConsumer.as_asgi(),
    ),
]
