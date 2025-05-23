"""CRUD operations for Comment model."""

from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.comment import Comment
from .base import CRUDBase


class CRUDComment(CRUDBase[Comment]):
    """CRUD operations for Comment model."""

    def create_with_author(self, db: Session, *, obj_in: dict, author_id: str) -> Comment:
        """Create a new comment with an author."""
        comment_data = obj_in.copy()
        comment_data["author_id"] = author_id
        return super().create(db, obj_in=comment_data)

    def get_multi_by_issue(self, db: Session, *, issue_id: str, skip: int = 0, limit: int = 100) -> List[Comment]:
        """Get multiple comments for a specific issue."""
        return (
            db.query(self.model)
            .filter(self.model.issue_id == issue_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_multi_by_author(self, db: Session, *, author_id: str, skip: int = 0, limit: int = 100) -> List[Comment]:
        """Get multiple comments by a specific author."""
        return (
            db.query(self.model)
            .filter(self.model.author_id == author_id)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

# Initialize CRUDComment instance for easy import
crud_comment = CRUDComment(Comment)
