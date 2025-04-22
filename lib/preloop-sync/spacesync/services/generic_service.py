"""
Generic tracker update services.
"""

from sqlalchemy.orm import Session

from spacemodels.crud import (
    crud_organization,
    crud_project,
)
from spacemodels.models import Tracker

from ..config import SERVICE_POLL_INTERVAL, logger
# Import exceptions, but not scan_issues directly
from ..exceptions import TrackerRateLimitError, TrackerError # Import necessary exceptions
from .base import PollingTrackerUpdateService
# TrackerClient is already available via self.client inherited from BaseTrackerUpdateService


class GenericPollingUpdateService(PollingTrackerUpdateService):
    """
    Generic polling update service for trackers that don't support webhooks
    or don't have a specific implementation.
    """

    def __init__(
        self, db: Session, tracker: Tracker, poll_interval: int = SERVICE_POLL_INTERVAL
    ):
        """
        Initialize the generic polling update service.

        Args:
            db: Database session
            tracker: Tracker model
            poll_interval: Poll interval in seconds (default: 90)
        """
        super().__init__(db, tracker, poll_interval)

    def setup(self) -> bool:
        """
        Set up the polling update service.
        Connection is implicitly tested during TrackerClient initialization.

        Returns:
            Always True for the generic polling service, assuming client init succeeded.
        """
        # No explicit setup needed here for generic polling after client init.
        # Connection validation happens implicitly in TrackerClient.__init__
        logger.debug(f"GenericPollingUpdateService setup complete for tracker {self.tracker.id}")
        return True

    def update(self) -> int:
        """
        Process updates for the tracker by polling. Handles rate limit errors.

        Returns:
            Number of issues updated during this run.
        """
        logger.info(f"Starting update poll for tracker {self.tracker.id} ({self.tracker.name})")
        # Get organizations for this tracker
        try:
            organizations = crud_organization.get_for_tracker(
                self.db, tracker_id=self.tracker.id
            )
        except Exception as e:
            logger.error(f"Failed to get organizations for tracker {self.tracker.id}: {e}", exc_info=True)
            return 0 # Cannot proceed without organizations

        total_updates = 0
        rate_limited = False # Flag to stop processing this tracker if rate limited

        for org in organizations:
            if rate_limited:
                break # Stop processing orgs for this tracker if rate limited

            # Get projects for this organization
            try:
                projects = crud_project.get_for_organization(
                    self.db, organization_id=org.id
                )
            except Exception as e:
                logger.error(f"Failed to get projects for org {org.id} (tracker {self.tracker.id}): {e}", exc_info=True)
                continue # Skip this org

            for project in projects:
                if rate_limited:
                    break # Stop processing projects if rate limited

                try:
                    # Scan issues for this project using the client instance
                    # The client instance holds the specific tracker implementation (GitHub, GitLab, etc.)
                    # The scan_issues method is defined in the TrackerClient class in core.py
                    issues, embedding_updates = self.client.scan_issues(
                        self.db, org, project
                    )
                    # Note: Removed self.client from args as it's implicitly self within the method call

                    total_updates += embedding_updates

                    if embedding_updates > 0:
                        logger.info(
                            f"Updated {embedding_updates} embeddings for project {project.id} ({project.name}) in tracker {self.tracker.id}"
                        )
                except TrackerRateLimitError as rle:
                    logger.warning(f"Rate limit hit for tracker {self.tracker.id} while scanning project {project.id}. Pausing updates for this cycle. Details: {rle}")
                    rate_limited = True # Set flag to stop processing this tracker
                    # Optionally, could interact with scheduler here if passed in
                    break # Stop processing projects for this org
                except TrackerError as te:
                    logger.error(f"Tracker error for tracker {self.tracker.id}, project {project.id}: {te}", exc_info=True)
                    # Decide whether to continue with other projects or stop for this tracker
                    continue # Continue with next project for now
                except Exception as e:
                    logger.error(f"Unexpected error scanning project {project.id} for tracker {self.tracker.id}: {e}", exc_info=True)
                    continue # Continue with next project

        logger.info(f"Finished update poll for tracker {self.tracker.id}. Total embedding updates: {total_updates}. Rate limited: {rate_limited}")
        return total_updates

    def cleanup(self) -> None:
        """Clean up resources when service is stopped."""
        # No specific cleanup needed for generic polling service unless resources are added
        logger.info(f"Cleaning up generic polling service for tracker {self.tracker.id}")
        pass
