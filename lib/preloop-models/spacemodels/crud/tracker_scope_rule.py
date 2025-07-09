"""CRUD operations for TrackerScopeRule model."""

from typing import List
from sqlalchemy.orm import Session
from ..models.tracker_scope_rule import TrackerScopeRule
from .base import CRUDBase


class CRUDTrackerScopeRule(CRUDBase[TrackerScopeRule]):
    """CRUD operations for TrackerScopeRule model."""

    def get_by_tracker(self, db: Session, *, tracker_id: str) -> List[TrackerScopeRule]:
        """Get all scope rules for a given tracker."""
        return (
            db.query(TrackerScopeRule)
            .filter(TrackerScopeRule.tracker_id == tracker_id)
            .all()
        )


crud_tracker_scope_rule = CRUDTrackerScopeRule(TrackerScopeRule)
