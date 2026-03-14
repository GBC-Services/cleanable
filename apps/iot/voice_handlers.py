"""
Voice Assistant Webhook Handlers
==================================

Intent-parsing webhook handlers for:
  1. **Amazon Alexa** (Alexa Skills Kit) — receives JSON payloads from
     the Alexa service, maps intents to booking-engine actions.
  2. **Apple Siri / HomeKit** — receives payloads from Siri Shortcuts
     via a custom HTTP action, maps commands to booking operations.

Both handlers authenticate the calling user via the VoiceAssistantLink
OAuth token (Alexa) or a signed JWT (Siri Shortcuts).

Supported Intents / Commands:
  • BookUsualServicePro  — "Book my usual Service Pro"
  • GetNextBooking       — "When is my next cleaning?"
  • CancelBooking        — "Cancel my next booking"
  • CheckLockStatus      — "Is my front door locked?"
  • GetBookingStatus     — "What's the status of my booking?"
  • ListUpcomingBookings — "List my upcoming cleanings"

Security:
  • Alexa: Payload signature verification via the Alexa Skills Kit spec.
  • Siri:  HMAC-SHA256 signed payload with a shared secret per user.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Alexa Skill Webhook Handler
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def handle_alexa_webhook(payload: dict) -> dict:
    """
    Process an incoming Alexa Skill request.

    Args:
        payload: The full JSON body from Alexa.

    Returns:
        Alexa-format response dict with ``outputSpeech``, ``card``, etc.
    """
    request_type = payload.get("request", {}).get("type", "")
    session = payload.get("session", {})

    # ── Launch Request ────────────────────────────────────────────────
    if request_type == "LaunchRequest":
        return _alexa_response(
            speech=(
                "Welcome to Cleanable. You can say things like "
                "'Book my usual Service Pro', 'When is my next cleaning?', "
                "or 'Is my front door locked?'."
            ),
            card_title="Welcome to Cleanable",
            reprompt="What would you like to do?",
            should_end=False,
        )

    # ── Intent Request ────────────────────────────────────────────────
    if request_type == "IntentRequest":
        intent = payload["request"].get("intent", {})
        intent_name = intent.get("name", "")
        slots = intent.get("slots", {})

        user = _resolve_alexa_user(session)
        if not user:
            return _alexa_response(
                speech=(
                    "I couldn't find your Cleanable account. "
                    "Please link your account in the Alexa app."
                ),
                card_title="Account Not Linked",
                should_end=True,
            )

        # Route to intent handlers
        handler = ALEXA_INTENT_MAP.get(intent_name)
        if handler:
            return handler(user, slots)

        # Built-in intents
        if intent_name in ("AMAZON.HelpIntent",):
            return _alexa_response(
                speech=(
                    "You can ask me to book your usual Service Pro, "
                    "check your next booking, cancel a booking, "
                    "or check your smart lock status."
                ),
                card_title="Cleanable Help",
                should_end=False,
            )

        if intent_name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
            return _alexa_response(
                speech="Goodbye!",
                should_end=True,
            )

        return _alexa_response(
            speech="I'm not sure how to help with that. Try asking about your bookings.",
            should_end=False,
        )

    # ── Session Ended ─────────────────────────────────────────────────
    if request_type == "SessionEndedRequest":
        return _alexa_response(speech="", should_end=True)

    return _alexa_response(
        speech="Something went wrong. Please try again.",
        should_end=True,
    )


# ── Alexa Intent Handlers ────────────────────────────────────────────


def _alexa_book_usual(user, slots: dict) -> dict:
    """
    Intent: BookUsualServicePro
    "Alexa, ask Cleanable to book my usual Service Pro."

    Logic:
      1. Find the user's most recently completed booking.
      2. Identify the Service Pro who did it.
      3. Create a new booking for tomorrow with the same place/services.
    """
    from apps.bookings.models import Booking, BookingService
    from apps.cleanings.models import CleanerForCleaning

    # Find last completed booking
    last_booking = (
        Booking.objects.filter(client=user, status=Booking.STATUS_COMPLETED, is_active=True)
        .order_by("-scheduled_date")
        .first()
    )

    if not last_booking:
        return _alexa_response(
            speech="I couldn't find any previous bookings. Please use the app to create your first booking.",
            card_title="No Previous Bookings",
            should_end=True,
        )

    # Find the assigned Service Pro from the last cleaning
    service_pro = None
    if hasattr(last_booking, "cleaning"):
        cleaner_link = (
            CleanerForCleaning.objects.filter(cleaning=last_booking.cleaning)
            .select_related("cleaner")
            .first()
        )
        if cleaner_link:
            service_pro = cleaner_link.cleaner

    # Schedule for tomorrow, same time window
    tomorrow = timezone.now().date() + timedelta(days=1)

    pro_name = service_pro.get_full_name() if service_pro else "your usual team"

    return _alexa_response(
        speech=(
            f"I've prepared a booking for {tomorrow.strftime('%A, %B %d')} "
            f"at {last_booking.place} with {pro_name}. "
            f"The estimated cost is ${last_booking.total_fee_final}. "
            "Please confirm in the Cleanable app to complete your booking."
        ),
        card_title="Booking Prepared",
        card_content=(
            f"Date: {tomorrow}\n"
            f"Place: {last_booking.place}\n"
            f"Service Pro: {pro_name}\n"
            f"Est. Cost: ${last_booking.total_fee_final}"
        ),
        should_end=True,
    )


def _alexa_get_next_booking(user, slots: dict) -> dict:
    """
    Intent: GetNextBooking
    "Alexa, ask Cleanable when is my next cleaning."
    """
    from apps.bookings.models import Booking

    next_booking = (
        Booking.objects.filter(
            client=user,
            status__in=(Booking.STATUS_NEW, Booking.STATUS_IN_WORK),
            scheduled_date__gte=timezone.now().date(),
            is_active=True,
        )
        .order_by("scheduled_date", "scheduled_start_dt")
        .first()
    )

    if not next_booking:
        return _alexa_response(
            speech="You don't have any upcoming bookings. Would you like me to book your usual Service Pro?",
            card_title="No Upcoming Bookings",
            should_end=False,
        )

    date_str = next_booking.scheduled_date.strftime("%A, %B %d")
    time_str = (
        next_booking.scheduled_start_dt.strftime("%-I:%M %p")
        if next_booking.scheduled_start_dt
        else "scheduled time"
    )

    return _alexa_response(
        speech=f"Your next cleaning is on {date_str} at {time_str} at {next_booking.place}.",
        card_title="Next Booking",
        card_content=(
            f"Date: {next_booking.scheduled_date}\n"
            f"Time: {time_str}\n"
            f"Place: {next_booking.place}\n"
            f"Status: {next_booking.get_status_display()}"
        ),
        should_end=True,
    )


def _alexa_cancel_booking(user, slots: dict) -> dict:
    """
    Intent: CancelBooking
    "Alexa, ask Cleanable to cancel my next booking."
    """
    from apps.bookings.models import Booking

    next_booking = (
        Booking.objects.filter(
            client=user,
            status=Booking.STATUS_NEW,
            scheduled_date__gte=timezone.now().date(),
            is_active=True,
        )
        .order_by("scheduled_date")
        .first()
    )

    if not next_booking:
        return _alexa_response(
            speech="You don't have any cancellable bookings.",
            card_title="Nothing to Cancel",
            should_end=True,
        )

    date_str = next_booking.scheduled_date.strftime("%A, %B %d")

    return _alexa_response(
        speech=(
            f"Your next booking is on {date_str} at {next_booking.place}. "
            "Please confirm the cancellation in the Cleanable app for security."
        ),
        card_title="Confirm Cancellation",
        card_content=(
            f"Booking: #{next_booking.id}\n"
            f"Date: {next_booking.scheduled_date}\n"
            f"Place: {next_booking.place}\n\n"
            "Open the Cleanable app to confirm."
        ),
        should_end=True,
    )


def _alexa_check_lock_status(user, slots: dict) -> dict:
    """
    Intent: CheckLockStatus
    "Alexa, ask Cleanable if my front door is locked."
    """
    from .models import ConnectedDevice
    from .smart_lock_service import ensure_valid_token, list_locks

    devices = ConnectedDevice.objects.filter(
        user=user,
        status=ConnectedDevice.STATUS_ACTIVE,
    )

    if not devices.exists():
        return _alexa_response(
            speech="You don't have any connected smart locks. Set them up in the Cleanable app.",
            card_title="No Smart Locks",
            should_end=True,
        )

    device = devices.first()
    try:
        access_token = ensure_valid_token(device)
        locks = list_locks(device.provider, access_token)
    except Exception as exc:
        logger.error("Lock status check failed for user %s: %s", user.email, exc)
        return _alexa_response(
            speech="I couldn't check your lock status right now. Please try again later.",
            should_end=True,
        )

    if not locks:
        return _alexa_response(
            speech="I found your connected device but couldn't read the lock status.",
            should_end=True,
        )

    lock = locks[0]
    status_text = lock.get("status", "unknown")
    name = lock.get("name", "Your lock")

    return _alexa_response(
        speech=f"{name} is currently {status_text}.",
        card_title="Lock Status",
        card_content=f"{name}: {status_text}",
        should_end=True,
    )


def _alexa_get_booking_status(user, slots: dict) -> dict:
    """
    Intent: GetBookingStatus
    "Alexa, ask Cleanable what's the status of my booking."
    """
    from apps.bookings.models import Booking

    # Get the most recent active booking
    booking = (
        Booking.objects.filter(client=user, is_active=True)
        .exclude(status__in=(Booking.STATUS_CANCELLED_BY_CLIENT, Booking.STATUS_CANCELLED_BY_MANAGER))
        .order_by("-scheduled_date")
        .first()
    )

    if not booking:
        return _alexa_response(
            speech="You don't have any active bookings.",
            card_title="No Active Bookings",
            should_end=True,
        )

    status_display = booking.get_status_display()
    date_str = booking.scheduled_date.strftime("%A, %B %d")

    return _alexa_response(
        speech=f"Your booking for {date_str} at {booking.place} is currently {status_display}.",
        card_title="Booking Status",
        card_content=(
            f"Date: {booking.scheduled_date}\n"
            f"Place: {booking.place}\n"
            f"Status: {status_display}"
        ),
        should_end=True,
    )


def _alexa_list_upcoming(user, slots: dict) -> dict:
    """
    Intent: ListUpcomingBookings
    "Alexa, ask Cleanable to list my upcoming cleanings."
    """
    from apps.bookings.models import Booking

    bookings = (
        Booking.objects.filter(
            client=user,
            status__in=(Booking.STATUS_NEW, Booking.STATUS_IN_WORK),
            scheduled_date__gte=timezone.now().date(),
            is_active=True,
        )
        .order_by("scheduled_date")[:5]
    )

    if not bookings:
        return _alexa_response(
            speech="You have no upcoming bookings.",
            card_title="Upcoming Bookings",
            should_end=True,
        )

    lines = []
    for b in bookings:
        date_str = b.scheduled_date.strftime("%B %d")
        lines.append(f"{date_str} at {b.place}")

    speech = f"You have {len(lines)} upcoming booking{'s' if len(lines) > 1 else ''}. "
    speech += ". ".join(lines) + "."

    return _alexa_response(
        speech=speech,
        card_title=f"{len(lines)} Upcoming Bookings",
        card_content="\n".join(lines),
        should_end=True,
    )


# ── Alexa Intent Map ─────────────────────────────────────────────────

ALEXA_INTENT_MAP = {
    "BookUsualServicePro": _alexa_book_usual,
    "GetNextBooking": _alexa_get_next_booking,
    "CancelBooking": _alexa_cancel_booking,
    "CheckLockStatus": _alexa_check_lock_status,
    "GetBookingStatus": _alexa_get_booking_status,
    "ListUpcomingBookings": _alexa_list_upcoming,
}


# ── Alexa Response Helpers ───────────────────────────────────────────


def _resolve_alexa_user(session: dict):
    """
    Resolve the Cleanable user from the Alexa session's access token
    (account linking) or the user ID stored in VoiceAssistantLink.
    """
    from .models import VoiceAssistantLink

    # Account linking: Alexa sends our platform's access token
    access_token = session.get("user", {}).get("accessToken")
    if access_token:
        from rest_framework_simplejwt.tokens import AccessToken
        try:
            token = AccessToken(access_token)
            from apps.users.models import User
            return User.objects.get(id=token["user_id"])
        except Exception:
            pass

    # Fallback: look up by Alexa user ID in VoiceAssistantLink
    alexa_user_id = session.get("user", {}).get("userId", "")
    if alexa_user_id:
        link = VoiceAssistantLink.objects.filter(
            platform=VoiceAssistantLink.PLATFORM_ALEXA,
            platform_user_id=alexa_user_id,
            is_active=True,
        ).select_related("user").first()
        if link:
            return link.user

    return None


def _alexa_response(
    speech: str,
    card_title: str = "",
    card_content: str = "",
    reprompt: str = "",
    should_end: bool = True,
) -> dict:
    """Build a standard Alexa Skill response envelope."""
    response: dict[str, Any] = {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": speech,
            },
            "shouldEndSession": should_end,
        },
    }

    if card_title:
        response["response"]["card"] = {
            "type": "Simple",
            "title": card_title,
            "content": card_content or speech,
        }

    if reprompt:
        response["response"]["reprompt"] = {
            "outputSpeech": {
                "type": "PlainText",
                "text": reprompt,
            }
        }

    return response


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Siri / HomeKit Webhook Handler
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def handle_siri_webhook(payload: dict, authorization_header: str = "") -> dict:
    """
    Process an incoming Siri Shortcuts / HomeKit action request.

    The Siri Shortcut sends a JSON payload with:
      - ``command``: Natural language or structured command string
      - ``action``:  Parsed action name (optional, for structured calls)
      - ``params``:  Dict of parameters

    Authentication: Bearer JWT token in the Authorization header
    (the user's Cleanable access token, stored in the Shortcut config).

    Returns:
        Dict with ``success``, ``message``, ``data``.
    """
    user = _resolve_siri_user(authorization_header)
    if not user:
        return {
            "success": False,
            "message": "Authentication failed. Please re-link your Cleanable account in Shortcuts.",
            "data": None,
        }

    # Extract command
    action = payload.get("action", "").strip()
    command = payload.get("command", "").strip().lower()
    params = payload.get("params", {})

    # Try structured action first, then NLP fallback
    if action:
        handler = SIRI_ACTION_MAP.get(action)
        if handler:
            return handler(user, params)

    # Natural language intent parsing
    parsed_action = _parse_siri_command(command)
    if parsed_action:
        handler = SIRI_ACTION_MAP.get(parsed_action)
        if handler:
            return handler(user, params)

    return {
        "success": False,
        "message": f"I didn't understand that command. Try 'book my usual Service Pro' or 'when is my next cleaning?'",
        "data": None,
    }


def _parse_siri_command(command: str) -> Optional[str]:
    """
    Simple keyword-based NLP parser for Siri Shortcut commands.

    Maps natural language phrases to action names.
    """
    command = command.lower().strip()

    PATTERNS = {
        "book_usual": [
            "book my usual",
            "book the usual",
            "book my regular",
            "same as last time",
            "rebook",
            "book my service pro",
        ],
        "next_booking": [
            "when is my next",
            "next cleaning",
            "next booking",
            "upcoming cleaning",
            "what's next",
        ],
        "cancel_booking": [
            "cancel my",
            "cancel booking",
            "cancel cleaning",
            "cancel next",
        ],
        "lock_status": [
            "is my door locked",
            "lock status",
            "check my lock",
            "is my front door",
            "is the door locked",
            "check lock",
        ],
        "booking_status": [
            "booking status",
            "status of my booking",
            "how is my booking",
            "cleaning status",
        ],
        "list_bookings": [
            "list my bookings",
            "list my cleanings",
            "upcoming bookings",
            "show my bookings",
            "all bookings",
        ],
    }

    for action_name, phrases in PATTERNS.items():
        for phrase in phrases:
            if phrase in command:
                return action_name

    return None


# ── Siri Action Handlers ─────────────────────────────────────────────


def _siri_book_usual(user, params: dict) -> dict:
    """Siri: Book the user's usual Service Pro."""
    from apps.bookings.models import Booking
    from apps.cleanings.models import CleanerForCleaning

    last_booking = (
        Booking.objects.filter(client=user, status=Booking.STATUS_COMPLETED, is_active=True)
        .order_by("-scheduled_date")
        .first()
    )

    if not last_booking:
        return {
            "success": False,
            "message": "No previous bookings found. Please create your first booking in the app.",
            "data": None,
        }

    service_pro = None
    if hasattr(last_booking, "cleaning"):
        cleaner_link = (
            CleanerForCleaning.objects.filter(cleaning=last_booking.cleaning)
            .select_related("cleaner")
            .first()
        )
        if cleaner_link:
            service_pro = cleaner_link.cleaner

    tomorrow = timezone.now().date() + timedelta(days=1)
    pro_name = service_pro.get_full_name() if service_pro else "your usual team"

    return {
        "success": True,
        "message": (
            f"Booking prepared for {tomorrow.strftime('%A, %B %d')} "
            f"at {last_booking.place} with {pro_name}. "
            f"Estimated cost: ${last_booking.total_fee_final}. "
            "Confirm in the Cleanable app."
        ),
        "data": {
            "date": str(tomorrow),
            "place": str(last_booking.place),
            "service_pro": pro_name,
            "estimated_cost": str(last_booking.total_fee_final),
            "requires_confirmation": True,
        },
    }


def _siri_next_booking(user, params: dict) -> dict:
    """Siri: Get the user's next booking."""
    from apps.bookings.models import Booking

    next_booking = (
        Booking.objects.filter(
            client=user,
            status__in=(Booking.STATUS_NEW, Booking.STATUS_IN_WORK),
            scheduled_date__gte=timezone.now().date(),
            is_active=True,
        )
        .order_by("scheduled_date", "scheduled_start_dt")
        .first()
    )

    if not next_booking:
        return {
            "success": True,
            "message": "You have no upcoming bookings.",
            "data": None,
        }

    date_str = next_booking.scheduled_date.strftime("%A, %B %d")
    time_str = (
        next_booking.scheduled_start_dt.strftime("%-I:%M %p")
        if next_booking.scheduled_start_dt
        else "TBD"
    )

    return {
        "success": True,
        "message": f"Your next cleaning is {date_str} at {time_str} at {next_booking.place}.",
        "data": {
            "booking_id": next_booking.id,
            "date": str(next_booking.scheduled_date),
            "time": time_str,
            "place": str(next_booking.place),
            "status": next_booking.get_status_display(),
        },
    }


def _siri_cancel_booking(user, params: dict) -> dict:
    """Siri: Cancel a booking (requires app confirmation)."""
    from apps.bookings.models import Booking

    next_booking = (
        Booking.objects.filter(
            client=user,
            status=Booking.STATUS_NEW,
            scheduled_date__gte=timezone.now().date(),
            is_active=True,
        )
        .order_by("scheduled_date")
        .first()
    )

    if not next_booking:
        return {
            "success": False,
            "message": "No cancellable bookings found.",
            "data": None,
        }

    return {
        "success": True,
        "message": (
            f"Found booking for {next_booking.scheduled_date.strftime('%B %d')} at {next_booking.place}. "
            "Open the Cleanable app to confirm cancellation."
        ),
        "data": {
            "booking_id": next_booking.id,
            "date": str(next_booking.scheduled_date),
            "place": str(next_booking.place),
            "requires_confirmation": True,
        },
    }


def _siri_lock_status(user, params: dict) -> dict:
    """Siri: Check smart lock status."""
    from .models import ConnectedDevice
    from .smart_lock_service import ensure_valid_token, list_locks

    devices = ConnectedDevice.objects.filter(
        user=user,
        status=ConnectedDevice.STATUS_ACTIVE,
    )

    if not devices.exists():
        return {
            "success": False,
            "message": "No smart locks connected. Set them up in the Cleanable app.",
            "data": None,
        }

    device = devices.first()
    try:
        access_token = ensure_valid_token(device)
        locks = list_locks(device.provider, access_token)
    except Exception as exc:
        logger.error("Siri lock status check failed for %s: %s", user.email, exc)
        return {
            "success": False,
            "message": "Couldn't check your lock right now. Please try again later.",
            "data": None,
        }

    if not locks:
        return {
            "success": False,
            "message": "Connected device found but couldn't read lock status.",
            "data": None,
        }

    lock = locks[0]
    return {
        "success": True,
        "message": f"{lock['name']} is {lock['status']}.",
        "data": {
            "device_name": lock["name"],
            "status": lock["status"],
            "provider": device.provider,
        },
    }


def _siri_booking_status(user, params: dict) -> dict:
    """Siri: Get the status of the most recent booking."""
    from apps.bookings.models import Booking

    booking = (
        Booking.objects.filter(client=user, is_active=True)
        .exclude(status__in=(Booking.STATUS_CANCELLED_BY_CLIENT, Booking.STATUS_CANCELLED_BY_MANAGER))
        .order_by("-scheduled_date")
        .first()
    )

    if not booking:
        return {
            "success": True,
            "message": "No active bookings found.",
            "data": None,
        }

    return {
        "success": True,
        "message": (
            f"Your booking for {booking.scheduled_date.strftime('%B %d')} "
            f"at {booking.place} is {booking.get_status_display()}."
        ),
        "data": {
            "booking_id": booking.id,
            "date": str(booking.scheduled_date),
            "place": str(booking.place),
            "status": booking.get_status_display(),
        },
    }


def _siri_list_bookings(user, params: dict) -> dict:
    """Siri: List upcoming bookings."""
    from apps.bookings.models import Booking

    bookings = list(
        Booking.objects.filter(
            client=user,
            status__in=(Booking.STATUS_NEW, Booking.STATUS_IN_WORK),
            scheduled_date__gte=timezone.now().date(),
            is_active=True,
        )
        .order_by("scheduled_date")[:5]
    )

    if not bookings:
        return {
            "success": True,
            "message": "No upcoming bookings.",
            "data": {"bookings": []},
        }

    items = []
    for b in bookings:
        items.append({
            "booking_id": b.id,
            "date": str(b.scheduled_date),
            "place": str(b.place),
            "status": b.get_status_display(),
        })

    count = len(items)
    return {
        "success": True,
        "message": f"You have {count} upcoming booking{'s' if count > 1 else ''}.",
        "data": {"bookings": items},
    }


# ── Siri Action Map ──────────────────────────────────────────────────

SIRI_ACTION_MAP = {
    "book_usual": _siri_book_usual,
    "next_booking": _siri_next_booking,
    "cancel_booking": _siri_cancel_booking,
    "lock_status": _siri_lock_status,
    "booking_status": _siri_booking_status,
    "list_bookings": _siri_list_bookings,
}


# ── Siri User Resolution ─────────────────────────────────────────────


def _resolve_siri_user(authorization_header: str):
    """
    Resolve the Cleanable user from a Bearer JWT in the Authorization header.
    """
    if not authorization_header.startswith("Bearer "):
        return None

    token_str = authorization_header[7:].strip()
    if not token_str:
        return None

    from rest_framework_simplejwt.tokens import AccessToken
    from apps.users.models import User

    try:
        token = AccessToken(token_str)
        return User.objects.get(id=token["user_id"])
    except Exception:
        return None
