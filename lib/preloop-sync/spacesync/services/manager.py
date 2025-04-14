"""
Tracker update service manager.
"""

import signal
import threading
import time
from typing import Dict

from sqlalchemy.orm import Session

from spacemodels.crud import crud_tracker
from spacemodels.db.session import get_db_session
from spacemodels.models import Tracker

from ..config import logger
from .base import BaseTrackerUpdateService, TrackerUpdateServiceFactory


class TrackerUpdateServiceManager:
    """
    Manager for tracker update services.

    This class is responsible for creating, starting, and stopping
    tracker update services for all active trackers.
    """

    def __init__(
        self, db: Session = None, max_workers: int = 10, reload_interval: int = 300
    ):
        """
        Initialize the tracker update service manager.

        Args:
            db: Database session (if None, will create one)
            max_workers: Maximum number of concurrent tracker services
        """
        self.db = db or next(get_db_session())
        self.max_workers = max_workers
        self.services: Dict[str, BaseTrackerUpdateService] = {}
        self.running = False
        self.reload_interval = reload_interval  # Reload tracker list periodically
        self.reload_thread = None

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Handle signals to gracefully shut down."""
        logger.info(f"Received signal {sig}, shutting down...")
        self.stop()

    def start(self):
        """Start all tracker update services."""
        if self.running:
            logger.warning("Tracker update service manager already running")
            return

        self.running = True
        logger.info("Starting tracker update service manager")

        # Start all services for active trackers
        self._init_services()

        # Start reload thread
        self.reload_thread = threading.Thread(target=self._reload_loop)
        self.reload_thread.daemon = True
        self.reload_thread.start()

    def stop(self):
        """Stop all tracker update services."""
        if not self.running:
            logger.warning("Tracker update service manager not running")
            return

        self.running = False
        logger.info("Stopping tracker update service manager")

        # Stop all services
        for tracker_id, _ in list(self.services.items()):
            self._stop_service(tracker_id)

        # Wait for reload thread to stop
        if self.reload_thread and self.reload_thread.is_alive():
            self.reload_thread.join(timeout=5.0)

        # Close DB session
        if self.db:
            self.db.close()
            self.db = None

    def _init_services(self):
        """Initialize services for all active trackers."""
        # Get all active trackers
        active_trackers = crud_tracker.get_active(self.db)
        logger.info(f"Found {len(active_trackers)} active trackers")

        # Create and start services for each tracker
        for tracker in active_trackers:
            self._start_service(tracker)

    def _start_service(self, tracker: Tracker):
        """
        Start a service for a tracker.

        Args:
            tracker: Tracker model
        """
        tracker_id = str(tracker.id)

        # Skip if service already exists
        if tracker_id in self.services:
            logger.info(f"Service for tracker {tracker_id} already running")
            return

        # Create service
        service = TrackerUpdateServiceFactory.create_service(self.db, tracker)

        # Set up service
        if service.setup():
            # Start service
            service.start()
            self.services[tracker_id] = service
            logger.info(f"Started service for tracker {tracker_id} ({tracker.name})")
        else:
            logger.error(
                f"Failed to set up service for tracker {tracker_id} ({tracker.name})"
            )

    def _stop_service(self, tracker_id: str):
        """
        Stop a service for a tracker.

        Args:
            tracker_id: Tracker ID
        """
        if tracker_id not in self.services:
            logger.warning(f"Service for tracker {tracker_id} not found")
            return

        service = self.services[tracker_id]
        service.stop()
        logger.info(f"Stopped service for tracker {tracker_id}")

        # Remove from services dict
        del self.services[tracker_id]

    def _reload_loop(self):
        """
        Reload tracker list periodically.

        This ensures that new trackers are added and deleted trackers are removed.
        """
        logger.info("Starting tracker reload loop")

        while self.running:
            # Sleep first to avoid double initialization at startup
            for _ in range(self.reload_interval):
                if not self.running:
                    break
                time.sleep(1)

            if not self.running:
                break

            logger.info("Reloading tracker list")

            # Get all active trackers
            active_trackers = crud_tracker.get_active(self.db)
            active_tracker_ids = {str(t.id) for t in active_trackers}

            # Find services to stop (trackers that are no longer active)
            for tracker_id in list(self.services.keys()):
                if tracker_id not in active_tracker_ids:
                    logger.info(
                        f"Tracker {tracker_id} is no longer active, stopping service"
                    )
                    self._stop_service(tracker_id)

            # Find trackers to start (new active trackers)
            for tracker in active_trackers:
                tracker_id = str(tracker.id)
                if tracker_id not in self.services:
                    logger.info(
                        f"Found new active tracker {tracker_id}, starting service"
                    )
                    self._start_service(tracker)

            logger.info(f"Reload complete, {len(self.services)} services running")


def run_service_manager():
    """Run the tracker update service manager."""
    # Create database session
    db = next(get_db_session())

    try:
        # Create and start service manager
        manager = TrackerUpdateServiceManager(db)
        manager.start()

        # Keep main thread alive
        while manager.running:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")

    finally:
        # Clean up
        db.close()


if __name__ == "__main__":
    run_service_manager()
