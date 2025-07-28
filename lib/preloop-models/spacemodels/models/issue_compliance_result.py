"""IssueComplianceResult model."""

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .issue import Issue


class IssueComplianceResult(Base):
    """Model for storing compliance results for an issue."""

    prompt_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    compliance_factor: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)

    issue_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("issue.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    issue: Mapped["Issue"] = relationship("Issue")
