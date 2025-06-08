"""Organization model."""

# Import at the end to avoid circular imports
from datetime import datetime
import uuid  # Added uuid import
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID  # Added UUID import
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .account import AccountOrganization
from .base import Base
from .tracker import Tracker

if TYPE_CHECKING:
    from .account import Account
    from .project import Project


class Organization(Base):
    """Organization model - a top-level entity that can contain multiple projects.

    An organization is owned by a single account through a tracker. The owner has full
    administrative access to the organization. Additional accounts can be added as
    members with different roles through the AccountOrganization relationship.
    """

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

    # Secret for verifying incoming webhooks (e.g., HMAC signature)
    webhook_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps for sync updates
    last_webhook_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    last_polling_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Foreign keys - the tracker determines the owner account
    tracker_id: Mapped[uuid.UUID] = mapped_column(  # Changed str to uuid.UUID
        UUID(as_uuid=True),  # Changed String(36) to UUID
        ForeignKey("tracker.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    tracker: Mapped["Tracker"] = relationship("Tracker", back_populates="organizations")
    projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="organization", cascade="all, delete-orphan"
    )
    # Members are additional accounts that have access to the organization
    members: Mapped[List["AccountOrganization"]] = relationship(
        "AccountOrganization", back_populates="organization"
    )

    # Property to get the owner account through the tracker
    @property
    def owner(self) -> "Account":
        """Get the owner account of this organization through the tracker."""
        return self.tracker.account
