"""
apps.api models
===============

This file makes the `apps.api` app's wallet models discoverable by
Django's migration framework.  It re-exports everything from
`models_wallet` so that ``python manage.py makemigrations api`` picks
them up correctly.
"""

from .models_wallet import DigitalWallet, WalletTransaction, PayoutRequest  # noqa: F401

__all__ = [
    "DigitalWallet",
    "WalletTransaction",
    "PayoutRequest",
]
