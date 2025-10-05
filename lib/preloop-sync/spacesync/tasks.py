import asyncio
from spacesync.config import logger
from spacemodels.db.session import get_db_session
from spacemodels.crud import crud_tracker
from spacesync.scanner.core import scan_tracker


def scan_tracker_task(tracker_id: int, since=None, force_update=False):
    return poll_tracker(tracker_id, since, force_update)


def poll_tracker(tracker_id: int, since=None, force_update=False):
    logger.info(f"Starting scan for tracker {tracker_id}")
    db = next(get_db_session())
    try:
        tracker = crud_tracker.get(db, id=tracker_id)
        if not tracker:
            logger.error(f"Tracker {tracker_id} not found")
            return None

        # Run the async scan_tracker in an event loop
        stats = asyncio.run(
            scan_tracker(db, tracker, since=since, force_update=force_update)
        )
        crud_tracker.validate(db, id=tracker_id, is_valid=True)
        logger.info(f"Scan for tracker {tracker_id} completed. Stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error scanning tracker {tracker_id}: {e}", exc_info=True)
        crud_tracker.validate(db, id=tracker_id, is_valid=False, message=str(e))
        return None
    finally:
        db.close()


def notify_admins(subject: str, message: str, message_html: str = None):
    from spacebridge.utils.email import send_email  # noqa: E402
    from spacebridge.config import settings  # noqa: E402

    logger.info(f"Notifying admins: {subject} - {message}")
    admin_email = settings.product_team_email
    send_email(admin_email, subject, message, message_html)


async def process_webhook_event(
    tracker_id: int, event_type: str, payload: dict, **kwargs
):
    """
    This task is triggered when a webhook event is received from a tracker.
    It uses the FlowTriggerService to check if any flows should be initiated.
    """
    logger.info(f"Processing tracker event: {tracker_id} - {event_type}")
    logger.debug(f"Payload: {payload}")
    logger.debug(f"kwargs: {kwargs}")

    db = next(get_db_session())
    try:
        tracker = crud_tracker.get(db, id=tracker_id)
        if not tracker:
            logger.error(f"Tracker {tracker_id} not found.")
            return

        from spacebridge.services.flow_trigger_service import FlowTriggerService

        event_data = {
            "source": tracker.tracker_type,
            "type": event_type,
            "payload": payload,
            "account_id": tracker.account_id,
            **kwargs,
        }

        trigger_service = FlowTriggerService(db)
        await trigger_service.process_event(event_data)
    finally:
        db.close()
