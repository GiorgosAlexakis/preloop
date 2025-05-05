"""
Tracker update service manager.
(Refactored for APScheduler integration)
"""

from typing import Optional, Set, List

import pytz
from datetime import datetime
from sqlalchemy.orm import Session
from apscheduler.schedulers.base import BaseScheduler # Import BaseScheduler for type hinting
from apscheduler.triggers.interval import IntervalTrigger # Import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError # Import specific error

from spacemodels.crud import crud_tracker
from spacemodels.db.session import get_db_session
from spacemodels.models import Organization, Project
from spacesync.scanner.core import TrackerClient
from ..exceptions import TrackerRateLimitError, TrackerError # Import necessary exceptions

from ..config import logger, SERVICE_POLL_INTERVAL # Import default interval


# Define a constant for the job ID prefix to easily identify tracker jobs
TRACKER_JOB_PREFIX = "tracker_update_"



def update_tracker(tracker_id: str):
    logger.info(f"Starting update poll for tracker {tracker_id}")
    total_embedding_updates = 0
    rate_limited_tracker = False # Flag to stop processing this tracker if rate limited

    # Each job run gets its own session using the generator pattern
    db: Optional[Session] = None
    session_generator = get_db_session()
    try:
        db = next(session_generator) # Get the session from the generator
        tracker = crud_tracker.get_by_id(db, id=tracker_id)
        if not tracker:
            logger.error(f"Tracker {tracker_id} not found in database.")
            return 0

        tracker_client = TrackerClient(tracker)

        # 1. Get organizations for this tracker from the API
        try:
            tracker_organizations: List[Organization] = tracker_client.scan_organizations(db)
            if not tracker_organizations:
                logger.info(f"No active organizations found for tracker {tracker_id}. Skipping update cycle.")
                return 0
        except Exception as e:
            logger.error(f"Failed to get organizations for tracker {tracker_id}: {e}", exc_info=True)
            return 0 # Cannot proceed without organizations

        # Process each organization
        for org in tracker_organizations:
            if rate_limited_tracker:
                logger.warning(f"Skipping remaining organizations for tracker {tracker_id} due to rate limit.")
                break # Stop processing orgs for this tracker if rate limited

            logger.debug(f"Processing organization {org.identifier} (ID: {org.id}) for tracker {tracker_id}")

            # 2. Scan Projects (fetches from API and reconciles with DB)
            processed_projects: List[Project] = []
            try:
                # Use the existing scan_projects method which handles API fetch and DB sync
                processed_projects = tracker_client.scan_projects(db=db, organization=org)
                logger.info(f"Successfully scanned/synchronized {len(processed_projects)} projects for org {org.identifier} (tracker {tracker_id}).")
            except TrackerRateLimitError as rle:
                logger.warning(f"Rate limit hit for tracker {tracker_id} during project scan for org {org.identifier}. Pausing updates for this tracker. Details: {rle}")
                rate_limited_tracker = True
                continue # Skip to next org (or break due to flag)
            except (TrackerError, NotImplementedError) as te:
                # Catch specific tracker errors or if scan_projects/get_projects isn't implemented
                logger.error(f"Tracker error scanning projects for org {org.identifier} (tracker {tracker_id}): {te}", exc_info=True)
                continue # Skip this org
            except Exception as e:
                logger.error(f"Unexpected error scanning projects for org {org.identifier} (tracker {tracker_id}): {e}", exc_info=True)
                continue # Skip this org

            # 3. Scan Issues for the synchronized projects returned by scan_projects
            logger.info(f"Scanning issues for {len(processed_projects)} projects in org {org.identifier} (tracker {tracker_id}).")
            for project in processed_projects:
                if rate_limited_tracker:
                    logger.warning(f"Skipping issue scan for project {project.identifier} due to rate limit.")
                    break # Stop processing projects for this org

                try:
                    # Scan issues for this synchronized project
                    # Note: scan_issues might also need error handling refinement
                    issues, embedding_updates = tracker_client.scan_issues(
                        db, org, project # Pass DB objects
                    )
                    total_embedding_updates += embedding_updates

                    if embedding_updates > 0:
                        logger.info(
                            f"Updated {embedding_updates} embeddings for project {project.id} ({project.name}) in tracker {tracker_id}"
                        )
                except TrackerRateLimitError as rle:
                    logger.warning(f"Rate limit hit for tracker {tracker_id} while scanning project {project.id}. Pausing updates for this tracker. Details: {rle}")
                    rate_limited_tracker = True # Set flag
                    break # Stop processing projects for this org
                except TrackerError as te:
                    logger.error(f"Tracker error scanning issues for project {project.id} (tracker {tracker_id}): {te}", exc_info=True)
                    continue # Continue with next project
                except Exception as e:
                    logger.error(f"Unexpected error scanning issues for project {project.id} (tracker {tracker_id}): {e}", exc_info=True)
                    continue # Continue with next project

        logger.info(f"Finished update poll for tracker {tracker_id}. Total embedding updates: {total_embedding_updates}. Rate limited: {rate_limited_tracker}")
        return 0 # Return 0 if tracker not found or other initial issues
    except StopIteration:
        logger.error(f"Failed to get database session from generator for tracker {tracker_id}.")
        return 0 # Failed to get session
    except Exception as e:
        logger.error(f"Error during tracker update for {tracker_id}: {e}", exc_info=True)
        return 0 # General error during update
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
