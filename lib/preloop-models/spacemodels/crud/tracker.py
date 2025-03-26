"""CRUD operations for Tracker model."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.tracker import Tracker, TrackerType
from .base import CRUDBase


class CRUDTracker(CRUDBase[Tracker]):
    """CRUD operations for Tracker model."""

    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> Tracker:
        """Create new tracker with initialized timestamp fields."""
        obj_data = dict(obj_in)

        # Initialize timestamp fields
        current_time = datetime.utcnow()
        obj_data.setdefault("created", current_time)
        obj_data.setdefault("last_updated", current_time)

        return super().create(db=db, obj_in=obj_data)

    def update(
        self, db: Session, *, db_obj: Tracker, obj_in: Dict[str, Any]
    ) -> Tracker:
        """Update tracker and its last_updated timestamp."""
        # Update last_updated field
        obj_in["last_updated"] = datetime.utcnow()

        return super().update(db=db, db_obj=db_obj, obj_in=obj_in)

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
        query = db.query(Tracker).filter(Tracker.is_active.is_(True))
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
            current_time = datetime.utcnow()
            tracker.last_validation = current_time
            tracker.last_updated = current_time
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
            tracker.last_updated = datetime.utcnow()
            db.add(tracker)
            db.commit()
            db.refresh(tracker)
        return tracker
