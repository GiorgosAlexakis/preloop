"""IssueRelationship model."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

from .issue import Issue


class IssueRelationship(Base):
    """Model for relationships between issues."""

    __tablename__ = "issue_relationship"

    source_issue_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("issue.id", ondelete="CASCADE"),
        primary_key=True,
    )
    target_issue_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("issue.id", ondelete="CASCADE"),
        primary_key=True,
    )
    type: Mapped[str] = mapped_column(String(50), primary_key=True)

    source_issue: Mapped["Issue"] = relationship(
        "Issue", foreign_keys=[source_issue_id]
    )
    target_issue: Mapped["Issue"] = relationship(
        "Issue", foreign_keys=[target_issue_id]
    )
