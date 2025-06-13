"""CRUD operations for Project model."""

from typing import List, Optional

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_  # Import func for lower() and or_

from ..models.project import Project
from ..models.organization import Organization  # Ensure Organization is imported
from .base import CRUDBase


class CRUDProject(CRUDBase[Project]):
    """CRUD operations for Project model."""

    def get_all_active_by_identifier_or_name_globally(
        self, db: Session, *, identifier_or_name: str
    ) -> List[Project]:
        """
        Get all active projects by identifier or name across all active organizations.
        The search is case-insensitive for names.
        Eager loads the organization for each project.

        Args:
            db: Database session.
            identifier_or_name: The project identifier (slug) or name to search for.

        Returns:
            A list of matching active Project objects, with their organizations eager-loaded.
            Returns an empty list if no matches are found.
        """
        return (
            db.query(Project)
            .join(
                Project.organization
            )  # Join with organization to filter by its status
            .options(
                joinedload(Project.organization)
            )  # Eager load organization details
            .filter(
                or_(
                    Project.identifier == identifier_or_name,
                    func.lower(Project.name) == func.lower(identifier_or_name),
                    Project.slug == identifier_or_name,  # Also check slug explicitly
                )
            )
            .filter(Project.is_active.is_(True))
            .filter(Organization.is_active.is_(True))  # Ensure organization is active
            .order_by(Project.updated_at.desc())  # Consistent ordering
            .all()
        )

    def get_by_slug_or_identifier(
        self,
        db: Session,
        *,
        slug_or_identifier: str,
        organization_id: Optional[str] = None,
    ) -> Optional[Project]:
        """
        Get a project by slug or identifier, optionally filtered by organization.

        If organization_id is provided, search is limited to that organization.
        If organization_id is None, search across all organizations.

        Returns:
            An optional matching Project object. Returns None if no match is found.
        """
        query = db.query(Project).filter(
            (Project.slug == slug_or_identifier)
            | (Project.identifier == slug_or_identifier)
            | (func.lower(Project.name) == func.lower(slug_or_identifier))
        )

        if organization_id:
            # If organization_id is provided, filter by it
            query = query.filter(Project.organization_id == organization_id)
        query = query.order_by(Project.updated_at.desc())
        return query.first()

    def get_by_name(
        self,
        db: Session,
        *,
        name: str,
        organization_id: Optional[str] = None,
        tracker_id: Optional[
            str
        ] = None,  # Keep tracker_id filter for potential future use, though search_issues doesn't use it now
    ) -> Optional[Project]:
        """
        Get a project by name, optionally filtered by organization and tracker.

        If organization_id is provided, search is limited to that organization.
        If organization_id is None, search across all organizations (unless tracker_id is specified).

        Args:
            db: Database session
            name: Project name to search for (case-insensitive)
            organization_id: Optional organization ID to filter by
            tracker_id: Optional tracker ID to filter by (joins with Organization)

        Returns:
            An optional matching Project object. Returns None if no match is found.
        """
        # Use case-insensitive comparison for name
        query = db.query(Project).filter(func.lower(Project.name) == func.lower(name))

        if organization_id:
            query = query.filter(Project.organization_id == organization_id)

        if tracker_id:
            # Projects don't have tracker_id directly - need to join with Organization
            query = query.join(Organization, Project.organization_id == Organization.id)
            query = query.filter(Organization.tracker_id == tracker_id)

        query = query.order_by(Project.updated_at.desc())

        return query.first()

    def get_by_identifier(self, db: Session, *, identifier: str) -> Optional[Project]:
        """
        Get a project by identifier.

        Args:
            db: Database session.
            identifier: The project identifier to search for.

        Returns:
            An optional matching Project object. Returns None if no match is found.
        """
        return db.query(Project).filter(Project.identifier == identifier).first()

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
    ) -> Optional[Project]:  # Changed return type
        """Get the most recently updated project by identifier or name across all organizations.

        Args:
            db: Database session
            identifier_or_name: Project identifier or name to search for

        Returns:
            An optional matching Project object (the most recently updated if multiple match).
            Returns None if no match is found.
        """
        return (
            db.query(Project)
            .filter(
                (Project.identifier == identifier_or_name)
                | (func.lower(Project.name) == func.lower(identifier_or_name))
            )
            .order_by(Project.updated_at.desc())
            .first()
        )
