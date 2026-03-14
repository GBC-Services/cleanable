"""
OAuth2 Provider Framework
=========================

Provides the Django models and utility layer for acting as an OAuth2
**client** that connects to third‑party smart‑home APIs (e.g., Ring,
Nest, SmartThings, August).  This is the *provider framework* — the
actual token exchange flows are triggered per‑integration.

Architecture:
  ┌──────────────┐        ┌────────────────────┐
  │  Next.js UI  │───────>│  Django API         │
  │  "Connect    │  POST  │  /api/v1/oauth2/    │
  │   Ring"      │───────>│    initiate/        │
  └──────────────┘        └────────┬───────────┘
                                   │ redirect
                          ┌────────▼───────────┐
                          │  3rd‑party OAuth2   │
                          │  (e.g., Ring API)   │
                          └────────┬───────────┘
                                   │ callback
                          ┌────────▼───────────┐
                          │  /api/v1/oauth2/    │
                          │    callback/        │
                          │  → store tokens     │
                          └────────────────────┘

Models:
  - ``OAuth2Integration``:  Registry of supported smart‑home providers
  - ``OAuth2Connection``:   Per‑user connection storing encrypted tokens

Security:
  - Refresh tokens are encrypted at rest via Fernet (``OAUTH2_ENCRYPTION_KEY``)
  - Access tokens are *never* stored; they are fetched on‑demand from
    the provider using the stored refresh token
  - PKCE is enforced for all public clients
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.users.models import User
from apps.utils.models import BaseModel


class OAuth2Integration(BaseModel):
    """
    Registry row for each supported smart‑home provider.

    Example:
        name="Ring"
        slug="ring"
        authorize_url="https://oauth.ring.com/authorize"
        token_url="https://oauth.ring.com/token"
        scopes="read write"
        client_id="abc123"
        client_secret="<encrypted>"
    """

    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=64, unique=True)
    icon_url = models.URLField(blank=True, default="")

    # OAuth2 endpoints
    authorize_url = models.URLField()
    token_url = models.URLField()
    revoke_url = models.URLField(blank=True, default="")
    scopes = models.CharField(
        max_length=512, blank=True, default="",
        help_text="Space-separated list of default scopes.",
    )

    # Client credentials (stored server‑side only)
    client_id = models.CharField(max_length=256)
    client_secret = models.CharField(
        max_length=512, blank=True, default="",
        help_text="Encrypted at rest. Empty for PKCE‑only public clients.",
    )

    # Behaviour flags
    use_pkce = models.BooleanField(
        default=True,
        help_text="Require PKCE (S256) for the authorization code flow.",
    )
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OAuth2Connection(BaseModel):
    """
    Per‑user, per‑integration connection storing the encrypted
    refresh token and metadata.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name="oauth2_connections",
    )
    integration = models.ForeignKey(
        OAuth2Integration, on_delete=models.CASCADE,
        related_name="connections",
    )

    # Token storage (refresh only — access tokens are ephemeral)
    encrypted_refresh_token = models.TextField(
        blank=True, default="",
        help_text="Fernet-encrypted refresh token.",
    )
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes_granted = models.CharField(max_length=512, blank=True, default="")

    # OAuth2 flow state
    state = models.UUIDField(default=uuid.uuid4, editable=False)
    pkce_code_verifier = models.CharField(
        max_length=128, blank=True, default="",
    )

    # Connection lifecycle
    STATUS_PENDING = "pending"
    STATUS_CONNECTED = "connected"
    STATUS_EXPIRED = "expired"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_CONNECTED, "Connected"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_REVOKED, "Revoked"),
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    connected_at = models.DateTimeField(null=True, blank=True)
    external_account_id = models.CharField(
        max_length=256, blank=True, default="",
        help_text="External user/account ID from the provider.",
    )

    class Meta:
        unique_together = ("user", "integration")
        ordering = ["-connected_at"]

    def __str__(self):
        return f"{self.user.email} ↔ {self.integration.name} ({self.status})"

    @property
    def is_token_expired(self):
        if self.token_expires_at is None:
            return True
        return timezone.now() >= self.token_expires_at

    def mark_connected(self, encrypted_refresh, expires_in=None, scopes=""):
        """Called after a successful token exchange."""
        self.encrypted_refresh_token = encrypted_refresh
        self.status = self.STATUS_CONNECTED
        self.connected_at = timezone.now()
        self.scopes_granted = scopes
        if expires_in:
            self.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        self.save()

    def mark_revoked(self):
        self.status = self.STATUS_REVOKED
        self.encrypted_refresh_token = ""
        self.save()


class OAuth2AuditLog(BaseModel):
    """
    Immutable audit trail for every OAuth2 token operation.
    """

    ACTION_INITIATE = "initiate"
    ACTION_CALLBACK = "callback"
    ACTION_REFRESH = "refresh"
    ACTION_REVOKE = "revoke"
    ACTION_ERROR = "error"
    ACTIONS = (
        (ACTION_INITIATE, "Initiate"),
        (ACTION_CALLBACK, "Callback"),
        (ACTION_REFRESH, "Refresh"),
        (ACTION_REVOKE, "Revoke"),
        (ACTION_ERROR, "Error"),
    )

    connection = models.ForeignKey(
        OAuth2Connection, on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=16, choices=ACTIONS)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.connection} — {self.action} @ {self.created}"
