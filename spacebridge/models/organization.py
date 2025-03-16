"""Organization model for SpaceBridge."""

from typing import Dict, List, Optional

from sqlalchemy import Column, JSON, String
from sqlalchemy.orm import relationship

from spacebridge.db.base import Base


class Organization(Base):
    """Organization model for SpaceBridge.

    An organization represents a top-level entity that can contain multiple projects.
    """

    # Primary key
    id = Column(String(36), primary_key=True, index=True)  # UUID

    # Organization details
    name = Column(String(255), nullable=False)
    identifier = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(1000), nullable=True)

    # Organization settings stored as JSON
    settings = Column(JSON, nullable=True, default=dict)

    # Relationships
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the organization."""
        return f"<Organization {self.name} ({self.identifier})>"
