"""
Tracker update service manager.
(Refactored for APScheduler integration)
"""

import signal
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session
from apscheduler.schedulers.base import BaseScheduler # Import BaseScheduler for type hinting
from apscheduler.triggers.interval import IntervalTrigger # Import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError # Import specific error

from spacemodels.crud import crud_tracker
from spacemodels.db.session import get_db_session
from spacemodels.models import Tracker

from ..config import logger, SERVICE_POLL_INTERVAL # Import default interval
from .base import BaseTrackerUpdateService, TrackerUpdateServiceFactory


# Define a constant for the job ID prefix to easily identify tracker jobs
TRACKER_JOB_PREFIX = "tracker_update_"

class TrackerUpdateServiceManager:
    """
    Manager for tracker update services.

    This class is now primarily responsible for holding references to service
    instances, but the scheduling and lifecycle management of the update *jobs*
    are handled by an external APScheduler instance.
    """

    def __init__(
        self, db: Session = None, scheduler: Optional[BaseScheduler] = None, reload_interval: int = 90
    ):
        """
        Initialize the tracker update service manager.

        Args:
            db: Database session (if None, will create one).
            scheduler: The APScheduler instance managing the jobs.
            reload_interval: Interval (in seconds) for the external reload job.
        """
        self.db = db or next(get_db_session())
        self.scheduler = scheduler # Store scheduler reference
        self.services: Dict[str, BaseTrackerUpdateService] = {} # Still holds service instances
        self.running = False
        self.reload_interval = reload_interval # Informational

        # Signal handling remains relevant for graceful shutdown of the process
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Handle signals to gracefully shut down."""
        logger.info(f"Received signal {sig}, initiating shutdown...")
        self.stop()
        # The actual scheduler shutdown is handled by atexit in run_service.py

    def start(self):
        """Marks the manager as running. Actual job scheduling is external."""
        if self.running:
            logger.warning("Tracker update service manager already marked as running")
            return

        self.running = True
        logger.info("Tracker update service manager started (scheduling handled by APScheduler).")
        # No longer starts _init_services or _reload_loop here

    def stop(self):
        """Marks the manager as stopped and cleans up service instances."""
        if not self.running:
            logger.warning("Tracker update service manager already marked as stopped")
            return

        self.running = False
        logger.info("Stopping tracker update service manager...")

        # Stop and cleanup all managed service instances
        # The corresponding scheduler jobs should be removed by the sync_scheduled_jobs function
        # or by the scheduler shutdown process itself.
        for tracker_id in list(self.services.keys()):
            self._stop_service_instance(tracker_id) # Renamed to avoid confusion with job stopping

        # No longer responsible for stopping threads or closing DB session here
        logger.info("Tracker update service manager stopped.")


    # Removed _init_services method

    def create_and_setup_service(self, tracker: Tracker) -> Optional[BaseTrackerUpdateService]:
        """
        Creates and sets up a service instance for a tracker.
        Does not start execution (scheduling is external).

        Args:
            tracker: Tracker model

        Returns:
            The created and setup service instance, or None if setup failed.
        """
        tracker_id = str(tracker.id)
        if tracker_id in self.services:
            logger.debug(f"Service instance for tracker {tracker_id} already exists.")
            # Return the existing instance
            return self.services[tracker_id]

        try:
            # Create service instance
            # Pass the DB session from the manager
            service = TrackerUpdateServiceFactory.create_service(self.db, tracker)

            # Set up service (e.g., register webhooks if applicable)
            if service.setup():
                self.services[tracker_id] = service
                logger.info(f"Created and set up service instance for tracker {tracker_id} ({tracker.name})")
                return service
            else:
                logger.error(
                    f"Failed to set up service instance for tracker {tracker_id} ({tracker.name})"
                )
                # Clean up partially created service if setup failed
                if tracker_id in self.services:
                    del self.services[tracker_id]
                return None
        except Exception as e:
            logger.error(f"Error creating service instance for tracker {tracker_id}: {e}", exc_info=True)
            return None

    def _stop_service_instance(self, tracker_id: str):
        """
        Stops and cleans up a service instance.
        Does not interact with the scheduler.

        Args:
            tracker_id: Tracker ID
        """
        if tracker_id not in self.services:
            logger.warning(f"Service instance for tracker {tracker_id} not found for stopping.")
            return

        service = self.services[tracker_id]
        try:
            service.stop() # Calls cleanup internally
            logger.info(f"Stopped and cleaned up service instance for tracker {tracker_id}")
        except Exception as e:
             logger.error(f"Error stopping service instance for tracker {tracker_id}: {e}", exc_info=True)
        finally:
            # Remove from managed services dict
            if tracker_id in self.services:
                del self.services[tracker_id]

    # Removed _reload_loop method


# --- APScheduler Job Synchronization Function ---

def sync_scheduled_jobs(scheduler: BaseScheduler, manager: TrackerUpdateServiceManager):
    """
    Synchronizes APScheduler jobs with active trackers in the database.

    This function should be called periodically by a dedicated APScheduler job.

    Args:
        scheduler: The APScheduler instance.
        manager: The TrackerUpdateServiceManager instance (provides DB session and service management).
    """
    logger.info("Starting tracker job synchronization...")
    # Acquire a new DB session specifically for this job run
    db: Optional[Session] = None
    try:
        db = next(get_db_session())
        logger.debug("Acquired new DB session for job synchronization.")

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
            finally:
                 # Also stop and cleanup the service instance if it exists
                 manager._stop_service_instance(tracker_id)


        # 6. Add jobs for new active trackers
        for tracker_id in trackers_to_add:
            logger.info(f"Processing tracker to add job for: {tracker_id}")
            # Find the tracker object
            tracker = next((t for t in active_trackers if str(t.id) == tracker_id), None)
            if not tracker:
                logger.error(f"Could not find tracker object for ID {tracker_id} during job add.")
                continue

            # Create or get the service instance (handles setup)
            # Pass the local db session to the factory/service constructor
            # We need to modify create_and_setup_service or call factory directly
            # Let's call factory directly for simplicity here
            service = None # Initialize service to None
            try:
                logger.debug(f"Attempting to create service for tracker {tracker_id}...")
                service = TrackerUpdateServiceFactory.create_service(db, tracker)
                logger.debug(f"Service created for tracker {tracker_id}. Attempting setup...")
                if not service.setup():
                    logger.error(f"Setup failed for service instance for tracker {tracker_id} ({tracker.name})")
                    service = None # Ensure service is None if setup failed
                    continue # Skip adding job if setup fails
                logger.info(f"Service setup successful for tracker {tracker_id}.")
                # Store the successfully setup service instance in the manager
                # This allows cleanup later if needed, e.g., for webhooks
                manager.services[tracker_id] = service
                logger.info(f"Created and set up service instance for tracker {tracker_id} ({tracker.name})")

            except Exception as e:
                logger.error(f"Error creating/setting up service instance for tracker {tracker_id}: {e}", exc_info=True)
                continue # Skip adding job if creation/setup fails


            # Since the factory now only returns PollingTrackerUpdateService or raises error,
            # and setup success is checked, we proceed if service is not None.
            if service:
                job_id = f"{TRACKER_JOB_PREFIX}{tracker_id}"
                # Determine interval: Check tracker metadata first, then service default, then global default
                interval_seconds = SERVICE_POLL_INTERVAL # Start with global default
                if tracker.meta_data and isinstance(tracker.meta_data.get('poll_interval_seconds'), int):
                    interval_seconds = tracker.meta_data['poll_interval_seconds']
                    logger.debug(f"Using custom interval {interval_seconds}s from metadata for tracker {tracker_id}")
                elif hasattr(service, 'poll_interval') and service.poll_interval:
                     interval_seconds = service.poll_interval
                     logger.debug(f"Using interval {interval_seconds}s from service config for tracker {tracker_id}")
                else:
                     logger.debug(f"Using global default interval {interval_seconds}s for tracker {tracker_id}")

                # Ensure interval is reasonable (e.g., not less than 60 seconds)
                interval_seconds = max(60, interval_seconds)

                trigger = IntervalTrigger(seconds=interval_seconds, jitter=30) # Add jitter

                try:
                    logger.info(f"Attempting to add job {job_id} to scheduler...")
                    # Pass the service instance's update method
                    # The service instance holds its own reference to the DB session created above
                    scheduler.add_job(
                        service.update,
                        trigger=trigger,
                        args=[], # Pass any required args to service.update here if needed
                        id=job_id,
                        name=f"Update_{tracker.name}_{tracker_id[:8]}",
                        replace_existing=True, # Replace if job somehow exists but wasn't tracked
                        max_instances=1 # Ensure only one run at a time per tracker (Iteration 3)
                    )
                    logger.info(f"Added/Updated job {job_id} for tracker {tracker_id} with interval {interval_seconds}s.")
                except Exception as e:
                    logger.error(f"Error adding/updating job {job_id}: {e}")
            # No need for elif/else here:
            # - If service is None, it means creation/setup failed and was logged earlier.
            # - If service exists, it's guaranteed to be PollingTrackerUpdateService by the factory.

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


# The run_service_manager function might need adjustment or removal
# depending on how run_service.py orchestrates things now.
# Keeping it commented out for now.
# def run_service_manager():
#     """Run the tracker update service manager."""
#     # This function's logic is largely moved to run_service.py's main()
#     pass

# if __name__ == "__main__":
#     # This entry point is likely not needed anymore as run_service.py is the main script
#     pass
