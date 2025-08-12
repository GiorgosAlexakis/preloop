from spacesync.config import logger
from spacemodels.db.session import get_db_session
from spacemodels.crud import crud_tracker
from spacesync.scanner.core import scan_tracker


def poll_tracker(tracker_id: int):
    return scan_tracker_task(tracker_id)


def scan_tracker_task(tracker_id: int, since=None):
    logger.info(f"Starting scan for tracker {tracker_id}")
    db = next(get_db_session())
    tracker = crud_tracker.get(db, id=tracker_id)
    try:
        stats = scan_tracker(db, tracker, since=since)
        crud_tracker.validate(db, id=tracker_id, is_valid=True)
    except Exception as e:
        crud_tracker.validate(db, id=tracker_id, is_valid=False, message=str(e))
    logger.info(f"Scan for tracker {tracker_id} completed. Stats: {stats}")
    db.close()


def notify_admins(subject: str, message: str, message_html: str = None):
    from spacebridge.utils.email import send_email  # noqa: E402
    from spacebridge.config import settings  # noqa: E402

    logger.info(f"Notifying admins: {subject} - {message}")
    admin_email = settings.product_team_email
    send_email(admin_email, subject, message, message_html)


async def process_webhook_event(tracker_id: int, event_type: str, payload: dict):
    """
    This task is triggered when a webhook event is received from a tracker.
    It uses the FlowTriggerService to check if any flows should be initiated.
    """
    logger.info(f"Processing tracker event: {tracker_id} - {event_type}")
    db = next(get_db_session())
    try:
        tracker = crud_tracker.get(db, id=tracker_id)
        if not tracker or not tracker.project or not tracker.project.organization:
            logger.error(f"Tracker {tracker_id} or its associations not found.")
            return

        from spacebridge.services.flow_trigger_service import FlowTriggerService

        event_data = {
            "source": tracker.tracker_type.value,
            "type": event_type,
            "payload": payload,
            "account_id": tracker.project.organization.account_id,
        }

        trigger_service = FlowTriggerService(db)
        await trigger_service.process_event(event_data)
    finally:
        db.close()
