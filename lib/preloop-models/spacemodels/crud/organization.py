"""CRUD operations for Organization model."""

from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func  # Import func for lower()

from ..models.organization import Organization
from ..models.tracker import Tracker
from .base import CRUDBase


class CRUDOrganization(CRUDBase[Organization]):
    """CRUD operations for Organization model."""

    def get_by_identifier(
        self, db: Session, *, identifier: str, account_id: Optional[str] = None
    ) -> Optional[Organization]:
        """Get organization by unique identifier."""
        query = db.query(Organization).filter(Organization.identifier == identifier)
        if account_id:
            query = query.join(Tracker).filter(Tracker.account_id == account_id)
        return query.first()

    def get_by_name(
        self,
        db: Session,
        *,
        name: str,
        tracker_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Optional[Organization]:
        """
        Get organization by name with optional tracker filter.
        """
        query = db.query(Organization).filter(
            func.lower(Organization.name) == func.lower(name)
        )

        if tracker_id:
            query = query.filter(Organization.tracker_id == tracker_id)
        if account_id:
            query = query.join(Tracker).filter(Tracker.account_id == account_id)

        return query.first()

    def count(self, db: Session, **filters) -> int:
        """Count total number of organizations, with optional filtering."""
        query = db.query(Organization)
        if "account_id" in filters:
            account_id = filters.pop("account_id")
            query = query.join(Tracker).filter(Tracker.account_id == account_id)
        for key, value in filters.items():
            if hasattr(Organization, key):
                query = query.filter(getattr(Organization, key) == value)
        return query.count()

    def get_for_tracker(
        self,
        db: Session,
        *,
        tracker_id: str,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[str] = None,
    ) -> List[Organization]:
        """Get organizations for a tracker."""
        query = db.query(Organization).filter(Organization.tracker_id == tracker_id)
        if account_id:
            query = query.join(Tracker).filter(Tracker.account_id == account_id)
        return query.offset(skip).limit(limit).all()

    def get_active(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[str] = None,
    ) -> List[Organization]:
        """Get active organizations."""
        query = db.query(Organization).filter(Organization.is_active.is_(True))
        if account_id:
            query = query.join(Tracker).filter(Tracker.account_id == account_id)
        return query.offset(skip).limit(limit).all()

    def get_for_account(
        self, db: Session, *, account_id: str, skip: int = 0, limit: int = 100
    ) -> List[Organization]:
        """Get organizations for an account."""
        return (
            db.query(Organization)
            .join(Tracker)
            .filter(Tracker.account_id == account_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def deactivate(self, db: Session, *, id: str) -> Optional[Organization]:
        """Deactivate an organization."""
        organization = self.get(db, id=id)
        if organization:
            organization.is_active = False
            db.add(organization)
            db.commit()
            db.refresh(organization)
        return organization
