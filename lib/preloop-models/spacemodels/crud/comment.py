"""CRUD operations for Comment model."""

from typing import Optional, List

from sqlalchemy.orm import Session

from ..models.comment import Comment
from ..models.account import Account
from ..models.tracker import Tracker
from .base import CRUDBase


class CRUDComment(CRUDBase[Comment]):
    """CRUD operations for Comment model."""

    def create_with_author(self, db: Session, *, obj_in: dict, author: str) -> Comment:
        """Create a new comment with an author."""
        author_obj = db.query(Account).filter(Account.username == author).first()
        if not author_obj:
            raise ValueError(f"Author with username '{author}' not found.")

        comment_data = obj_in.copy()
        comment_data["author_id"] = author_obj.id
        # The 'author' relationship is now correctly handled by SQLAlchemy
        # through the back-populates mechanism via the author_id foreign key.
        if "author" in comment_data:
            del comment_data["author"]

        return super().create(db, obj_in=comment_data)

    def get_by_external_id(
        self,
        db: Session,
        *,
        external_id: str,
        issue_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Optional[Comment]:
        """Get comment by external ID with optional issue filter."""
        query = db.query(self.model).filter(self.model.external_id == external_id)
        if issue_id:
            query = query.filter(self.model.issue_id == issue_id)
        if account_id:
            query = query.join(Tracker).join(Account).filter(Account.id == account_id)
        return query.first()

    def get_multi_by_issue(
        self,
        db: Session,
        *,
        issue_id: str,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[str] = None,
    ) -> List[Comment]:
        """Get multiple comments for a specific issue."""
        query = db.query(self.model).filter(self.model.issue_id == issue_id)
        if account_id:
            query = query.join(Tracker).join(Account).filter(Account.id == account_id)
        return (
            query.order_by(self.model.created_at.asc()).offset(skip).limit(limit).all()
        )

    def get_multi_by_author(
        self,
        db: Session,
        *,
        author: str,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[str] = None,
    ) -> List[Comment]:
        """Get multiple comments by a specific author."""
        query = (
            db.query(self.model)
            .join(self.model.author)
            .filter(Account.username == author)
        )
        if account_id:
            query = query.join(Tracker).filter(Account.id == account_id)
        return (
            query.order_by(self.model.created_at.desc()).offset(skip).limit(limit).all()
        )


# Initialize CRUDComment instance for easy import
crud_comment = CRUDComment(Comment)
