"""CRUD operations for Issue model."""

from datetime import datetime, timezone  # Import timezone
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.issue import Issue
from ..models.project import Project
from .base import CRUDBase


class CRUDIssue(CRUDBase[Issue]):
    """CRUD operations for Issue model."""

    def create_with_external(
        self, db: Session, *, obj_in: Dict, sync_to_tracker: bool = True
    ) -> Issue:
        """Create issue, optionally syncing with external tracker."""
        issue = self.create(db, obj_in=obj_in)

        if sync_to_tracker and issue.tracker_id:
            # Placeholder for logic to sync issue to external tracker
            # Update external_id and external_url after sync
            pass

        return issue

    def get_by_title(
        self,
        db: Session,
        *,
        title: str,
        project_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        tracker_id: Optional[str] = None,
    ) -> Optional[Issue]:
        """
        Get issue by title with optional project, organization, and tracker filters.

        Args:
            db: Database session
            title: Issue title to search for
            project_id: Optional project ID to filter by
            organization_id: Optional organization ID to filter by
            tracker_id: Optional tracker ID to filter by

        Returns:
            Issue object if found, otherwise None
        """
        query = db.query(Issue).filter(Issue.title == title)

        if project_id:
            query = query.filter(Issue.project_id == project_id)

        if organization_id:
            # Issues don't have organization_id directly - need to join with Project
            query = query.join(Project, Issue.project_id == Project.id)
            query = query.filter(Project.organization_id == organization_id)

        if tracker_id:
            query = query.filter(Issue.tracker_id == tracker_id)

        return query.first()

    def get_by_key(
        self, db: Session, *, key: str, project_id: Optional[str] = None
    ) -> Optional[Issue]:
        """Get issue by its unique key."""
        query = db.query(Issue).filter(Issue.key == key)
        if project_id:
            query = query.filter(Issue.project_id == project_id)
        return query.first()

    def get_by_external_id(
        self, db: Session, *, project_id: str, external_id: str
    ) -> Optional[Issue]:
        """Get issue by its external ID and project ID."""
        return (
            db.query(Issue)
            .filter(
                Issue.project_id == project_id, Issue.external_id == str(external_id)
            )
            .first()
        )

    def get_for_project(
        self,
        db: Session,
        *,
        project_id: str,
        status: Optional[str] = None,
        issue_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Issue]:
        """Get issues for a project with optional filters."""
        query = db.query(Issue).filter(Issue.project_id == project_id)

        if status:
            query = query.filter(Issue.status == status)
        if issue_type:
            query = query.filter(Issue.issue_type == issue_type)

        return query.order_by(Issue.created_at.desc()).offset(skip).limit(limit).all()

    def get_issue_counts_per_project(
        self, db: Session, *, project_ids: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, int]]:
        """
        Get the number of issues for each project.

        Args:
            db: The database session.
            project_ids: An optional list of project IDs to filter by. If None,
                         counts issues for all projects.

        Returns:
            A dictionary mapping project_id to the number of issues.
        """
        query = db.query(Issue.project_id, func.count(Issue.id))

        if project_ids is not None:
            if not project_ids:
                return {}
            query = query.filter(Issue.project_id.in_(project_ids))

        result = query.group_by(Issue.project_id).all()
        return {project_id: {"total": count} for project_id, count in result}

    def get_for_tracker(
        self, db: Session, *, tracker_id: str, skip: int = 0, limit: int = 100
    ) -> List[Issue]:
        """Get issues for a tracker."""
        return (
            db.query(Issue)
            .filter(Issue.tracker_id == tracker_id)
            .order_by(Issue.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def sync_from_external(
        self, db: Session, *, tracker_id: str, external_id: str
    ) -> Optional[Issue]:
        """Sync issue from external tracker by ID."""
        # Placeholder for logic to fetch issue details from external tracker
        # and update or create local issue
        return None

    def update_status(
        self, db: Session, *, id: str, status: str, sync_to_tracker: bool = True
    ) -> Optional[Issue]:
        """Update issue status and optionally sync to tracker."""
        issue = self.get(db, id=id)
        if issue:
            issue.status = status

            if sync_to_tracker and issue.external_id:
                # Placeholder for logic to sync status to external tracker
                pass

            db.add(issue)
            db.commit()
            db.refresh(issue)
        return issue

    def update_last_synced(self, db: Session, *, id: str) -> Optional[Issue]:
        """Update last_synced timestamp."""
        issue = self.get(db, id=id)
        if issue:
            issue.last_synced = datetime.now(timezone.utc)
            db.add(issue)
            db.commit()
            db.refresh(issue)
        return issue
