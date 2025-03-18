"""CRUD operations for Tracker model."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.tracker import Tracker, TrackerType
from .base import CRUDBase


class CRUDTracker(CRUDBase[Tracker]):
    """CRUD operations for Tracker model."""

    def get_for_account(
        self, db: Session, *, account_id: str, skip: int = 0, limit: int = 100
    ) -> List[Tracker]:
        """Get trackers for an account."""
        return (
            db.query(Tracker)
            .filter(Tracker.account_id == account_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active(
        self,
        db: Session,
        *,
        account_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Tracker]:
        """Get active trackers, optionally filtered by account."""
        query = db.query(Tracker).filter(Tracker.is_active == True)
        if account_id:
            query = query.filter(Tracker.account_id == account_id)
        return query.offset(skip).limit(limit).all()

    def get_by_type(
        self,
        db: Session,
        *,
        tracker_type: TrackerType,
        account_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Tracker]:
        """Get trackers by type, optionally filtered by account."""
        query = db.query(Tracker).filter(Tracker.tracker_type == tracker_type.value)
        if account_id:
            query = query.filter(Tracker.account_id == account_id)
        return query.offset(skip).limit(limit).all()

    def validate(
        self, db: Session, *, id: str, is_valid: bool, message: Optional[str] = None
    ) -> Optional[Tracker]:
        """Update tracker validation status."""
        tracker = self.get(db, id=id)
        if tracker:
            tracker.is_valid = is_valid
            tracker.last_validation = datetime.utcnow()
            tracker.validation_message = message
            db.add(tracker)
            db.commit()
            db.refresh(tracker)
        return tracker

    def deactivate(self, db: Session, *, id: str) -> Optional[Tracker]:
        """Deactivate a tracker."""
        tracker = self.get(db, id=id)
        if tracker:
            tracker.is_active = False
            db.add(tracker)
            db.commit()
            db.refresh(tracker)
        return tracker
