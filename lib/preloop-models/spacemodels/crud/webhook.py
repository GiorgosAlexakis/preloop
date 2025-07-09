"""CRUD operations for Webhook model."""

from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.webhook import Webhook
from .base import CRUDBase


class CRUDWebhook(CRUDBase[Webhook]):
    """CRUD operations for Webhook model."""

    def get_by_project_id(self, db: Session, *, project_id: str) -> Optional[Webhook]:
        """
        Get a webhook by project ID.

        Args:
            db: Database session.
            project_id: The project ID to search for.

        Returns:
            An optional matching Webhook object. Returns None if no match is found.
        """
        return db.query(Webhook).filter(Webhook.project_id == project_id).first()

    def get_all_for_project(
        self, db: Session, *, project_id: str, skip: int = 0, limit: int = 100
    ) -> List[Webhook]:
        """Get all webhooks for a project."""
        return (
            db.query(Webhook)
            .filter(Webhook.project_id == project_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
