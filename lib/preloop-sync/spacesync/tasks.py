import asyncio
from spacesync.config import logger
from spacebridge.utils.email import send_email
from spacebridge.config import settings
from spacemodels.db.session import get_db_session
from spacemodels.crud import crud_tracker
from spacesync.scanner.core import scan_tracker


def add(x, y):
    """A simple synchronous task."""
    print(f"  > Executing add({x}, {y})")
    return x + y


async def send_report(email: str, content: str):
    """An asynchronous task simulating an I/O operation."""
    print(f"  > Executing send_report to {email}...")
    await asyncio.sleep(2)  # Simulate sending an email
    print(f"  > Report sent successfully to {email}.")
    return True


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
    logger.info(f"Notifying admins: {subject} - {message}")
    admin_email = settings.product_team_email
    send_email(admin_email, subject, message, message_html)


def process_tracker_event(tracker_id: int, event_type: str, payload: dict):
    logger.info(f"Processing tracker event: {tracker_id} - {event_type}")
