#!/usr/bin/env python
"""
Script to run the SpaceSync tracker update service using APScheduler.
"""

import argparse
import logging
import sys
import time
from pathlib import Path
import atexit
from datetime import datetime  # Import datetime

# Add project root to path
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent)
)  # Go up two levels to reach project root

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.interval import IntervalTrigger  # Import IntervalTrigger

from spacemodels.db.session import get_db_session
from spacesync.config import logger

# Import the sync function and the manager
from spacesync.services.manager import TrackerUpdateServiceManager, sync_scheduled_jobs


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the SpaceSync tracker update service."
    )
    parser.add_argument(
        "--foreground", action="store_true", help="Run in foreground (don't daemonize)"
    )
    parser.add_argument(
        "--reload-interval",
        type=int,
        default=90,
        help="Interval (in seconds) to reload tracker list and schedule jobs",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Maximum number of concurrent update jobs",
    )

    return parser.parse_args()


def setup_logging(log_level):
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# Global scheduler instance
scheduler = None


def shutdown_scheduler():
    """Function to shut down the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        logger.info("Shutting down scheduler...")
        try:
            # Wait=False allows atexit to proceed without blocking on job completion
            scheduler.shutdown(wait=False)
            logger.info("Scheduler shutdown initiated.")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")


def main():
    """Run the service."""
    global scheduler
    # Parse command line arguments
    args = parse_args()

    # Set up logging
    setup_logging(args.log_level)

    # Create database session (will be passed to manager and sync job)
    # Ensure the session remains open while the scheduler runs
    db = next(get_db_session())

    # Configure scheduler executor
    executors = {"default": ThreadPoolExecutor(args.max_workers)}
    job_defaults = {
        "coalesce": False,  # Run jobs even if previous run is pending
        "max_instances": 1,  # Default max instances per job (can be overridden)
    }

    # Initialize the scheduler
    scheduler = BackgroundScheduler(
        executors=executors, job_defaults=job_defaults, timezone="UTC"
    )

    # Register shutdown hook
    atexit.register(shutdown_scheduler)

    # Create service manager (passing scheduler and db session)
    # The manager now primarily holds state and service instances
    manager = TrackerUpdateServiceManager(
        db=db, scheduler=scheduler, reload_interval=args.reload_interval
    )
    manager.running = True  # Mark manager as running conceptually

    try:
        # Add the recurring job to sync tracker jobs
        scheduler.add_job(
            sync_scheduled_jobs,
            trigger=IntervalTrigger(seconds=args.reload_interval),
            args=[scheduler, manager],  # Pass scheduler and manager instances
            id="tracker_reload_job",
            name="Sync Tracker Jobs",
            replace_existing=True,
            misfire_grace_time=60,  # Allow 1 minute grace time
            next_run_time=datetime.now(),  # Run immediately on start
        )
        logger.info(
            f"Scheduled tracker job synchronization every {args.reload_interval} seconds."
        )

        # Start the scheduler
        scheduler.start()
        logger.info(f"APScheduler started with max_workers={args.max_workers}")

        # manager.start() is no longer needed for scheduling

        logger.info("SpaceSync service started with APScheduler")

        # Keep main thread alive if running in foreground
        if args.foreground:
            while True:  # Keep running until interrupted
                time.sleep(1)
        else:
            # In background mode, the scheduler thread keeps the process alive
            while True:
                time.sleep(3600)  # Sleep for a long time

    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received, stopping service...")
        # The atexit handler will call shutdown_scheduler()

    finally:
        # Manager cleanup (stopping service instances)
        if manager and manager.running:
            manager.stop()
        # Explicitly close DB session if manager didn't (or if it's still open)
        if db:
            try:
                # Check if session is still active before closing
                if not db.is_closed:
                    db.close()
                    logger.info("Database session closed.")
            except Exception as e:
                logger.error(f"Error closing database session: {e}")


if __name__ == "__main__":
    sys.exit(main())
