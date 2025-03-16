"""Organization model for SpaceBridge."""

from typing import Dict, List, Optional

from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from spacebridge.db.base import Base


class Organization(Base):
    """Organization model for SpaceBridge.

    An organization represents a top-level entity that can contain multiple projects.
    """

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)  # UUID

    # Organization details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Organization settings stored as JSON
    settings: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of the organization."""
        return f"<Organization {self.name} ({self.identifier})>"
