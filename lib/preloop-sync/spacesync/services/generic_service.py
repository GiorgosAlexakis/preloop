"""
Generic tracker update services.
"""

from sqlalchemy.orm import Session
from typing import List
from spacemodels.crud import (
    crud_organization,
)
from spacemodels.models import Tracker, Organization, Project
from ..exceptions import TrackerRateLimitError, TrackerError # Import necessary exceptions
from ..config import SERVICE_POLL_INTERVAL, logger
from .base import PollingTrackerUpdateService


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
        Process updates for the tracker by polling. Fetches projects from the tracker API
        via scan_projects, updates the database, and then scans issues.
        Handles rate limit errors.

        Returns:
            Number of issue embeddings updated during this run.
        """
        logger.info(f"Starting update poll for tracker {self.tracker.id} ({self.tracker.name})")
        total_embedding_updates = 0
        rate_limited_tracker = False # Flag to stop processing this tracker if rate limited

        # 1. Get organizations for this tracker from DB
        try:
            db_organizations: List[Organization] = crud_organization.get_for_tracker(
                self.db, tracker_id=self.tracker.id
            )
            if not db_organizations:
                logger.info(f"No active organizations found for tracker {self.tracker.id}. Skipping update cycle.")
                return 0
        except Exception as e:
            logger.error(f"Failed to get organizations for tracker {self.tracker.id}: {e}", exc_info=True)
            return 0 # Cannot proceed without organizations

        # Process each organization
        for org in db_organizations:
            if rate_limited_tracker:
                logger.warning(f"Skipping remaining organizations for tracker {self.tracker.id} due to rate limit.")
                break # Stop processing orgs for this tracker if rate limited

            logger.debug(f"Processing organization {org.identifier} (ID: {org.id}) for tracker {self.tracker.id}")

            # 2. Scan Projects (fetches from API and reconciles with DB)
            processed_projects: List[Project] = []
            try:
                # Use the existing scan_projects method which handles API fetch and DB sync
                processed_projects = self.client.scan_projects(db=self.db, organization=org)
                logger.info(f"Successfully scanned/synchronized {len(processed_projects)} projects for org {org.identifier} (tracker {self.tracker.id}).")
            except TrackerRateLimitError as rle:
                logger.warning(f"Rate limit hit for tracker {self.tracker.id} during project scan for org {org.identifier}. Pausing updates for this tracker. Details: {rle}")
                rate_limited_tracker = True
                continue # Skip to next org (or break due to flag)
            except (TrackerError, NotImplementedError) as te:
                # Catch specific tracker errors or if scan_projects/get_projects isn't implemented
                logger.error(f"Tracker error scanning projects for org {org.identifier} (tracker {self.tracker.id}): {te}", exc_info=True)
                continue # Skip this org
            except Exception as e:
                logger.error(f"Unexpected error scanning projects for org {org.identifier} (tracker {self.tracker.id}): {e}", exc_info=True)
                continue # Skip this org

            # 3. Scan Issues for the synchronized projects returned by scan_projects
            logger.info(f"Scanning issues for {len(processed_projects)} projects in org {org.identifier} (tracker {self.tracker.id}).")
            for project in processed_projects:
                if rate_limited_tracker:
                    logger.warning(f"Skipping issue scan for project {project.identifier} due to rate limit.")
                    break # Stop processing projects for this org

                try:
                    # Scan issues for this synchronized project
                    # Note: scan_issues might also need error handling refinement
                    issues, embedding_updates = self.client.scan_issues(
                        self.db, org, project # Pass DB objects
                    )
                    total_embedding_updates += embedding_updates

                    if embedding_updates > 0:
                        logger.info(
                            f"Updated {embedding_updates} embeddings for project {project.id} ({project.name}) in tracker {self.tracker.id}"
                        )
                except TrackerRateLimitError as rle:
                    logger.warning(f"Rate limit hit for tracker {self.tracker.id} while scanning project {project.id}. Pausing updates for this tracker. Details: {rle}")
                    rate_limited_tracker = True # Set flag
                    break # Stop processing projects for this org
                except TrackerError as te:
                    logger.error(f"Tracker error scanning issues for project {project.id} (tracker {self.tracker.id}): {te}", exc_info=True)
                    continue # Continue with next project
                except Exception as e:
                    logger.error(f"Unexpected error scanning issues for project {project.id} (tracker {self.tracker.id}): {e}", exc_info=True)
                    continue # Continue with next project

        logger.info(f"Finished update poll for tracker {self.tracker.id}. Total embedding updates: {total_embedding_updates}. Rate limited: {rate_limited_tracker}")
        return total_embedding_updates

    def cleanup(self) -> None:
        """Clean up resources when service is stopped."""
        # No specific cleanup needed for generic polling service unless resources are added
        logger.info(f"Cleaning up generic polling service for tracker {self.tracker.id}")
        pass
