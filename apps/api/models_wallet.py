"""
Digital Wallet Models
=====================

Provides per-Service-Pro wallet accounting, transaction ledger, and
payout-request lifecycle.  These models live in apps.api so they are
auto-discovered by the existing ``apps.api`` INSTALLED_APPS entry.

Migration note
--------------
After saving this file run::

    python manage.py makemigrations api
    python manage.py migrate
"""

from decimal import Decimal

from django.db import models

from apps.users.models import User


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DigitalWallet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class DigitalWallet(models.Model):
    """One-to-one wallet for every Service Pro."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="digital_wallet",
    )

    available_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    pending_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    lifetime_earnings = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
    )

    # Stripe Connect Express account attached to this pro
    stripe_account_id = models.CharField(
        max_length=64, blank=True, null=True, default=None,
        help_text="Stripe Connect Express account ID (acct_…)",
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "api"
        verbose_name = "Digital Wallet"
        verbose_name_plural = "Digital Wallets"

    def __str__(self):
        return f"Wallet({self.user.email}) available={self.available_balance}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WalletTransaction
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class WalletTransaction(models.Model):
    """Immutable ledger entry for every money movement on a wallet."""

    TYPE_EARNING = "EARNING"
    TYPE_PAYOUT = "PAYOUT"
    TYPE_ADJUSTMENT = "ADJUSTMENT"
    TYPE_REFUND = "REFUND"

    TRANSACTION_TYPES = (
        (TYPE_EARNING, "Earning"),
        (TYPE_PAYOUT, "Payout"),
        (TYPE_ADJUSTMENT, "Adjustment"),
        (TYPE_REFUND, "Refund"),
    )

    STATUS_PENDING = "PENDING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    STATUSES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    )

    wallet = models.ForeignKey(
        DigitalWallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=16, choices=TRANSACTION_TYPES,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, default="")
    # Stripe transfer_id, payout_id, or any external reference
    reference_id = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=STATUSES, default=STATUS_PENDING,
    )
    # nullable FK — not every transaction is tied to a booking
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True, blank=True, default=None,
        related_name="wallet_transactions",
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "api"
        ordering = ["-created"]
        verbose_name = "Wallet Transaction"
        verbose_name_plural = "Wallet Transactions"

    def __str__(self):
        return (
            f"WalletTx({self.transaction_type}, {self.amount}, "
            f"{self.status})"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PayoutRequest
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PayoutRequest(models.Model):
    """Service Pro's request to withdraw from their available balance."""

    STATUS_PENDING = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    STATUSES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    )

    wallet = models.ForeignKey(
        DigitalWallet,
        on_delete=models.CASCADE,
        related_name="payout_requests",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=16, choices=STATUSES, default=STATUS_PENDING,
    )
    stripe_payout_id = models.CharField(
        max_length=64, blank=True, null=True, default=None,
        help_text="Stripe Payout object ID (po_…)",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True, default=None)
    failure_reason = models.TextField(null=True, blank=True, default=None)

    class Meta:
        app_label = "api"
        ordering = ["-requested_at"]
        verbose_name = "Payout Request"
        verbose_name_plural = "Payout Requests"

    def __str__(self):
        return (
            f"PayoutRequest({self.wallet.user.email}, "
            f"{self.amount}, {self.status})"
        )
