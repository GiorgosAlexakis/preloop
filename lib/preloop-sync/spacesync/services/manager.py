"""
Tracker update service manager.
(Refactored for APScheduler integration)
"""

from typing import Optional, Set, List

import pytz
from datetime import datetime, timedelta # Import timedelta
from sqlalchemy.orm import Session
from apscheduler.schedulers.base import BaseScheduler # Import BaseScheduler for type hinting
from apscheduler.triggers.interval import IntervalTrigger # Import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError # Import specific error

from spacemodels.crud import crud_tracker
from spacemodels.db.session import get_db_session
from spacemodels.models import Organization
from spacesync.scanner.core import TrackerClient, _process_organization # Import the helper
from ..exceptions import TrackerRateLimitError # Import necessary exceptions

from ..config import logger, SERVICE_POLL_INTERVAL # Import default interval

# Define the polling threshold (consistency with core.py)
# TODO: Make this configurable centrally
POLLING_THRESHOLD = timedelta(hours=1)


# Define a constant for the job ID prefix to easily identify tracker jobs
TRACKER_JOB_PREFIX = "tracker_update_"



def update_tracker(tracker_id: str):
    logger.info(f"Starting update poll for tracker {tracker_id}")
    # Initialize stats dictionary similar to scan_tracker
    stats = {
        "organizations_scanned": 0,
        "organizations_skipped_webhook": 0,
        "organizations_skipped_polling": 0,
        "projects": 0,
        "issues": 0,
        "embeddings_updated": 0,
        "errors": 0,
    }
    rate_limited_tracker = False # Flag to stop processing this tracker if rate limited

    # Each job run gets its own session using the generator pattern
    db: Optional[Session] = None
    session_generator = get_db_session()
    try:
        db = next(session_generator) # Get the session from the generator
        tracker = crud_tracker.get_by_id(db, id=tracker_id)
        if not tracker:
            logger.error(f"Tracker {tracker_id} not found in database.")
            return stats # Return empty stats

        tracker_client = TrackerClient(tracker)
        # Use epoch time (Jan 1, 1970) to effectively scan all issues when polling
        # This matches the behavior in the original scan_tracker before refactoring
        since = datetime(1970, 1, 1)
        # Force update is false by default for scheduled jobs
        force_update = False

        # 1. Get organizations for this tracker from the API
        try:
            tracker_organizations: List[Organization] = tracker_client.scan_organizations(db)
            if not tracker_organizations:
                logger.info(f"No active organizations found for tracker {tracker_id}. Skipping update cycle.")
                return stats # Return empty stats
        except TrackerRateLimitError as rle:
             logger.warning(f"Rate limit hit for tracker {tracker_id} during organization scan. Pausing updates for this tracker. Details: {rle}")
             rate_limited_tracker = True
             tracker_organizations = [] # Ensure loop doesn't run
             stats["errors"] += 1
        except Exception as e:
            logger.error(f"Failed to get organizations for tracker {tracker_id}: {e}", exc_info=True)
            return stats # Return empty stats with error count potentially incremented

        # Process each organization using the helper function from core.py
        for org in tracker_organizations:
            if rate_limited_tracker:
                logger.warning(f"Skipping remaining organizations for tracker {tracker_id} due to prior rate limit.")
                break # Stop processing orgs for this tracker if rate limited

            try:
                # Call the centralized processing function
                org_stats, skipped = _process_organization(
                    db=db,
                    client=tracker_client,
                    org=org,
                    since=since,
                    force_update=force_update,
                    polling_threshold=POLLING_THRESHOLD,
                )

                # Aggregate stats
                if skipped:
                    # Increment appropriate skipped counter based on current org state
                    now = datetime.utcnow() # Re-check time
                    if org.last_webhook_update and (now - org.last_webhook_update) < POLLING_THRESHOLD:
                         stats["organizations_skipped_webhook"] += 1
                    elif org.last_polling_update and (now - org.last_polling_update) < POLLING_THRESHOLD:
                         stats["organizations_skipped_polling"] += 1
                else:
                    stats["organizations_scanned"] += 1
                    stats["projects"] += org_stats["projects"]
                    stats["issues"] += org_stats["issues"]
                    stats["embeddings_updated"] += org_stats["embeddings_updated"]
                    stats["errors"] += org_stats["errors"]

            except TrackerRateLimitError as rle:
                 # Catch rate limit errors that might occur within _process_organization
                 # (e.g., during project or issue scanning)
                 logger.warning(f"Rate limit hit for tracker {tracker_id} while processing org {org.identifier}. Pausing updates. Details: {rle}")
                 rate_limited_tracker = True
                 stats["errors"] += 1
                 # Don't 'continue' here, let the rate_limited_tracker flag handle skipping subsequent orgs
            except Exception as e:
                 # Catch unexpected errors during the processing of a single organization
                 logger.error(f"Unexpected error processing organization {org.identifier} for tracker {tracker_id}: {e}", exc_info=True)
                 stats["errors"] += 1
                 # Continue to the next organization even if one fails unexpectedly

        logger.info(f"Finished update poll for tracker {tracker_id}. Stats: {stats}. Rate limited encountered: {rate_limited_tracker}")
        return stats # Return the collected statistics
    except StopIteration:
        logger.error(f"Failed to get database session from generator for tracker {tracker_id}.")
        stats["errors"] += 1
        return stats # Return stats indicating error
    except Exception as e:
        logger.error(f"Error during tracker update job for {tracker_id}: {e}", exc_info=True)
        stats["errors"] += 1
        return stats # Return stats indicating error
    finally:
        # Ensure the session is closed if it was successfully obtained
        if db:
            try:
                db.close()
                logger.debug(f"Closed DB session for tracker {tracker_id}")
            except Exception as close_exc:
                logger.error(f"Error closing DB session for tracker {tracker_id}: {close_exc}")

# --- APScheduler Job Synchronization Function ---

def sync_scheduled_jobs(scheduler: BaseScheduler, db: Session):
    """
    Synchronizes APScheduler jobs with active trackers in the database.

    This function should be called periodically by a dedicated APScheduler job.

    Args:
        scheduler: The APScheduler instance.
        manager: The TrackerUpdateServiceManager instance (provides DB session and service management).
    """
    logger.info("Starting tracker job synchronization...")
    # Acquire a new DB session specifically for this job run
    db = next(get_db_session())
    try:
        # 1. Get current tracker job IDs from scheduler
        current_job_ids: Set[str] = set()
        for job in scheduler.get_jobs():
            if job.id.startswith(TRACKER_JOB_PREFIX):
                # Extract tracker ID from job ID
                current_job_ids.add(job.id.replace(TRACKER_JOB_PREFIX, "", 1))

        # 2. Fetch all *active* trackers from the database using the local session
        active_trackers = crud_tracker.get_active(db)
        active_tracker_ids: Set[str] = {str(t.id) for t in active_trackers}
        logger.info(f"Found {len(active_trackers)} active trackers in DB: {active_tracker_ids}") # Changed to INFO
        logger.info(f"Found {len(current_job_ids)} existing tracker jobs in scheduler: {current_job_ids}") # Changed to INFO

        # 3. Identify trackers needing new jobs
        trackers_to_add = {tid for tid in active_tracker_ids if tid not in current_job_ids}
        logger.debug(f"Trackers to add jobs for: {trackers_to_add}")

        # 4. Identify jobs to remove (for deactivated trackers)
        jobs_to_remove = {jid for jid in current_job_ids if jid not in active_tracker_ids}
        logger.info(f"Trackers needing job removal: {jobs_to_remove}") # Changed to INFO

        # 5. Remove jobs for deactivated trackers
        for tracker_id in jobs_to_remove:
            job_id = f"{TRACKER_JOB_PREFIX}{tracker_id}"
            try:
                scheduler.remove_job(job_id)
                logger.info(f"Removed job {job_id} for deactivated tracker {tracker_id}.")
            except JobLookupError:
                 logger.warning(f"Job {job_id} not found in scheduler, likely already removed.")
            except Exception as e:
                logger.error(f"Error removing job {job_id}: {e}")


        # 6. Add jobs for new active trackers
        for tracker_id in trackers_to_add:
            logger.info(f"Processing tracker to add job for: {tracker_id}")
            # Find the tracker object
            tracker = next((t for t in active_trackers if str(t.id) == tracker_id), None)
            if not tracker:
                logger.error(f"Could not find tracker object for ID {tracker_id} during job add.")
                continue

            scheduler.add_job(
                update_tracker,
                id=f"{TRACKER_JOB_PREFIX}{tracker_id}",
                name=f"Update Tracker {tracker_id}",
                replace_existing=True,
                misfire_grace_time=60,
                args=[tracker_id], # Only pass tracker_id, job will get its own session
                trigger=IntervalTrigger(seconds=SERVICE_POLL_INTERVAL),
                next_run_time=datetime.now(pytz.utc),
            )
            logger.info(f"Added job for tracker {tracker_id} with interval {SERVICE_POLL_INTERVAL} seconds.")

        logger.info("Tracker job synchronization complete.")

    except Exception as e:
        logger.error(f"Error during tracker job synchronization: {e}", exc_info=True)
    finally:
        # Ensure the locally acquired DB session is closed
        if db:
            try:
                db.close()
                logger.debug("Closed DB session for job synchronization.")
            except Exception as e:
                logger.error(f"Error closing DB session in job synchronization: {e}")
