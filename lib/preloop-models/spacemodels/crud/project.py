"""CRUD operations for Project model."""

from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.project import Project
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

    def get_active(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """Get active projects."""
        return (
            db.query(Project)
            .filter(Project.is_active == True)
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
