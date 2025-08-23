"""CRUD operations for IssueRelationship model."""

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.issue_relationship import IssueRelationship
from .base import CRUDBase


class CRUDIssueRelationship(CRUDBase[IssueRelationship]):
    """CRUD operations for IssueRelationship model."""

    def create(
        self,
        db: Session,
        *,
        source_issue_id: str,
        target_issue_id: str,
        type: str,
        reason: Optional[str] = None,
        confidence_score: Optional[float] = None,
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
            reason=reason,
            confidence_score=confidence_score,
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

    def get_relationships_for_issues(
        self, db: Session, *, issue_ids: List[str]
    ) -> List[IssueRelationship]:
        """Get all relationships where both source and target are in the given list of issues."""
        return (
            db.query(self.model)
            .filter(
                self.model.source_issue_id.in_(issue_ids),
                self.model.target_issue_id.in_(issue_ids),
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
