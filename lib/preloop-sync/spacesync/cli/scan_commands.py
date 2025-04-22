"""
Scan commands for SpaceSync CLI.
"""

import click
import time
import logging
import atexit
import signal # Import signal

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.interval import IntervalTrigger

from spacemodels.crud import crud_account, crud_tracker
from spacemodels.db.session import get_db_session

# Import scanner functions for other commands
from ..scanner import scan_account
from ..scanner import scan_tracker as scan_tracker_func

# Import service components for the 'scan all' (now service start) command
from ..services.manager import TrackerUpdateServiceManager, sync_scheduled_jobs
from ..config import logger # Use the configured logger
from ..utils import safe_exit


# --- Scheduler Setup ---
# Global scheduler instance for the 'scan all' command
scheduler = None

def shutdown_scheduler():
    """Function to shut down the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        logger.info("Shutting down scheduler...")
        try:
            scheduler.shutdown(wait=False) # Use wait=False for atexit
            logger.info("Scheduler shut down successfully.")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")

# Register the shutdown hook globally for the CLI process
atexit.register(shutdown_scheduler)

# --- Signal Handling for Graceful Shutdown ---
keep_running = True
def handle_shutdown_signal(sig, frame):
    """Sets the flag to stop the main loop."""
    global keep_running
    logger.info(f"Received signal {sig}, initiating shutdown...")
    keep_running = False

signal.signal(signal.SIGINT, handle_shutdown_signal)
signal.signal(signal.SIGTERM, handle_shutdown_signal)
# --- End Signal Handling ---


@click.group()
def scan():
    """
    Commands for scanning issue trackers or starting the continuous sync service.
    """
    pass


@scan.command(name="all")
@click.option(
    "--reload-interval",
    type=int,
    default=90,
    help="Interval (in seconds) to reload tracker list and sync jobs.",
    show_default=True,
)
@click.option(
    "--max-workers",
    type=int,
    default=10,
    help="Maximum number of concurrent tracker update jobs.",
    show_default=True,
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="INFO",
    help="Set the logging level.",
    show_default=True,
)
def scan_all(reload_interval: int, max_workers: int, log_level: str):
    """
    Start the continuous SpaceSync service in the foreground.

    This service periodically checks for active trackers and schedules
    background jobs to scan them for updates based on their configured intervals.
    Press Ctrl+C to stop the service.
    """
    global scheduler
    # Set up logging level based on command option
    logging.getLogger("spacesync").setLevel(getattr(logging, log_level.upper()))
    # Configure root logger for APScheduler logs etc.
    logging.basicConfig(level=getattr(logging, log_level.upper()), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


    click.echo(f"Starting SpaceSync service in foreground (reload interval: {reload_interval}s, max workers: {max_workers})...")
    click.echo("Press Ctrl+C to stop.")

    # Get database session (ensure it stays open for the service duration)
    # Note: The session created here is primarily for the manager initialization.
    # The sync_scheduled_jobs function now creates its own session per run.
    db = next(get_db_session())

    # Configure scheduler executor
    executors = {
        'default': ThreadPoolExecutor(max_workers)
    }
    job_defaults = {
        'coalesce': False,
        'max_instances': 1
    }

    # Initialize the scheduler
    scheduler = BackgroundScheduler(executors=executors, job_defaults=job_defaults, timezone="UTC")

    # Create service manager instance (needed by sync_scheduled_jobs)
    manager = TrackerUpdateServiceManager(db=db, scheduler=scheduler, reload_interval=reload_interval)
    manager.running = True # Mark manager as conceptually running

    try:
        # Add the recurring job to sync tracker jobs
        # Run it once immediately, then schedule subsequent runs
        scheduler.add_job(
            sync_scheduled_jobs,
            trigger=IntervalTrigger(seconds=reload_interval),
            args=[scheduler, manager],
            id='tracker_reload_job',
            name='Sync Tracker Jobs',
            replace_existing=True,
            misfire_grace_time=60,
            # next_run_time=datetime.now() # Removed: Will run immediately after start + initial call
        )
        logger.info(f"Scheduled tracker job synchronization every {reload_interval} seconds.")

        # Start the scheduler
        scheduler.start()
        logger.info(f"APScheduler started with max_workers={max_workers}")

        # Manually trigger the first sync immediately after starting scheduler
        logger.info("Triggering initial tracker job synchronization...")
        sync_scheduled_jobs(scheduler, manager)

        # Keep main thread alive while the scheduler runs in the background.
        # Exit loop when keep_running flag is set by signal handler.
        while keep_running:
            time.sleep(1)

        # No need for explicit except KeyboardInterrupt/SystemExit here,
        # the signal handler sets the flag, the loop exits, and finally runs.
        logger.info("Main loop exited.")

    finally:
        # Cleanup manager resources
        if manager and manager.running:
             manager.stop()
        # Close DB session initially created for the manager
        # Use db.is_active check instead of is_closed
        if db and db.is_active:
            try:
                db.close()
                logger.info("Initial database session closed.")
            except Exception as e:
                logger.error(f"Error closing initial database session: {e}")
        click.echo("SpaceSync service stopped.")


@scan.command(name="account")
@click.argument("account_id", type=str)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--force-update",
    "-f",
    is_flag=True,
    help="Force update of all embeddings even if content hasn't changed",
)
def scan_account_cmd(account_id: str, verbose: bool, force_update: bool):
    """
    Perform a ONE-OFF scan for a specific account and all its trackers.
    Does NOT start the continuous service.

    ACCOUNT_ID: The ID of the account to scan (UUID string).
    """
    # Get database session
    db = next(get_db_session())

    # Check if account exists
    account = crud_account.get(db, id=account_id)
    if not account:
        safe_exit(1, f"Account with ID {account_id} not found")

    click.echo(f"Scanning account: {account.username} (ID: {account.id})...")

    # Scan the account (pass force_update)
    stats = scan_account(db, account_id, verbose, force_update) # Pass force_update

    # Print summary
    click.echo("\n=== Scan Complete ===")
    click.echo(f"Trackers scanned: {stats['trackers_scanned']}")
    click.echo(f"Trackers with errors: {stats['trackers_with_errors']}")
    click.echo(f"Total organizations: {stats['organizations']}")
    click.echo(f"Total projects: {stats['projects']}")
    click.echo(f"Total issues: {stats['issues']}")
    click.echo(f"Total embeddings updated: {stats['embeddings_updated']}")
    click.echo(f"Total duration: {stats['duration_seconds']:.2f} seconds")

    db.close()


@scan.command(name="tracker")
@click.argument("tracker_id", type=str)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--force-update",
    "-f",
    is_flag=True,
    help="Force update of all embeddings even if content hasn't changed",
)
def scan_tracker_cmd(tracker_id: str, verbose: bool, force_update: bool):
    """
    Perform a ONE-OFF scan for a specific tracker.
    Does NOT start the continuous service.

    TRACKER_ID: The ID of the tracker to scan (UUID string).
    """
    # Get database session
    db = next(get_db_session())

    # Check if tracker exists
    tracker = crud_tracker.get(db, id=tracker_id)
    if not tracker:
        safe_exit(1, f"Tracker with ID {tracker_id} not found")

    click.echo(f"Scanning tracker: ID {tracker.id} ({tracker.tracker_type})...")

    # Scan the tracker (pass force_update)
    stats = scan_tracker_func(db, tracker, verbose, force_update) # Pass force_update

    # Print summary
    click.echo("\n=== Scan Complete ===")
    click.echo(f"Organizations: {stats['organizations']}")
    click.echo(f"Projects: {stats['projects']}")
    click.echo(f"Issues: {stats['issues']}")
    click.echo(f"Embeddings updated: {stats['embeddings_updated']}")
    click.echo(f"Errors: {stats['errors']}")
    click.echo(f"Duration: {stats['duration_seconds']:.2f} seconds")

    db.close()
