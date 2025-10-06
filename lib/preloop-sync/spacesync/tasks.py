from spacesync.config import logger
from spacemodels.db.session import get_db_session
from spacemodels.crud import crud_tracker
from spacesync.scanner.core import scan_tracker


def scan_tracker_task(tracker_id: int, since=None, force_update=False):
    return poll_tracker(tracker_id, since, force_update)


async def poll_tracker(tracker_id: int, since=None, force_update=False):
    logger.info(f"Starting scan for tracker {tracker_id}")
    db = next(get_db_session())
    try:
        tracker = crud_tracker.get(db, id=tracker_id)
        if not tracker:
            logger.error(f"Tracker {tracker_id} not found")
            return None

        # Await the async scan_tracker directly
        stats = await scan_tracker(db, tracker, since=since, force_update=force_update)
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


async def cleanup_tracker_webhooks(tracker_id: str):
    """
    Clean up webhooks when a tracker is deleted.

    This task:
    1. Finds all webhooks associated with projects/organizations under this tracker
    2. Deletes those webhook records from our database
    3. Checks if there are any other non-deleted trackers of the same type with the same URL
    4. If not, deletes the webhooks from the external tracker service

    Args:
        tracker_id: The ID of the deleted tracker
    """
    logger.info(f"Starting webhook cleanup for tracker {tracker_id}")

    db = next(get_db_session())
    try:
        from spacemodels.models.tracker import Tracker
        from spacemodels.models.webhook import Webhook
        from spacemodels.models.organization import Organization
        from spacemodels.models.project import Project
        from spacesync.spacesync.trackers import create_tracker_client

        # Get the deleted tracker (include deleted ones)
        tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
        if not tracker:
            logger.error(f"Tracker {tracker_id} not found for webhook cleanup")
            return

        logger.info(
            f"Cleaning up webhooks for tracker {tracker.name} (type: {tracker.tracker_type}, url: {tracker.url})"
        )

        # Find all organizations under this tracker
        organizations = (
            db.query(Organization).filter(Organization.tracker_id == tracker_id).all()
        )
        org_ids = [org.id for org in organizations]

        # Find all projects under this tracker (either directly or through organizations)
        projects = (
            db.query(Project)
            .filter(
                (Project.tracker_id == tracker_id)
                | (Project.organization_id.in_(org_ids) if org_ids else False)
            )
            .all()
        )
        project_ids = [proj.id for proj in projects]

        # Find all webhooks for these projects and organizations
        webhooks = (
            db.query(Webhook)
            .filter(
                (Webhook.project_id.in_(project_ids) if project_ids else False)
                | (Webhook.organization_id.in_(org_ids) if org_ids else False)
            )
            .all()
        )

        logger.info(
            f"Found {len(webhooks)} webhooks to clean up for tracker {tracker_id}"
        )

        # Check if there are other non-deleted trackers with same type and URL
        other_trackers = (
            db.query(Tracker)
            .filter(
                Tracker.tracker_type == tracker.tracker_type,
                Tracker.url == tracker.url,
                Tracker.id != tracker_id,
                Tracker.is_deleted.is_(False),
            )
            .all()
        )

        should_delete_external = len(other_trackers) == 0
        if should_delete_external:
            logger.info(
                "No other active trackers with same type/URL found. Will delete webhooks from external tracker."
            )
        else:
            logger.info(
                f"Found {len(other_trackers)} other active trackers with same type/URL. "
                f"Will not delete webhooks from external tracker."
            )

        # Delete webhooks from external tracker if needed
        if should_delete_external and webhooks:
            try:
                # Create a tracker client to delete webhooks
                client = await create_tracker_client(
                    tracker_type=tracker.tracker_type,
                    tracker_id=tracker_id,
                    api_key=tracker.api_key,
                    connection_details={
                        "url": tracker.url,
                        **(tracker.connection_details or {}),
                    },
                )

                for webhook in webhooks:
                    try:
                        if webhook.external_id:
                            await client.delete_webhook(webhook.external_id)
                            logger.info(
                                f"Deleted webhook {webhook.external_id} from external tracker"
                            )
                    except Exception as e:
                        logger.error(
                            f"Failed to delete webhook {webhook.external_id} from external tracker: {e}",
                            exc_info=True,
                        )
            except Exception as e:
                logger.error(
                    f"Failed to create tracker client for webhook cleanup: {e}",
                    exc_info=True,
                )

        # Delete webhook records from our database
        for webhook in webhooks:
            try:
                db.delete(webhook)
                logger.info(f"Deleted webhook record {webhook.id} from database")
            except Exception as e:
                logger.error(
                    f"Failed to delete webhook record {webhook.id}: {e}", exc_info=True
                )

        db.commit()
        logger.info(
            f"Webhook cleanup completed for tracker {tracker_id}. Deleted {len(webhooks)} webhooks."
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error during webhook cleanup for tracker {tracker_id}: {e}",
            exc_info=True,
        )
    finally:
        db.close()
