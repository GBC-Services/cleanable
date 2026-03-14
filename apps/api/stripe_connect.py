"""
Stripe Connect Service
======================

All Stripe Connect Express operations for Cleanable:

  - create_connect_account   — create Express account for Agency Owner
  - create_account_link      — generate onboarding link
  - create_split_payment     — PaymentIntent with transfer + platform fee
  - process_payout           — instant payout to Service Pro's connected account
  - get_account_balance      — retrieve balance for a connected account
  - handle_webhook           — process incoming Stripe webhooks

Migration note
--------------
Ensure the Company model has a ``stripe_account_id`` field (CharField,
max_length=64, blank=True, null=True).  See apps/companies/models.py.
"""

import logging

import stripe
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Initialise once at import time; respects the per-request override pattern
stripe.api_key = settings.STRIPE_SECRET_KEY


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Connect Account Management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def create_connect_account(user):
    """
    Create a Stripe Express account for an Agency Owner.

    Stores the resulting ``account_id`` on the user's associated Company
    via ``getattr`` / ``setattr`` to remain migration-safe if the field
    has not yet been added.

    Returns:
        stripe.Account — the newly created (or existing) account object.

    Raises:
        ValueError — if the user has no associated company.
        stripe.error.StripeError — on Stripe API failures.
    """
    company = getattr(user, "company", None)
    if company is None:
        raise ValueError(
            f"User {user.email} has no associated company."
        )

    # Idempotency: if an account already exists, return it
    existing_account_id = getattr(company, "stripe_account_id", None)
    if existing_account_id:
        return stripe.Account.retrieve(existing_account_id)

    account = stripe.Account.create(
        type="express",
        email=user.email,
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        business_type="company",
        metadata={
            "company_id": str(company.id),
            "company_name": company.name or "",
            "user_id": str(user.id),
        },
    )

    # Persist the account ID if the field exists on the model
    try:
        company.stripe_account_id = account["id"]
        company.save(update_fields=["stripe_account_id"])
    except Exception as exc:
        logger.warning(
            "Could not save stripe_account_id on Company %s: %s",
            company.id,
            exc,
        )

    return account


def create_account_link(user):
    """
    Generate a Stripe Connect onboarding link for an Agency Owner.

    The link redirects back to the frontend after onboarding is
    completed or the user abandons the flow.

    Returns:
        str — the one-time onboarding URL.

    Raises:
        ValueError — if the company has no stripe_account_id yet.
    """
    company = getattr(user, "company", None)
    if company is None:
        raise ValueError(f"User {user.email} has no associated company.")

    account_id = getattr(company, "stripe_account_id", None)
    if not account_id:
        # Auto-create the account if it doesn't exist yet
        account = create_connect_account(user)
        account_id = account["id"]

    base_url = getattr(settings, "FRONTEND_BASE_URL", "https://cleanable.app")
    account_link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=f"{base_url}/stripe/connect/refresh/",
        return_url=f"{base_url}/stripe/connect/return/",
        type="account_onboarding",
    )
    return account_link["url"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Payment Splitting
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def create_split_payment(booking, platform_fee_percent=None):
    """
    Create a PaymentIntent that splits revenue between the platform and
    the agency's connected Stripe account.

    Args:
        booking: Booking model instance (must have total_fee_final,
                 stripe_payment_intent_id, place.company or company FK).
        platform_fee_percent (float | None): Override the default platform
            fee percentage from settings (default 15 %).

    Returns:
        stripe.PaymentIntent — the created intent object.
    """
    if platform_fee_percent is None:
        platform_fee_percent = getattr(
            settings, "STRIPE_CONNECT_PLATFORM_FEE_PERCENT", 15.0
        )

    # Resolve connected account — bookings may link a company via cleaning
    company = None
    if hasattr(booking, "company") and booking.company:
        company = booking.company
    elif booking.place and hasattr(booking.place, "region"):
        # Fallback: pick any active company in the same region
        from apps.companies.models import Company
        company = Company.objects.filter(
            region=booking.place.region, is_active=True
        ).first()

    stripe_account_id = getattr(company, "stripe_account_id", None) if company else None

    amount_cents = int(float(booking.total_fee_final) * 100)
    platform_fee_cents = int(amount_cents * platform_fee_percent / 100)

    create_kwargs = dict(
        amount=amount_cents,
        currency="usd",
        metadata={
            "booking_uuid": str(booking.uuid),
            "booking_id": str(booking.id),
        },
        description=f"Cleanable booking #{booking.short_id}",
    )

    if stripe_account_id:
        create_kwargs["application_fee_amount"] = platform_fee_cents
        create_kwargs["transfer_data"] = {"destination": stripe_account_id}

    intent = stripe.PaymentIntent.create(**create_kwargs)
    return intent


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Payouts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def process_payout(user, amount):
    """
    Trigger an instant payout to a Service Pro's connected Stripe account.

    The payout is issued against the connected account balance, not the
    platform balance.

    Args:
        user:   User instance with a DigitalWallet that has a
                stripe_account_id.
        amount: Decimal or float — payout amount in USD.

    Returns:
        stripe.Payout — the created payout object.

    Raises:
        ValueError — if the wallet or stripe_account_id is missing.
        stripe.error.StripeError — on Stripe API failures.
    """
    try:
        wallet = user.digital_wallet
    except Exception:
        raise ValueError(f"User {user.email} has no DigitalWallet.")

    stripe_account_id = wallet.stripe_account_id
    if not stripe_account_id:
        raise ValueError(
            f"Service Pro {user.email} has no connected Stripe account."
        )

    amount_cents = int(float(amount) * 100)
    payout = stripe.Payout.create(
        amount=amount_cents,
        currency="usd",
        method="instant",
        stripe_account=stripe_account_id,
        metadata={"user_id": str(user.id)},
    )
    return payout


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Balance Enquiry
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def get_account_balance(stripe_account_id):
    """
    Retrieve the Stripe balance for a connected account.

    Args:
        stripe_account_id (str): Stripe Connect account ID (acct_…).

    Returns:
        stripe.Balance — balance object with ``available`` and
        ``pending`` lists.
    """
    return stripe.Balance.retrieve(stripe_account=stripe_account_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Webhook Processing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def handle_webhook(payload, sig_header):
    """
    Validate and process an incoming Stripe webhook event.

    Args:
        payload (bytes):   Raw request body.
        sig_header (str):  Value of the ``Stripe-Signature`` HTTP header.

    Returns:
        dict — ``{"status": "handled", "event_type": <type>}``
             or ``{"status": "ignored", "event_type": <type>}``

    Raises:
        stripe.error.SignatureVerificationError — on invalid signature.
        ValueError — if STRIPE_WEBHOOK_SECRET is not configured.
    """
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise ValueError(
            "STRIPE_WEBHOOK_SECRET is not configured in settings."
        )

    event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)

    handler = _WEBHOOK_HANDLERS.get(event["type"])
    if handler:
        handler(event)
        return {"status": "handled", "event_type": event["type"]}

    return {"status": "ignored", "event_type": event["type"]}


# ── Individual event handlers ─────────────────────────────────────────


def _handle_account_updated(event):
    """Sync Company.stripe_account_id state when an Express account updates."""
    account = event["data"]["object"]
    account_id = account["id"]
    charges_enabled = account.get("charges_enabled", False)
    payouts_enabled = account.get("payouts_enabled", False)

    logger.info(
        "Stripe account.updated: %s charges_enabled=%s payouts_enabled=%s",
        account_id, charges_enabled, payouts_enabled,
    )

    from apps.companies.models import Company
    Company.objects.filter(stripe_account_id=account_id).update(
        # You can store additional fields here as your model evolves.
        # For now we just log; the field itself is already set.
    )


def _handle_payment_intent_succeeded(event):
    """Mark the corresponding Booking as paid."""
    intent = event["data"]["object"]
    booking_uuid = intent.get("metadata", {}).get("booking_uuid")
    if not booking_uuid:
        return

    from apps.bookings.models import Booking
    try:
        booking = Booking.objects.get(uuid=booking_uuid)
        booking.stripe_payment_intent_id = intent["id"]
        booking.payment_status = Booking.PAYMENT_STATUS_FULLY_PAID
        booking.save(update_fields=["stripe_payment_intent_id", "payment_status"])
        logger.info(
            "Booking %s marked as paid via PaymentIntent %s",
            booking_uuid, intent["id"],
        )
    except Booking.DoesNotExist:
        logger.warning(
            "payment_intent.succeeded: booking %s not found.", booking_uuid
        )


def _handle_payout_paid(event):
    """Update PayoutRequest status to COMPLETED when Stripe payout lands."""
    payout = event["data"]["object"]
    payout_id = payout["id"]

    from apps.api.models_wallet import PayoutRequest
    updated = PayoutRequest.objects.filter(
        stripe_payout_id=payout_id, status=PayoutRequest.STATUS_PROCESSING
    ).update(
        status=PayoutRequest.STATUS_COMPLETED,
        completed_at=timezone.now(),
    )
    logger.info(
        "payout.paid: updated %d PayoutRequest(s) for payout %s",
        updated, payout_id,
    )


_WEBHOOK_HANDLERS = {
    "account.updated": _handle_account_updated,
    "payment_intent.succeeded": _handle_payment_intent_succeeded,
    "payout.paid": _handle_payout_paid,
}
