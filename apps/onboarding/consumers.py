"""
Onboarding WebSocket Consumers
================================

Real-time WebSocket channels for:
  1. Agency approval queue — Agency Owners receive live join requests
  2. Service Pro notifications — approval/rejection results
"""

import json
import logging

from channels.generic.websocket import AsyncJsonWebSocketConsumer

logger = logging.getLogger(__name__)


class AgencyApprovalConsumer(AsyncJsonWebSocketConsumer):
    """
    WebSocket: ws/onboarding/approvals/<agency_id>/

    Agency Owners connect to receive real-time approval requests
    from Service Pros who fuzzy-matched their agency name.

    Inbound messages: none expected (read-only stream)
    Outbound messages:
      {
        "type": "approval.request",
        "data": {
          "uuid": "...",
          "service_pro_name": "...",
          "service_pro_email": "...",
          "typed_agency_name": "...",
          "match_score": 0.89,
          "created_at": "...",
          "expires_at": "..."
        }
      }
    """

    async def connect(self):
        self.agency_id = self.scope["url_route"]["kwargs"]["agency_id"]
        self.group_name = f"agency_{self.agency_id}_approvals"

        # Verify the user is an Agency Owner for this company
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        if user.role != 30 or user.company_id != int(self.agency_id):
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"Agency approval WS connected: agency={self.agency_id}")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

    async def approval_request(self, event):
        """Handle approval.request group message — forward to WebSocket."""
        await self.send_json({
            "type": "approval_request",
            "data": event["data"],
        })


class ServiceProNotificationConsumer(AsyncJsonWebSocketConsumer):
    """
    WebSocket: ws/onboarding/notifications/

    Service Pros connect to receive real-time approval/rejection
    notifications for their agency join requests.
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"user_{user.id}_notifications"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

    async def approval_result(self, event):
        """Handle approval.result group message — forward to WebSocket."""
        await self.send_json({
            "type": "approval_result",
            "data": event["data"],
        })
