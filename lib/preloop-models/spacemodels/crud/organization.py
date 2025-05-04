"""CRUD operations for Organization model."""

from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func  # Import func for lower()

from ..models.organization import Organization
from .base import CRUDBase


class CRUDOrganization(CRUDBase[Organization]):
    """CRUD operations for Organization model."""

    def __init__(self):
        """Initialize with the Organization model."""
        super().__init__(model=Organization)

    def get_by_identifier(
        self, db: Session, *, identifier: str
    ) -> Optional[Organization]:
        """Get organization by unique identifier."""
        return (
            db.query(Organization).filter(Organization.identifier == identifier).first()
        )

    def get_by_name(
        self, db: Session, *, name: str, tracker_id: Optional[str] = None
    ) -> Optional[Organization]:
        """
        Get organization by name with optional tracker filter.

        Args:
            db: Database session
            name: Organization name to search for
            tracker_id: Optional tracker ID to filter by

        Returns:
            Organization object if found, otherwise None
        """
        query = db.query(Organization).filter(
            func.lower(Organization.name) == func.lower(name)
        )

        if tracker_id:
            query = query.filter(Organization.tracker_id == tracker_id)

        return query.first()

    def count(self, db: Session, **filters) -> int:
        """Count total number of organizations, with optional filtering."""
        query = db.query(Organization)
        for key, value in filters.items():
            if hasattr(Organization, key):
                query = query.filter(getattr(Organization, key) == value)
        return query.count()

    def get_for_tracker(
        self, db: Session, *, tracker_id: str, skip: int = 0, limit: int = 100
    ) -> List[Organization]:
        """Get organizations for a tracker."""
        return (
            db.query(Organization)
            .filter(Organization.tracker_id == tracker_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[Organization]:
        """Get active organizations."""
        return (
            db.query(Organization)
            .filter(Organization.is_active.is_(True))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_for_account(
        self, db: Session, *, account_id: str, skip: int = 0, limit: int = 100
    ) -> List[Organization]:
        """Get organizations for an account."""
        return (
            db.query(Organization)
            .join(Organization.accounts)
            .filter(Organization.accounts.any(account_id == account_id))
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
