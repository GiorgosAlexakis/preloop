"""CRUD operations for IssueRelationship model."""

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.issue_relationship import IssueRelationship
from .base import CRUDBase


class CRUDIssueRelationship(CRUDBase[IssueRelationship]):
    """CRUD operations for IssueRelationship model."""

    def create(
        self, db: Session, *, source_issue_id: str, target_issue_id: str, type: str
    ) -> IssueRelationship:
        """Create a new issue relationship."""
        if type == "related":
            # For undirected relationships, store with the smaller ID first to avoid duplicates
            if source_issue_id > target_issue_id:
                source_issue_id, target_issue_id = target_issue_id, source_issue_id

        db_obj = IssueRelationship(
            source_issue_id=source_issue_id,
            target_issue_id=target_issue_id,
            type=type,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_for_issue(self, db: Session, *, issue_id: str) -> List[IssueRelationship]:
        """Get all relationships for a given issue."""
        return (
            db.query(self.model)
            .filter(
                or_(
                    self.model.source_issue_id == issue_id,
                    self.model.target_issue_id == issue_id,
                )
            )
            .all()
        )

    def remove(
        self, db: Session, *, source_issue_id: str, target_issue_id: str, type: str
    ) -> Optional[IssueRelationship]:
        """Remove an issue relationship."""
        if type == "related":
            if source_issue_id > target_issue_id:
                source_issue_id, target_issue_id = target_issue_id, source_issue_id

        obj = (
            db.query(self.model)
            .filter_by(
                source_issue_id=source_issue_id,
                target_issue_id=target_issue_id,
                type=type,
            )
            .first()
        )

        if obj:
            db.delete(obj)
            db.commit()
        return obj


issue_relationship = CRUDIssueRelationship(IssueRelationship)
