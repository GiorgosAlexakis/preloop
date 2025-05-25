"""Comment model."""

from typing import TYPE_CHECKING, Optional, List, Dict

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .base import Base

if TYPE_CHECKING:
    from .issue import Issue
    from .account import Account
    from .embedding import IssueEmbedding


class Comment(Base):
    """Comment model - represents a comment on an issue or other entities."""

    __tablename__ = "comment"

    body: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="issue",
        comment="Type of comment (e.g., 'issue', 'merge_request')",
    )

    # Foreign keys
    issue_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("issue.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "account.id", ondelete="SET NULL"
        ),  # Or CASCADE, depending on desired behavior
        nullable=True,  # Allow comments from deleted users or system
        index=True,
    )

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="comments")
    author: Mapped[Optional["Account"]] = relationship(
        "Account"
    )  # Add back_populates if a 'comments' relationship is added to Account
    embeddings: Mapped[List["IssueEmbedding"]] = relationship(
        "IssueEmbedding", back_populates="comment", cascade="all, delete-orphan"
    )

    # Metadata stored as JSON (for custom fields, labels, etc.)
    meta_data: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, type='{self.type}', issue_id='{self.issue_id}', author_id='{self.author_id}')>"
