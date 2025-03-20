"""
Generic tracker update services.
"""

import datetime
from typing import Dict, Any, List, Optional
import time

from sqlalchemy.orm import Session

from ..config import logger, SERVICE_POLL_INTERVAL
from spacemodels.models import Tracker, Organization, Project, Issue
from spacemodels.crud import crud_tracker, crud_organization, crud_project, crud_issue, crud_issue_embedding
from ..scanner.core import TrackerClient, scan_issues
from .base import PollingTrackerUpdateService


class GenericPollingUpdateService(PollingTrackerUpdateService):
    """
    Generic polling update service for trackers that don't support webhooks
    or don't have a specific implementation.
    """
    
    def __init__(self, db: Session, tracker: Tracker, poll_interval: int = SERVICE_POLL_INTERVAL):
        """
        Initialize the generic polling update service.
        
        Args:
            db: Database session
            tracker: Tracker model
            poll_interval: Poll interval in seconds (default: 300)
        """
        super().__init__(db, tracker, poll_interval)
    
    def setup(self) -> bool:
        """
        Set up the polling update service.
        
        Returns:
            True if setup was successful, False otherwise
        """
        # Validate tracker connection
        try:
            crud_tracker.validate_connection(self.db, tracker_id=self.tracker.id)
            return True
        except Exception as e:
            logger.error(f"Error setting up polling service for tracker {self.tracker.id}: {str(e)}")
            return False
    
    def update(self) -> int:
        """
        Process updates for the tracker by polling.
        
        Returns:
            Number of issues updated
        """
        # Get organizations for this tracker
        organizations = crud_organization.get_for_tracker(self.db, tracker_id=self.tracker.id)
        
        total_updates = 0
        
        for org in organizations:
            # Get projects for this organization
            projects = crud_project.get_for_organization(self.db, organization_id=org.id)
            
            for project in projects:
                # Scan issues for this project
                # We reuse the existing scan_issues method from the scanner core
                issues, embedding_updates = scan_issues(
                    self.db,
                    self.client,
                    org,
                    project
                )
                
                total_updates += embedding_updates
                
                if embedding_updates > 0:
                    logger.info(f"Updated {embedding_updates} issues for project {project.id} ({project.name})")
        
        return total_updates
    
    def cleanup(self) -> None:
        """Clean up resources when service is stopped."""
        # No cleanup needed for generic polling service
        pass
