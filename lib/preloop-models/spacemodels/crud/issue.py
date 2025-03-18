"""CRUD operations for Issue model."""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.issue import Issue
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
            issue.last_synced = datetime.utcnow()
            db.add(issue)
            db.commit()
            db.refresh(issue)
        return issue
