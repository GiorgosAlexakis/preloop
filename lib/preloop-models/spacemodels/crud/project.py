"""CRUD operations for Project model."""

from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func  # Import func for lower()

from ..models.project import Project
from ..models.organization import Organization
from .base import CRUDBase


class CRUDProject(CRUDBase[Project]):
    """CRUD operations for Project model."""

    def get_by_identifier(
        self, db: Session, *, identifier: str, organization_id: str
    ) -> Optional[Project]:
        """Get project by identifier within an organization."""
        return (
            db.query(Project)
            .filter(
                Project.identifier == identifier,
                Project.organization_id == organization_id,
            )
            .first()
        )

    def get_by_name(
        self,
        db: Session,
        *,
        name: str,
        organization_id: Optional[str] = None,
        tracker_id: Optional[str] = None,
    ) -> Optional[Project]:
        """
        Get project by name with optional organization and tracker filters.

        Args:
            db: Database session
            name: Project name to search for
            organization_id: Optional organization ID to filter by
            tracker_id: Optional tracker ID to filter by

        Returns:
            Project object if found, otherwise None
        """
        # Use case-insensitive comparison for name
        query = db.query(Project).filter(func.lower(Project.name) == func.lower(name))

        if organization_id:
            query = query.filter(Project.organization_id == organization_id)

        if tracker_id:
            # Projects don't have tracker_id directly - need to join with Organization
            query = query.join(Organization, Project.organization_id == Organization.id)
            query = query.filter(Organization.tracker_id == tracker_id)

        return query.first()

    def get_for_organization(
        self, db: Session, *, organization_id: str, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """Get projects for an organization."""
        return (
            db.query(Project)
            .filter(Project.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(self, db: Session, *, organization_id: str) -> int:
        """Count total number of projects for an organization."""
        return (
            db.query(Project).filter(Project.organization_id == organization_id).count()
        )

    def get_active(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """Get active projects."""
        return (
            db.query(Project)
            .filter(Project.is_active.is_(True))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def deactivate(self, db: Session, *, id: str) -> Optional[Project]:
        """Deactivate a project."""
        project = self.get(db, id=id)
        if project:
            project.is_active = False
            db.add(project)
            db.commit()
            db.refresh(project)
        return project

    def get_by_identifier_or_name_across_orgs(
        self, db: Session, *, identifier_or_name: str
    ) -> List[Project]:
        """Get projects by identifier or name across all organizations.

        Args:
            db: Database session
            identifier_or_name: Project identifier or name to search for

        Returns:
            List of matching projects
        """
        return (
            db.query(Project)
            .filter(
                (Project.identifier == identifier_or_name)
                | (func.lower(Project.name) == func.lower(identifier_or_name))
            )
            .all()
        )
