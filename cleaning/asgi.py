"""
ASGI config for cleaning project.
=================================

Handles both HTTP and WebSocket connections:

  HTTP  → Standard Django ASGI application
  WS    → Django Channels routing for:
           • /ws/gps-tracking/{booking_uuid}/  — Live GPS tracking for En Route
           • /ws/alerts/                        — Support Architect alert channel

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cleaning.settings")

# Initialize Django ASGI application early to ensure apps are loaded
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.iot.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)
