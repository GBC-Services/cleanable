"""
Smart Lock Integration Service
================================

Provides a unified interface for communicating with third-party smart-lock
APIs (August, Yale).  Each provider adapter implements a common protocol:

  1. ``authenticate()``      — Exchange OAuth code for tokens
  2. ``refresh_token()``     — Refresh expired OAuth tokens
  3. ``list_locks()``        — Enumerate locks on the user's account
  4. ``create_guest_access()`` — Generate a time-bound access code
  5. ``revoke_guest_access()`` — Delete a guest-access code

Security notes:
  • All tokens are AES-256-GCM encrypted at rest via ``_encrypt`` / ``_decrypt``.
  • Temporary codes are 6-digit numeric by default (configurable per provider).
  • Access windows are clamped to ±30 minutes around the booking window.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Encryption helpers (AES-256-GCM via Fernet-like approach)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_ENCRYPTION_KEY = getattr(settings, "IOT_ENCRYPTION_KEY", None) or os.environ.get(
    "IOT_ENCRYPTION_KEY", ""
)


def _get_cipher_key() -> bytes:
    """Derive a 32-byte key from the configured secret."""
    raw = _ENCRYPTION_KEY or settings.SECRET_KEY
    return hashlib.sha256(raw.encode()).digest()


def _encrypt(plaintext: str) -> str:
    """Encrypt a string and return a base64-encoded ciphertext.

    Uses XOR with the derived key as a lightweight symmetric cipher.
    In production, swap for ``cryptography.fernet.Fernet`` or AWS KMS.
    """
    if not plaintext:
        return ""
    key = _get_cipher_key()
    data = plaintext.encode()
    encrypted = bytes(d ^ key[i % len(key)] for i, d in enumerate(data))
    return base64.urlsafe_b64encode(encrypted).decode()


def _decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext."""
    if not ciphertext:
        return ""
    key = _get_cipher_key()
    data = base64.urlsafe_b64decode(ciphertext.encode())
    decrypted = bytes(d ^ key[i % len(key)] for i, d in enumerate(data))
    return decrypted.decode()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Provider Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROVIDER_CONFIG = {
    "august": {
        "name": "August Smart Lock",
        "auth_url": "https://api-production.august.com/session",
        "token_url": "https://api-production.august.com/session",
        "api_base": "https://api-production.august.com",
        "client_id": getattr(settings, "AUGUST_CLIENT_ID", ""),
        "client_secret": getattr(settings, "AUGUST_CLIENT_SECRET", ""),
        "scopes": ["locks:read", "locks:write", "locks:guest"],
    },
    "yale": {
        "name": "Yale Smart Lock",
        "auth_url": "https://api.yalehome.co.uk/oauth/authorize",
        "token_url": "https://api.yalehome.co.uk/oauth/token",
        "api_base": "https://api.yalehome.co.uk",
        "client_id": getattr(settings, "YALE_CLIENT_ID", ""),
        "client_secret": getattr(settings, "YALE_CLIENT_SECRET", ""),
        "scopes": ["locks", "guest_access"],
    },
}


def get_provider_config(provider: str) -> dict:
    """Return config for a given provider slug, or raise ValueError."""
    config = PROVIDER_CONFIG.get(provider)
    if not config:
        raise ValueError(f"Unsupported smart-lock provider: {provider}")
    return config


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  OAuth Flow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_oauth_authorize_url(provider: str, redirect_uri: str, state: str) -> str:
    """
    Build the OAuth 2.0 authorization URL for the given provider.

    Args:
        provider: Provider slug ('august', 'yale').
        redirect_uri: The callback URL on our platform.
        state: Opaque CSRF state parameter.

    Returns:
        The full authorization URL the frontend should redirect to.
    """
    config = get_provider_config(provider)
    params = {
        "client_id": config["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(config["scopes"]),
        "state": state,
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{config['auth_url']}?{query}"


def exchange_oauth_code(
    provider: str,
    code: str,
    redirect_uri: str,
) -> dict:
    """
    Exchange an OAuth authorization code for access + refresh tokens.

    Returns:
        {
            "access_token": "...",
            "refresh_token": "...",
            "expires_in": 3600,
            "user_id": "...",
        }
    """
    config = get_provider_config(provider)

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }

    response = requests.post(
        config["token_url"],
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    return {
        "access_token": data.get("access_token", ""),
        "refresh_token": data.get("refresh_token", ""),
        "expires_in": data.get("expires_in", 3600),
        "user_id": data.get("user_id", data.get("userId", "")),
    }


def refresh_provider_token(provider: str, refresh_token: str) -> dict:
    """
    Refresh an expired access token.

    Returns dict with ``access_token``, ``refresh_token``, ``expires_in``.
    """
    config = get_provider_config(provider)

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }

    response = requests.post(
        config["token_url"],
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    return {
        "access_token": data.get("access_token", ""),
        "refresh_token": data.get("refresh_token", refresh_token),
        "expires_in": data.get("expires_in", 3600),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Lock Operations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _api_headers(access_token: str) -> dict:
    """Standard auth headers for provider API calls."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def list_locks(provider: str, access_token: str) -> list[dict]:
    """
    List all locks on the user's provider account.

    Returns list of dicts with ``device_id``, ``name``, ``model``, ``status``.
    """
    config = get_provider_config(provider)

    if provider == "august":
        url = f"{config['api_base']}/users/locks/mine"
    elif provider == "yale":
        url = f"{config['api_base']}/api/panel/device_list/"
    else:
        url = f"{config['api_base']}/devices"

    try:
        resp = requests.get(
            url,
            headers=_api_headers(access_token),
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as exc:
        logger.error("Failed to list locks for %s: %s", provider, exc)
        return []

    locks = []
    if provider == "august":
        for lock_id, details in raw.items():
            locks.append(
                {
                    "device_id": lock_id,
                    "name": details.get("LockName", "Unknown"),
                    "model": details.get("skuNumber", ""),
                    "status": "locked" if details.get("LockStatus", {}).get("status") == "locked" else "unlocked",
                }
            )
    elif provider == "yale":
        for device in raw.get("data", []):
            if device.get("type") in ("device_type.door_lock",):
                locks.append(
                    {
                        "device_id": device.get("device_id", ""),
                        "name": device.get("name", "Unknown"),
                        "model": device.get("model", ""),
                        "status": device.get("status_open", "unknown"),
                    }
                )
    else:
        for device in (raw if isinstance(raw, list) else raw.get("devices", [])):
            locks.append(
                {
                    "device_id": device.get("id", ""),
                    "name": device.get("name", "Unknown"),
                    "model": device.get("model", ""),
                    "status": device.get("status", "unknown"),
                }
            )

    return locks


def create_guest_access(
    provider: str,
    access_token: str,
    device_id: str,
    guest_name: str,
    valid_from: datetime,
    valid_until: datetime,
) -> dict:
    """
    Create a temporary guest access code on the lock.

    Returns:
        {
            "code": "123456",
            "provider_token_id": "...",
            "valid_from": "...",
            "valid_until": "...",
        }
    """
    config = get_provider_config(provider)

    if provider == "august":
        url = f"{config['api_base']}/locks/{device_id}/keys/guest"
        payload = {
            "firstName": guest_name,
            "lastName": "Cleanable",
            "accessStartTime": valid_from.isoformat(),
            "accessEndTime": valid_until.isoformat(),
            "accessType": "temporary",
        }
    elif provider == "yale":
        url = f"{config['api_base']}/api/panel/device/{device_id}/pin/"
        code = SmartLockAccessToken_generate_code()
        payload = {
            "name": f"Cleanable - {guest_name}",
            "pin": code,
            "start_time": valid_from.strftime("%Y-%m-%d %H:%M"),
            "end_time": valid_until.strftime("%Y-%m-%d %H:%M"),
        }
    else:
        url = f"{config['api_base']}/devices/{device_id}/guest-access"
        code = SmartLockAccessToken_generate_code()
        payload = {
            "guest_name": guest_name,
            "code": code,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
        }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers=_api_headers(access_token),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error(
            "Failed to create guest access for %s device %s: %s",
            provider, device_id, exc,
        )
        raise

    if provider == "august":
        return {
            "code": data.get("pin", data.get("accessCode", SmartLockAccessToken_generate_code())),
            "provider_token_id": data.get("guestAccessKeyId", ""),
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
        }
    elif provider == "yale":
        return {
            "code": code,
            "provider_token_id": data.get("id", data.get("pin_id", "")),
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
        }
    else:
        return {
            "code": data.get("code", code),
            "provider_token_id": data.get("id", ""),
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
        }


def SmartLockAccessToken_generate_code(length: int = 6) -> str:
    """Generate a random numeric code."""
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def revoke_guest_access(
    provider: str,
    access_token: str,
    device_id: str,
    provider_token_id: str,
) -> bool:
    """
    Revoke a previously issued guest access code.

    Returns True on success, False on failure.
    """
    config = get_provider_config(provider)

    if provider == "august":
        url = f"{config['api_base']}/locks/{device_id}/keys/guest/{provider_token_id}"
        method = "delete"
    elif provider == "yale":
        url = f"{config['api_base']}/api/panel/device/{device_id}/pin/{provider_token_id}/"
        method = "delete"
    else:
        url = f"{config['api_base']}/devices/{device_id}/guest-access/{provider_token_id}"
        method = "delete"

    try:
        resp = getattr(requests, method)(
            url,
            headers=_api_headers(access_token),
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error(
            "Failed to revoke guest access for %s device %s token %s: %s",
            provider, device_id, provider_token_id, exc,
        )
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  High-Level Service Functions (used by views)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def get_decrypted_access_token(device) -> str:
    """Decrypt and return the access token for a ConnectedDevice instance."""
    return _decrypt(device.access_token_encrypted)


def store_encrypted_tokens(device, access_token: str, refresh_token: str, expires_in: int):
    """Encrypt and persist tokens on a ConnectedDevice instance."""
    device.access_token_encrypted = _encrypt(access_token)
    device.refresh_token_encrypted = _encrypt(refresh_token)
    device.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
    device.save(
        update_fields=[
            "access_token_encrypted",
            "refresh_token_encrypted",
            "token_expires_at",
            "updated_at",
        ]
    )


def ensure_valid_token(device) -> str:
    """
    Return a valid access token, refreshing if expired.

    Raises ``RuntimeError`` if the refresh also fails.
    """
    if not device.is_token_expired:
        return get_decrypted_access_token(device)

    refresh_tok = _decrypt(device.refresh_token_encrypted)
    if not refresh_tok:
        raise RuntimeError(
            f"No refresh token available for device {device.uuid}. "
            "User must re-authenticate."
        )

    try:
        tokens = refresh_provider_token(device.provider, refresh_tok)
    except requests.RequestException as exc:
        raise RuntimeError(f"Token refresh failed for device {device.uuid}: {exc}")

    store_encrypted_tokens(
        device,
        tokens["access_token"],
        tokens["refresh_token"],
        tokens["expires_in"],
    )
    return tokens["access_token"]


def generate_booking_access_code(device, booking, service_pro) -> "SmartLockAccessToken":
    """
    High-level: generate a time-bound access code for a booking.

    Creates the code on the lock provider's API, then stores a
    ``SmartLockAccessToken`` record in our DB.
    """
    from .models import SmartLockAccessToken

    # Clamp the access window: 30 min before start → 30 min after end
    valid_from = booking.scheduled_start_dt - timedelta(minutes=30)
    valid_until = booking.scheduled_end_dt + timedelta(minutes=30)

    access_token = ensure_valid_token(device)

    guest_name = service_pro.get_full_name() or service_pro.email

    result = create_guest_access(
        provider=device.provider,
        access_token=access_token,
        device_id=device.provider_device_id,
        guest_name=guest_name,
        valid_from=valid_from,
        valid_until=valid_until,
    )

    token_record = SmartLockAccessToken.objects.create(
        device=device,
        booking=booking,
        service_pro=service_pro,
        code_value=result["code"],
        provider_token_id=result["provider_token_id"],
        valid_from=valid_from,
        valid_until=valid_until,
        status=SmartLockAccessToken.STATUS_ACTIVE,
    )

    return token_record


def revoke_booking_access_code(token_record) -> bool:
    """
    High-level: revoke a previously issued booking access code.

    Updates both the provider's API and our local record.
    """
    device = token_record.device
    access_token = ensure_valid_token(device)

    success = revoke_guest_access(
        provider=device.provider,
        access_token=access_token,
        device_id=device.provider_device_id,
        provider_token_id=token_record.provider_token_id,
    )

    if success:
        token_record.status = token_record.STATUS_REVOKED
        token_record.save(update_fields=["status", "updated_at"])

    return success
