"""Webhook model."""

from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .project import Project
    from .organization import Organization


class Webhook(Base):
    """Webhook model - represents a registered webhook."""

    __tablename__ = "webhook"

    # Webhook details
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    events: Mapped[List[str]] = mapped_column(JSON, nullable=False)

    # Foreign keys
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    organization: Mapped["Organization"] = relationship("Organization")
