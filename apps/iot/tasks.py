"""
IoT Celery Tasks
=================

Background tasks for the IoT module:

  scrub_old_gps_history
    Runs daily via Celery Beat.  Deletes GPSHistoryLog rows older than
    ``GPS_HISTORY_RETENTION_DAYS`` (default 30 days) to comply with
    data-minimization requirements.

  check_ghost_mode_conflicts
    Scans for Service Pros who have Ghost Mode active during an overlapping
    scheduled booking window.  Sends alerts to the Agency Owner.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrub_old_gps_history(self):
    """
    Delete GPS history logs older than the configured retention period.

    Default retention: 30 days (configurable via ``GPS_HISTORY_RETENTION_DAYS``).

    This task is scheduled to run daily at 03:00 via Celery Beat.
    Batch-deletes in chunks of 5,000 to avoid long-running transactions.
    """
    from apps.iot.privacy_models import GPSHistoryLog

    retention_days = getattr(settings, "GPS_HISTORY_RETENTION_DAYS", 30)
    cutoff = timezone.now() - timedelta(days=retention_days)

    total_deleted = 0
    batch_size = 5_000

    while True:
        # Get IDs to delete in batches (avoids lock contention)
        ids_to_delete = list(
            GPSHistoryLog.objects.filter(recorded_at__lt=cutoff)
            .values_list("id", flat=True)[:batch_size]
        )

        if not ids_to_delete:
            break

        deleted_count, _ = GPSHistoryLog.objects.filter(
            id__in=ids_to_delete
        ).delete()
        total_deleted += deleted_count

        logger.info(
            "scrub_old_gps_history: deleted %d records (batch), total so far: %d",
            deleted_count,
            total_deleted,
        )

    logger.info(
        "scrub_old_gps_history: completed — purged %d records older than %d days",
        total_deleted,
        retention_days,
    )

    return {
        "purged_count": total_deleted,
        "retention_days": retention_days,
        "cutoff": cutoff.isoformat(),
    }


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def check_ghost_mode_conflicts(self):
    """
    Scan for Ghost Mode conflicts with active/upcoming bookings.

    For each Service Pro with Ghost Mode active, check if they have a
    booking within the current time window.  If so, create a GhostModeAlert
    and notify the Agency Owner.

    This can be called periodically (e.g., every 15 min) or triggered
    when Ghost Mode is activated.
    """
    from apps.bookings.models import Booking
    from apps.cleanings.models import Cleaning, CleanerForCleaning
    from apps.iot.privacy_models import GhostModeAlert, GhostModeState
    from apps.users.models import User

    now = timezone.now()
    alerts_created = 0

    # Find all Service Pros with Ghost Mode active
    active_ghost_states = GhostModeState.objects.filter(
        is_active=True,
    ).select_related("service_pro")

    for ghost_state in active_ghost_states:
        pro = ghost_state.service_pro

        # Find active bookings assigned to this Service Pro
        # via CleanerForCleaning → Cleaning → Booking
        active_cleaning_ids = CleanerForCleaning.objects.filter(
            cleaner=pro,
        ).values_list("cleaning__booking_id", flat=True)

        overlapping_bookings = Booking.objects.filter(
            id__in=active_cleaning_ids,
            scheduled_start_dt__lte=now,
            scheduled_end_dt__gte=now,
            status__in=[Booking.STATUS_NEW, Booking.STATUS_IN_WORK],
        )

        for booking in overlapping_bookings:
            # Check if we already sent an alert for this booking today
            existing = GhostModeAlert.objects.filter(
                service_pro=pro,
                booking=booking,
                alert_type=GhostModeAlert.ALERT_GHOST_DURING_JOB,
                created_at__date=now.date(),
            ).exists()

            if existing:
                continue

            # Find the Agency Owner (the company owner for this booking)
            agency_owner = None
            if booking.place and booking.place.client:
                # The agency owner would be found via the cleaning company
                pass

            # Try to find the agency owner through the pro's company
            if pro.company:
                agency_owner = User.objects.filter(
                    company=pro.company,
                    role=User.ROLE_AGENCY_OWNER,
                ).first()

            alert = GhostModeAlert.objects.create(
                service_pro=pro,
                agency_owner=agency_owner,
                booking=booking,
                alert_type=GhostModeAlert.ALERT_GHOST_DURING_JOB,
                message=(
                    f"{pro.get_full_name() or pro.email} has Ghost Mode active "
                    f"during booking #{booking.short_id} "
                    f"({booking.scheduled_start_dt} — {booking.scheduled_end_dt}). "
                    f"Manual geographic check-in is required."
                ),
                metadata={
                    "booking_id": booking.id,
                    "booking_short_id": booking.short_id,
                    "service_pro_id": pro.id,
                    "activated_at": ghost_state.activated_at.isoformat()
                    if ghost_state.activated_at
                    else None,
                },
            )

            alerts_created += 1

            # Send real-time alert via WebSocket if available
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync

                channel_layer = get_channel_layer()
                if channel_layer and agency_owner:
                    async_to_sync(channel_layer.group_send)(
                        f"ghost_alerts_{agency_owner.id}",
                        {
                            "type": "ghost.mode.alert",
                            "payload": {
                                "alert_id": str(alert.uuid),
                                "service_pro_name": pro.get_full_name() or pro.email,
                                "service_pro_id": pro.id,
                                "booking_id": booking.id,
                                "booking_short_id": booking.short_id,
                                "message": alert.message,
                                "timestamp": now.isoformat(),
                            },
                        },
                    )
            except ImportError:
                pass

            logger.info(
                "Ghost Mode alert created: %s during booking #%s",
                pro.email,
                booking.short_id,
            )

    logger.info(
        "check_ghost_mode_conflicts: completed — %d new alerts",
        alerts_created,
    )

    return {"alerts_created": alerts_created}
