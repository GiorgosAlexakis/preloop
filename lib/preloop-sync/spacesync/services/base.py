"""
Base classes for tracker update services.
"""

import abc
import datetime
import threading
import time

from sqlalchemy.orm import Session

from spacemodels.models import Tracker

from ..config import SERVICE_WEBHOOK_ENABLED, logger
from ..scanner.core import TrackerClient


class BaseTrackerUpdateService(abc.ABC):
    """
    Abstract base class for tracker update services.

    This class provides the framework for continuously updating
    trackers in the database, whether via webhooks or polling.
    """

    def __init__(self, db: Session, tracker: Tracker):
        """
        Initialize the tracker update service.

        Args:
            db: Database session
            tracker: Tracker model
        """
        self.db = db
        self.tracker = tracker
        self.client = TrackerClient(tracker)
        self.running = False
        self.last_check = datetime.datetime.utcnow()

    @abc.abstractmethod
    def setup(self) -> bool:
        """
        Set up the update service.

        Returns:
            True if setup was successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def update(self) -> int:
        """
        Process updates for the tracker.

        Returns:
            Number of issues updated
        """
        pass

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Clean up resources when service is stopped."""
        pass

    def start(self) -> None:
        """Start the update service."""
        self.running = True

    def stop(self) -> None:
        """Stop the update service."""
        self.running = False
        self.cleanup()


class PollingTrackerUpdateService(BaseTrackerUpdateService):
    """
    Base class for tracker update services that use polling.
    """

    def __init__(self, db: Session, tracker: Tracker, poll_interval: int = 300):
        """
        Initialize the polling tracker update service.

        Args:
            db: Database session
            tracker: Tracker model
            poll_interval: Poll interval in seconds (default: 300)
        """
        super().__init__(db, tracker)
        self.poll_interval = poll_interval
        self.thread = None

    def poll_loop(self) -> None:
        """
        Main polling loop. Runs in a separate thread.
        """
        logger.info(
            f"Starting polling for tracker {self.tracker.id} ({self.tracker.name})"
        )

        while self.running:
            try:
                updates = self.update()
                logger.info(
                    f"Polled tracker {self.tracker.id}, found {updates} updates"
                )
                self.last_check = datetime.datetime.utcnow()
            except Exception as e:
                logger.error(f"Error polling tracker {self.tracker.id}: {str(e)}")

            # Sleep for poll interval
            time.sleep(self.poll_interval)

    def start(self) -> None:
        """Start the polling service in a new thread."""
        super().start()
        self.thread = threading.Thread(target=self.poll_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self) -> None:
        """Stop the polling service."""
        super().stop()
        if self.thread and self.thread.is_alive():
            self.thread.join(
                timeout=5.0
            )  # Wait up to 5 seconds for thread to terminate


class WebhookTrackerUpdateService(BaseTrackerUpdateService):
    """
    Base class for tracker update services that use webhooks.
    """

    def __init__(self, db: Session, tracker: Tracker):
        """
        Initialize the webhook tracker update service.

        Args:
            db: Database session
            tracker: Tracker model
        """
        super().__init__(db, tracker)
        self.webhook_url = None

    @abc.abstractmethod
    def register_webhook(self) -> bool:
        """
        Register webhook with the tracker service.

        Returns:
            True if registration was successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def unregister_webhook(self) -> bool:
        """
        Unregister webhook from the tracker service.

        Returns:
            True if unregistration was successful, False otherwise
        """
        pass

    def setup(self) -> bool:
        """
        Set up the webhook update service.

        Returns:
            True if setup was successful, False otherwise
        """
        return self.register_webhook()

    def cleanup(self) -> None:
        """Clean up webhook registration."""
        self.unregister_webhook()


class TrackerUpdateServiceFactory:
    """
    Factory class for creating tracker update services.
    """

    @staticmethod
    def create_service(db: Session, tracker: Tracker) -> BaseTrackerUpdateService:
        """
        Create a tracker update service for the given tracker.

        Args:
            db: Database session
            tracker: Tracker model

        Returns:
            Appropriate tracker update service instance

        Raises:
            ValueError: If tracker type is not supported
        """
        tracker_type = tracker.tracker_type.lower()

        if tracker_type == "gitlab" and SERVICE_WEBHOOK_ENABLED:
            # Import here to avoid circular imports
            from .gitlab_service import GitLabWebhookUpdateService

            return GitLabWebhookUpdateService(db, tracker)
        elif tracker_type == "gitlab" and not SERVICE_WEBHOOK_ENABLED:
            # Fallback to generic polling if webhooks are disabled
            from .generic_service import GenericPollingUpdateService

            return GenericPollingUpdateService(db, tracker)
        elif tracker_type == "github":
            # For now, fallback to generic polling for GitHub
            from .generic_service import GenericPollingUpdateService

            return GenericPollingUpdateService(db, tracker)
        elif tracker_type == "jira":
            # For now, fallback to generic polling for Jira
            from .generic_service import GenericPollingUpdateService

            return GenericPollingUpdateService(db, tracker)
        else:
            raise ValueError(f"Unsupported tracker type: {tracker_type}")
