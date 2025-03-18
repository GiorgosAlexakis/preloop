"""Organization model."""

from typing import Dict, List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .base import Base
from .account import AccountOrganization
from .tracker import Tracker

# Import at the end to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .project import Project


class Organization(Base):
    """Organization model - a top-level entity that can contain multiple projects."""

    # Organization details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Organization settings stored as JSON
    settings: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Generic metadata field for extensibility
    meta_data: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    # Foreign keys
    tracker_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tracker.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    tracker: Mapped["Tracker"] = relationship("Tracker", back_populates="organizations")
    projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="organization", cascade="all, delete-orphan"
    )
    accounts: Mapped[List["AccountOrganization"]] = relationship(
        "AccountOrganization", back_populates="organization"
    )
