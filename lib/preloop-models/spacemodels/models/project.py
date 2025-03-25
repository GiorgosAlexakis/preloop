"""Project model."""

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .base import Base

if TYPE_CHECKING:
    from .issue import Issue
    from .organization import Organization


class Project(Base):
    """Project model - belongs to an organization."""

    # Project details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Foreign keys
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Project settings stored as JSON
    settings: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Project-specific tracker settings
    # For configuring project-specific keys, filters, etc.
    tracker_settings: Mapped[Optional[Dict]] = mapped_column(
        JSON, nullable=True, default=dict
    )

    # Generic metadata field for extensibility
    meta_data: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="projects"
    )
    issues: Mapped[List["Issue"]] = relationship(
        "Issue", back_populates="project", cascade="all, delete-orphan"
    )
