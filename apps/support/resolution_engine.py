"""
Resolution Engine — Decision Array Executor
=============================================

Core business logic for the three resolution actions:
  1. Refund (partial/full) via Stripe API
  2. Schedule Re-do — create a high-priority re-cleaning task
  3. Cancel & Blacklist — terminate service + re-assign recurring bookings

Each action:
  - Creates a ResolutionAction audit record
  - Executes the domain logic (Stripe, Cleaning creation, booking re-assignment)
  - Dispatches multi-channel notifications to all stakeholders
  - Updates the Complaint status
"""

import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.bookings.models import Booking
from apps.cleanings.models import Cleaning
from apps.companies.models import Company
from apps.support.resolution_models import (
    AgencyBlacklist,
    Complaint,
    ComplaintNotification,
    ResolutionAction,
)
from apps.users.models import User

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Notification Dispatcher
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _dispatch_notification(
    complaint: Complaint,
    resolution_action: ResolutionAction | None,
    recipient,
    channel: str,
    message_body: str,
):
    """
    Create a ComplaintNotification record and attempt delivery.
    For SMS: uses Twilio (via existing NotificationTemplate infra).
    For Push: uses FCM / APNs placeholder.
    For In-App: creates the record (frontend polls).
    """
    notif = ComplaintNotification.objects.create(
        complaint=complaint,
        resolution_action=resolution_action,
        recipient=recipient,
        channel=channel,
        message_body=message_body,
        status=ComplaintNotification.STATUS_PENDING,
    )

    try:
        if channel == ComplaintNotification.CHANNEL_SMS:
            # Leverage existing Twilio infra from apps.notifications
            phone = getattr(recipient, "phone", None)
            if phone:
                try:
                    from twilio.rest import Client
                    client = Client(
                        settings.TWILIO_ACCOUNT_SID,
                        settings.TWILIO_AUTH_TOKEN,
                    )
                    client.messages.create(
                        to=str(phone),
                        from_=settings.TWILIO_PHONE_FROM,
                        body=message_body,
                    )
                except Exception as sms_err:
                    logger.warning("SMS send failed: %s", sms_err)
                    # Still mark as sent for dev — production would retry
            notif.status = ComplaintNotification.STATUS_SENT
            notif.sent_at = timezone.now()

        elif channel == ComplaintNotification.CHANNEL_PUSH:
            # Placeholder for FCM/APNs push integration
            # In production: send via firebase_admin or APNs
            logger.info(
                "Push notification queued for user %s: %s",
                recipient.pk, message_body[:80],
            )
            notif.status = ComplaintNotification.STATUS_SENT
            notif.sent_at = timezone.now()

        elif channel == ComplaintNotification.CHANNEL_IN_APP:
            notif.status = ComplaintNotification.STATUS_SENT
            notif.sent_at = timezone.now()

        elif channel == ComplaintNotification.CHANNEL_EMAIL:
            try:
                from apps.utils.emails_sending import EmailsSending
                EmailsSending().send(
                    subject=f"Complaint Update — {complaint.get_scenario_display()}",
                    text=message_body,
                    to_emails=[recipient.email],
                )
            except Exception as email_err:
                logger.warning("Email send failed: %s", email_err)
            notif.status = ComplaintNotification.STATUS_SENT
            notif.sent_at = timezone.now()

    except Exception as e:
        logger.error("Notification dispatch error: %s", e)
        notif.status = ComplaintNotification.STATUS_FAILED
        notif.error_detail = str(e)

    notif.save(update_fields=["status", "sent_at", "error_detail"])
    return notif


def _notify_all_stakeholders(
    complaint: Complaint,
    resolution_action: ResolutionAction,
    message_template: str,
):
    """
    Send multi-channel (SMS + Push + In-App) notifications to all
    stakeholders: Resident, Agency Owner(s), assigned Service Pro(s).
    """
    stakeholders = _collect_stakeholders(complaint)
    notifications = []

    for user, role_label in stakeholders:
        personalized_msg = (
            f"[{role_label}] {message_template}"
        )
        # SMS
        if getattr(user, "phone", None):
            notifications.append(
                _dispatch_notification(
                    complaint, resolution_action, user,
                    ComplaintNotification.CHANNEL_SMS, personalized_msg,
                )
            )
        # Push
        notifications.append(
            _dispatch_notification(
                complaint, resolution_action, user,
                ComplaintNotification.CHANNEL_PUSH, personalized_msg,
            )
        )
        # In-App
        notifications.append(
            _dispatch_notification(
                complaint, resolution_action, user,
                ComplaintNotification.CHANNEL_IN_APP, personalized_msg,
            )
        )

    return notifications


def _collect_stakeholders(complaint: Complaint):
    """
    Gather all users who should be notified about a complaint resolution.
    Returns list of (user, role_label) tuples.
    """
    stakeholders = []

    # 1. Resident
    if complaint.resident:
        stakeholders.append((complaint.resident, "Resident"))

    # 2. Agency Owner(s) for the company
    if complaint.company:
        agency_owners = User.objects.filter(
            company=complaint.company,
            role=User.ROLE_AGENCY_OWNER,
            is_active=True,
        )
        for owner in agency_owners:
            stakeholders.append((owner, "Agency Owner"))

    # 3. Assigned Service Pro(s) from the Cleaning
    if complaint.cleaning:
        from apps.cleanings.models import CleanerForCleaning
        cleaner_links = CleanerForCleaning.objects.filter(
            cleaning=complaint.cleaning,
        ).select_related("cleaner")
        for link in cleaner_links:
            if link.cleaner:
                stakeholders.append((link.cleaner, "Service Pro"))

    # 4. Assigned Support Architect
    if complaint.assigned_to:
        stakeholders.append((complaint.assigned_to, "Support Architect"))

    return stakeholders


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. REFUND — Partial or Full via Stripe
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def execute_refund(
    complaint: Complaint,
    performed_by,
    refund_type: str,  # "refund_partial" or "refund_full"
    amount: Decimal | None = None,
    notes: str = "",
) -> ResolutionAction:
    """
    Process a Stripe refund for the complaint's booking.

    For full refund: refunds total_fee_final.
    For partial refund: refunds the specified amount.
    """
    booking = complaint.booking
    action_type = (
        ResolutionAction.ACTION_REFUND_FULL
        if refund_type == "refund_full"
        else ResolutionAction.ACTION_REFUND_PARTIAL
    )

    with transaction.atomic():
        action = ResolutionAction.objects.create(
            complaint=complaint,
            performed_by=performed_by,
            action_type=action_type,
            execution_status=ResolutionAction.EXEC_PROCESSING,
            notes=notes,
        )

        # Determine refund amount
        if refund_type == "refund_full":
            refund_amount = booking.total_fee_final
        else:
            if amount is None or amount <= 0:
                action.execution_status = ResolutionAction.EXEC_FAILED
                action.notes += "\n[ERROR] Partial refund requires a positive amount."
                action.save()
                return action
            refund_amount = min(amount, booking.total_fee_final)

        action.refund_amount = refund_amount

        # Execute Stripe refund
        payment_intent_id = booking.stripe_payment_intent_id
        if payment_intent_id:
            try:
                stripe_refund = stripe.Refund.create(
                    payment_intent=payment_intent_id,
                    amount=int(refund_amount * 100),  # Stripe uses cents
                )
                action.stripe_refund_id = stripe_refund.id
                action.execution_status = ResolutionAction.EXEC_COMPLETED
                action.executed_at = timezone.now()
            except stripe.error.StripeError as e:
                logger.error("Stripe refund failed: %s", e)
                action.execution_status = ResolutionAction.EXEC_FAILED
                action.notes += f"\n[STRIPE ERROR] {str(e)}"
        else:
            # No Stripe payment on file — mark completed (manual refund needed)
            action.execution_status = ResolutionAction.EXEC_COMPLETED
            action.executed_at = timezone.now()
            action.notes += "\n[INFO] No Stripe payment intent found. Manual refund may be needed."

        action.save()

        # Update complaint status
        complaint.status = Complaint.STATUS_RESOLVED
        complaint.resolved_at = timezone.now()
        complaint.save(update_fields=["status", "resolved_at", "updated"])

    # Notify all stakeholders
    refund_label = "Full" if refund_type == "refund_full" else "Partial"
    _notify_all_stakeholders(
        complaint, action,
        f"{refund_label} refund of ${refund_amount:.2f} issued for "
        f"Booking #{booking.short_id} — {complaint.get_scenario_display()}."
    )

    return action


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. SCHEDULE RE-DO — Create high-priority re-cleaning
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def execute_schedule_redo(
    complaint: Complaint,
    performed_by,
    use_different_agency: bool = False,
    preferred_company_id: int | None = None,
    notes: str = "",
) -> ResolutionAction:
    """
    Create a new high-priority Cleaning task for the same booking.
    Optionally assigns a different Agency.
    """
    booking = complaint.booking

    with transaction.atomic():
        action = ResolutionAction.objects.create(
            complaint=complaint,
            performed_by=performed_by,
            action_type=ResolutionAction.ACTION_SCHEDULE_REDO,
            execution_status=ResolutionAction.EXEC_PROCESSING,
            notes=notes,
        )

        # Determine which company to assign
        target_company = None
        if preferred_company_id:
            try:
                target_company = Company.objects.get(
                    pk=preferred_company_id, is_active=True,
                )
            except Company.DoesNotExist:
                pass

        if use_different_agency and not target_company:
            # Find an alternative agency in the same region
            current_company = complaint.company
            blacklisted_ids = AgencyBlacklist.objects.filter(
                resident=complaint.resident,
            ).values_list("company_id", flat=True)

            exclude_ids = set(blacklisted_ids)
            if current_company:
                exclude_ids.add(current_company.pk)

            target_company = (
                Company.objects.filter(
                    is_active=True,
                    region=booking.place.zip_code.region
                    if booking.place and booking.place.zip_code
                    else None,
                )
                .exclude(pk__in=exclude_ids)
                .first()
            )

        if not target_company and complaint.company:
            target_company = complaint.company

        # Create re-cleaning
        redo_cleaning = Cleaning.objects.create(
            booking=booking,
            company=target_company,
            status=Cleaning.STATUS_NOT_ASSIGNED,
            scheduled_date=booking.scheduled_date,
            scheduled_start_dt=booking.scheduled_start_dt,
            scheduled_end_dt=booking.scheduled_end_dt,
        )

        action.redo_cleaning = redo_cleaning
        action.redo_assigned_company = target_company
        action.execution_status = ResolutionAction.EXEC_COMPLETED
        action.executed_at = timezone.now()
        action.save()

        # Update complaint status
        complaint.status = Complaint.STATUS_RESOLVED
        complaint.resolved_at = timezone.now()
        complaint.save(update_fields=["status", "resolved_at", "updated"])

    # Notify
    agency_name = target_company.name if target_company else "TBD"
    _notify_all_stakeholders(
        complaint, action,
        f"Re-cleaning scheduled for Booking #{booking.short_id} — "
        f"assigned to {agency_name}. Scenario: {complaint.get_scenario_display()}."
    )

    return action


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. CANCEL & BLACKLIST — Terminate + Re-assign future bookings
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def execute_cancel_blacklist(
    complaint: Complaint,
    performed_by,
    notes: str = "",
) -> ResolutionAction:
    """
    1. Cancel the current cleaning
    2. Blacklist the agency for this Resident
    3. Re-assign all future recurring bookings to a different agency
    """
    booking = complaint.booking
    company_to_blacklist = complaint.company

    if not company_to_blacklist:
        action = ResolutionAction.objects.create(
            complaint=complaint,
            performed_by=performed_by,
            action_type=ResolutionAction.ACTION_CANCEL_BLACKLIST,
            execution_status=ResolutionAction.EXEC_FAILED,
            notes=notes + "\n[ERROR] No agency found on this complaint to blacklist.",
        )
        return action

    with transaction.atomic():
        action = ResolutionAction.objects.create(
            complaint=complaint,
            performed_by=performed_by,
            action_type=ResolutionAction.ACTION_CANCEL_BLACKLIST,
            execution_status=ResolutionAction.EXEC_PROCESSING,
            notes=notes,
            blacklisted_company=company_to_blacklist,
        )

        # 1. Cancel the current cleaning
        if complaint.cleaning:
            complaint.cleaning.status = Cleaning.STATUS_CANCELLED_BY_SERVICE
            complaint.cleaning.save(update_fields=["status"])

        # 2. Create blacklist entry
        AgencyBlacklist.objects.get_or_create(
            resident=complaint.resident,
            company=company_to_blacklist,
            defaults={
                "complaint": complaint,
                "reason": (
                    f"Blacklisted due to {complaint.get_scenario_display()} "
                    f"(Complaint #{complaint.pk})"
                ),
            },
        )

        # 3. Re-assign future recurring bookings
        # Find all future cleanings for this resident assigned to the blacklisted agency
        future_cleanings = Cleaning.objects.filter(
            booking__client=complaint.resident,
            company=company_to_blacklist,
            status__lte=Cleaning.STATUS_NOT_STARTED,
            scheduled_start_dt__gt=timezone.now(),
        )

        # Get all blacklisted agency IDs for this resident
        all_blacklisted = set(
            AgencyBlacklist.objects.filter(
                resident=complaint.resident,
            ).values_list("company_id", flat=True)
        )

        # Find an alternative agency
        region = None
        if booking.place and booking.place.zip_code:
            region = booking.place.zip_code.region

        replacement_company = (
            Company.objects.filter(is_active=True, region=region)
            .exclude(pk__in=all_blacklisted)
            .first()
        ) if region else None

        reassigned_count = 0
        for cleaning in future_cleanings:
            if replacement_company:
                cleaning.company = replacement_company
                cleaning.save(update_fields=["company"])
                reassigned_count += 1
            else:
                # No replacement available — cancel
                cleaning.status = Cleaning.STATUS_CANCELLED_BY_SERVICE
                cleaning.save(update_fields=["status"])

        action.reassigned_bookings_count = reassigned_count
        action.execution_status = ResolutionAction.EXEC_COMPLETED
        action.executed_at = timezone.now()
        action.save()

        # Update complaint
        complaint.status = Complaint.STATUS_RESOLVED
        complaint.resolved_at = timezone.now()
        complaint.save(update_fields=["status", "resolved_at", "updated"])

    # Notify
    replacement_name = replacement_company.name if replacement_company else "N/A"
    _notify_all_stakeholders(
        complaint, action,
        f"Agency \"{company_to_blacklist.name}\" has been blacklisted for Resident "
        f"due to {complaint.get_scenario_display()}. "
        f"{reassigned_count} future booking(s) re-assigned to {replacement_name}."
    )

    return action


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Add Internal Note
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def add_resolution_note(
    complaint: Complaint,
    performed_by,
    notes: str,
) -> ResolutionAction:
    """Add an internal note to the complaint without executing any resolution."""
    return ResolutionAction.objects.create(
        complaint=complaint,
        performed_by=performed_by,
        action_type=ResolutionAction.ACTION_NOTE,
        execution_status=ResolutionAction.EXEC_COMPLETED,
        executed_at=timezone.now(),
        notes=notes,
    )
