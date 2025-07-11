"""CRUD operations for Project model."""

from typing import List, Optional

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from ..models.project import Project
from ..models.organization import Organization
from ..models.tracker import Tracker
from .base import CRUDBase


class CRUDProject(CRUDBase[Project]):
    """CRUD operations for Project model."""

    def get_all_active_by_identifier_or_name_globally(
        self,
        db: Session,
        *,
        identifier_or_name: str,
        account_id: Optional[str] = None,
    ) -> List[Project]:
        """
        Get all active projects by identifier or name across all active organizations.
        The search is case-insensitive for names.
        Eager loads the organization for each project.
        """
        query = (
            db.query(Project)
            .join(Project.organization)
            .options(joinedload(Project.organization))
            .filter(
                or_(
                    Project.identifier == identifier_or_name,
                    func.lower(Project.name) == func.lower(identifier_or_name),
                    Project.slug == identifier_or_name,
                )
            )
            .filter(Project.is_active.is_(True))
            .filter(Organization.is_active.is_(True))
        )

        if account_id:
            query = query.join(Organization.tracker).filter(
                Tracker.account_id == account_id
            )

        return query.order_by(Project.updated_at.desc()).all()

    def get_by_slug_or_identifier(
        self,
        db: Session,
        *,
        slug_or_identifier: str,
        organization_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Optional[Project]:
        """
        Get a project by slug or identifier, optionally filtered by organization.
        """
        query = db.query(Project).filter(
            (Project.slug == slug_or_identifier)
            | (Project.identifier == slug_or_identifier)
            | (func.lower(Project.name) == func.lower(slug_or_identifier))
        )

        if organization_id:
            query = query.filter(Project.organization_id == organization_id)

        if account_id:
            query = (
                query.join(Project.organization)
                .join(Organization.tracker)
                .filter(Tracker.account_id == account_id)
            )

        return query.order_by(Project.updated_at.desc()).first()

    def get_by_name(
        self,
        db: Session,
        *,
        name: str,
        organization_id: Optional[str] = None,
        tracker_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Optional[Project]:
        """
        Get a project by name, optionally filtered by organization, tracker, and account.
        """
        query = db.query(Project).filter(func.lower(Project.name) == func.lower(name))

        if organization_id:
            query = query.filter(Project.organization_id == organization_id)

        if tracker_id:
            query = query.join(Project.organization).filter(
                Organization.tracker_id == tracker_id
            )

        if account_id:
            query = (
                query.join(Project.organization)
                .join(Organization.tracker)
                .filter(Tracker.account_id == account_id)
            )

        return query.order_by(Project.updated_at.desc()).first()

    def get_by_identifier(
        self, db: Session, *, identifier: str, account_id: Optional[str] = None
    ) -> Optional[Project]:
        """
        Get a project by identifier.
        """
        query = db.query(Project).filter(Project.identifier == identifier)
        if account_id:
            query = (
                query.join(Project.organization)
                .join(Organization.tracker)
                .filter(Tracker.account_id == account_id)
            )
        return query.first()

    def get_for_organization(
        self,
        db: Session,
        *,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[str] = None,
    ) -> List[Project]:
        """Get projects for an organization."""
        query = db.query(Project).filter(Project.organization_id == organization_id)
        if account_id:
            query = (
                query.join(Project.organization)
                .join(Organization.tracker)
                .filter(Tracker.account_id == account_id)
            )
        return query.offset(skip).limit(limit).all()

    def count_for_organization(
        self, db: Session, *, organization_id: str, account_id: Optional[str] = None
    ) -> int:
        """Count total number of projects for an organization."""
        query = db.query(Project).filter(Project.organization_id == organization_id)
        if account_id:
            query = (
                query.join(Project.organization)
                .join(Organization.tracker)
                .filter(Tracker.account_id == account_id)
            )
        return query.count()

    def get_active(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[str] = None,
    ) -> List[Project]:
        """Get active projects."""
        query = db.query(Project).filter(Project.is_active.is_(True))
        if account_id:
            query = (
                query.join(Project.organization)
                .join(Organization.tracker)
                .filter(Tracker.account_id == account_id)
            )
        return query.offset(skip).limit(limit).all()

    def deactivate(
        self, db: Session, *, id: str, account_id: Optional[str] = None
    ) -> Optional[Project]:
        """Deactivate a project."""
        project = self.get(db, id=id, account_id=account_id)
        if project:
            project.is_active = False
            db.add(project)
            db.commit()
            db.refresh(project)
        return project

    def get_by_identifier_or_name_across_orgs(
        self,
        db: Session,
        *,
        identifier_or_name: str,
        account_id: Optional[str] = None,
    ) -> Optional[Project]:
        """Get the most recently updated project by identifier or name across all organizations."""
        query = db.query(Project).filter(
            (Project.identifier == identifier_or_name)
            | (func.lower(Project.name) == func.lower(identifier_or_name))
        )
        if account_id:
            query = (
                query.join(Project.organization)
                .join(Organization.tracker)
                .filter(Tracker.account_id == account_id)
            )
        return query.order_by(Project.updated_at.desc()).first()
