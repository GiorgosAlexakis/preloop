import click
import time
import logging
import atexit
import signal  # Import signal
import pytz
from datetime import datetime  # Import datetime


from spacemodels.db.session import get_db_session
from ..services.manager import sync_scheduled_jobs


from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.interval import IntervalTrigger
from ..config import logger


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

# --- Scheduler Setup ---
# Global scheduler instance
scheduler = None


def shutdown_scheduler():
    """Function to shut down the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        logger.info("Shutting down scheduler...")
        try:
            scheduler.shutdown(wait=False)  # Use wait=False for atexit
            logger.info("Scheduler shut down successfully.")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")


# Register the shutdown hook globally for the CLI process
atexit.register(shutdown_scheduler)


@click.option(
    "--reload-interval",
    type=int,
    default=60,
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
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
    help="Set the logging level.",
    show_default=True,
)
@click.command(name="scheduler")
def scheduler_cmd(reload_interval: int, max_workers: int, log_level: str):
    """
    Start the SpaceSync scheduler service in the foreground.

    This service periodically checks for active trackers and schedules
    background jobs to scan them for updates based on their configured intervals.
    Press Ctrl+C to stop the service.
    """
    global scheduler
    # Set up logging level based on command option
    logging.getLogger("spacesync").setLevel(getattr(logging, log_level.upper()))
    # Configure root logger for APScheduler logs etc.
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    click.echo(
        f"Starting SpaceSync scheduler service in foreground (reload interval: {reload_interval}s, max workers: {max_workers})..."
    )
    click.echo("Press Ctrl+C to stop.")

    # Get database session (ensure it stays open for the service duration)
    # Note: The session created here is primarily for the manager initialization.
    # The sync_scheduled_jobs function now creates its own session per run.
    db = next(get_db_session())

    # Configure scheduler executor
    executors = {"default": ThreadPoolExecutor(max_workers)}
    job_defaults = {"coalesce": False, "max_instances": 1}

    # Initialize the scheduler
    scheduler = BackgroundScheduler(
        executors=executors, job_defaults=job_defaults, timezone="UTC"
    )

    try:
        # Start the scheduler
        scheduler.start()
        logger.info(f"APScheduler started with max_workers={max_workers}")

        # Add the recurring job to sync tracker jobs
        # Run it once immediately, then schedule subsequent runs
        scheduler.add_job(
            sync_scheduled_jobs,
            trigger=IntervalTrigger(seconds=reload_interval),
            args=[scheduler, db],
            id="tracker_reload_job",
            name="Sync Tracker Jobs",
            replace_existing=True,
            misfire_grace_time=60,
            next_run_time=datetime.now(pytz.utc),
        )
        logger.info(
            f"Scheduled tracker job synchronization every {reload_interval} seconds."
        )

        # Keep main thread alive while the scheduler runs in the background.
        # Exit loop when keep_running flag is set by signal handler.
        while keep_running:
            time.sleep(1)

        # No need for explicit except KeyboardInterrupt/SystemExit here,
        # the signal handler sets the flag, the loop exits, and finally runs.
        logger.info("Main loop exited.")

    finally:
        # Explicitly attempt scheduler shutdown here
        shutdown_scheduler()

        # Close DB session
        # Use db.is_active check instead of is_closed
        if db and db.is_active:
            try:
                db.close()
                logger.info("Initial database session closed.")
            except Exception as e:
                logger.error(f"Error closing initial database session: {e}")
        click.echo("SpaceSync scheduler service stopped.")
