"""
IoT & Smart Home Models
========================

Data models for the platform's IoT integration layer:

  ConnectedDevice      — An OAuth-linked smart-home device (lock, hub, etc.)
  SmartLockAccessToken — Time-bound access codes generated for a booking
  VoiceAssistantLink   — OAuth link between a user and a voice platform (Alexa / Siri)

Design decisions:
  • ``ConnectedDevice.provider`` uses a plain CharField (not choices) so we can
    add new lock vendors without a migration.
  • Access tokens store ``code_value`` as encrypted text — the field is
    write-once and should never be exposed after initial creation.
  • ``VoiceAssistantLink`` stores the OAuth refresh token in ``encrypted_token``;
    the access token is fetched on demand via the provider's token endpoint.
"""

import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Connected Device
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ConnectedDevice(models.Model):
    """
    A smart-home device linked to a Resident's account via OAuth.

    Supported providers (not limited to):
      - ``august``   — August Smart Lock
      - ``yale``     — Yale Smart Lock
      - ``smartthings`` — Samsung SmartThings hub
    """

    PROVIDER_AUGUST = "august"
    PROVIDER_YALE = "yale"
    PROVIDER_SMARTTHINGS = "smartthings"

    STATUS_ACTIVE = "active"
    STATUS_DISCONNECTED = "disconnected"
    STATUS_PENDING = "pending"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_DISCONNECTED, "Disconnected"),
        (STATUS_PENDING, "Pending Setup"),
    ]

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connected_devices",
    )
    place = models.ForeignKey(
        "clients.Place",
        on_delete=models.CASCADE,
        related_name="connected_devices",
        null=True,
        blank=True,
        help_text="Optional link to a specific Place (apartment/house).",
    )

    # ── Provider details ──────────────────────────────────────────────
    provider = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Smart-lock vendor slug, e.g. 'august', 'yale'.",
    )
    provider_device_id = models.CharField(
        max_length=255,
        help_text="Vendor-side device identifier.",
    )
    device_name = models.CharField(
        max_length=255,
        help_text="Human-friendly device name, e.g. 'Front Door Lock'.",
    )
    device_model = models.CharField(max_length=255, blank=True, default="")

    # ── OAuth tokens (encrypted at rest) ──────────────────────────────
    access_token_encrypted = models.TextField(
        blank=True,
        default="",
        help_text="AES-encrypted OAuth access token for the device provider.",
    )
    refresh_token_encrypted = models.TextField(
        blank=True,
        default="",
        help_text="AES-encrypted OAuth refresh token for the device provider.",
    )
    token_expires_at = models.DateTimeField(null=True, blank=True)

    # ── State ─────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    smart_access_enabled = models.BooleanField(
        default=False,
        help_text=(
            "When True, the platform auto-generates a temporary access code "
            "for booked Service Pros on the day of cleaning."
        ),
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary provider-specific data (firmware version, battery, etc.).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "provider"], name="idx_device_user_provider"),
            models.Index(fields=["provider", "provider_device_id"], name="idx_device_ext_id"),
        ]
        unique_together = [("user", "provider", "provider_device_id")]

    def __str__(self):
        return f"{self.device_name} ({self.provider}) — {self.user.email}"

    @property
    def is_token_expired(self):
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Smart Lock Access Token
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SmartLockAccessToken(models.Model):
    """
    A time-bound access code/token generated for a specific booking.

    The Service Pro receives this code (via push / SMS) on the day of the
    cleaning.  It expires automatically once the booking window closes.
    """

    STATUS_ACTIVE = "active"
    STATUS_USED = "used"
    STATUS_EXPIRED = "expired"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_USED, "Used"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_REVOKED, "Revoked"),
    ]

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    device = models.ForeignKey(
        ConnectedDevice,
        on_delete=models.CASCADE,
        related_name="access_tokens",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="smart_lock_tokens",
    )
    service_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="smart_lock_tokens",
        help_text="The Service Pro who will use this code.",
    )

    # ── Code details ──────────────────────────────────────────────────
    code_value = models.CharField(
        max_length=64,
        help_text="The actual lock code or virtual-key token. Write-once.",
    )
    provider_token_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Vendor-side token/guest-access identifier for revocation.",
    )

    # ── Time window ───────────────────────────────────────────────────
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "status"], name="idx_access_booking_status"),
            models.Index(fields=["device", "valid_from", "valid_until"], name="idx_access_window"),
        ]

    def __str__(self):
        return (
            f"AccessToken {self.uuid} for booking #{self.booking_id} "
            f"({self.valid_from} → {self.valid_until})"
        )

    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.status == self.STATUS_ACTIVE
            and self.valid_from <= now <= self.valid_until
        )

    def expire_if_needed(self):
        """Mark as expired if the window has closed."""
        if self.status == self.STATUS_ACTIVE and timezone.now() > self.valid_until:
            self.status = self.STATUS_EXPIRED
            self.save(update_fields=["status", "updated_at"])
            return True
        return False

    @classmethod
    def generate_code(cls, length=6):
        """Generate a random numeric access code."""
        return "".join([str(secrets.randbelow(10)) for _ in range(length)])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Voice Assistant Link
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class VoiceAssistantLink(models.Model):
    """
    An OAuth link between a Cleanable user and a voice-assistant platform.

    Supported platforms:
      - ``alexa``   — Amazon Alexa (via Alexa Skills Kit)
      - ``siri``    — Apple Siri / HomeKit (via Siri Shortcuts + HomeKit API)
      - ``google``  — Google Assistant (reserved for future use)
    """

    PLATFORM_ALEXA = "alexa"
    PLATFORM_SIRI = "siri"
    PLATFORM_GOOGLE = "google"
    PLATFORM_CHOICES = [
        (PLATFORM_ALEXA, "Amazon Alexa"),
        (PLATFORM_SIRI, "Apple Siri / HomeKit"),
        (PLATFORM_GOOGLE, "Google Assistant"),
    ]

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="voice_assistant_links",
    )

    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        db_index=True,
    )
    platform_user_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="User identifier on the voice platform (e.g. Amazon user ID).",
    )

    # ── OAuth ─────────────────────────────────────────────────────────
    encrypted_token = models.TextField(
        blank=True,
        default="",
        help_text="Encrypted OAuth refresh/access token for the voice platform.",
    )
    token_expires_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-linked_at"]
        unique_together = [("user", "platform")]
        indexes = [
            models.Index(
                fields=["platform", "platform_user_id"],
                name="idx_voice_platform_uid",
            ),
        ]

    def __str__(self):
        return f"{self.get_platform_display()} link for {self.user.email}"
