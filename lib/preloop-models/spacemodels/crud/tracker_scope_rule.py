"""CRUD operations for TrackerScopeRule model."""

from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.tracker_scope_rule import TrackerScopeRule
from ..models.tracker import Tracker
from .base import CRUDBase


class CRUDTrackerScopeRule(CRUDBase[TrackerScopeRule]):
    """CRUD operations for TrackerScopeRule model."""

    def get_by_tracker(
        self, db: Session, *, tracker_id: str, account_id: Optional[str] = None
    ) -> List[TrackerScopeRule]:
        """Get all scope rules for a given tracker."""
        query = db.query(TrackerScopeRule).filter(
            TrackerScopeRule.tracker_id == tracker_id
        )
        if account_id:
            query = query.join(Tracker).filter(Tracker.account_id == account_id)
        return query.all()


crud_tracker_scope_rule = CRUDTrackerScopeRule(TrackerScopeRule)
