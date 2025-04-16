"""Tracker model and related types."""

import enum
from datetime import datetime

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.types import JSON, DateTime

from .base import Base

if TYPE_CHECKING:
    from .account import Account
    from .issue import Issue
    from .organization import Organization


class TrackerType(enum.Enum):
    """Enum for tracker types."""

    GITHUB = "github"
    GITLAB = "gitlab"
    JIRA = "jira"


class Tracker(Base):
    """Tracker model - represents an integration with an issue tracking system.

    A tracker is owned by a single account and determines ownership of organizations.
    The account that owns a tracker is considered the owner of all organizations
    linked to that tracker. This provides a clear ownership hierarchy:

    Account -> Tracker -> Organization -> Projects

    Where each entity is owned by the entity to its left.
    """

    # Tracker details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tracker_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Possible values: github, gitlab, jira"
    )
    url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="URL to the tracker (required for Jira, optional for others)",
    )
    api_key: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Encrypted API key or token for authentication",
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    is_deleted: Mapped[bool] = mapped_column(
        default=False, index=True, comment="Flag for soft deletion"
    )
    is_owner_managed: Mapped[bool] = mapped_column(
        default=True,
        comment="If True, the account that owns this tracker also owns all organizations linked to it",
    )

    # Additional connection details stored as JSON
    # Structure examples:
    # GitHub: {
    #     "repository": "owner/repo",
    #     "private_key_path": "/path/to/key.pem",  # For GitHub Apps
    #     "app_id": "12345",                       # For GitHub Apps
    #     "installation_id": "67890"               # For GitHub Apps
    # }
    # GitLab: {
    #     "project_id": "12345",
    #     "group_path": "my-group"
    # }
    # Jira: {
    #     "project_key": "PROJECT",
    #     "cloud_id": "cloud-id-for-jira-cloud",
    #     "use_oauth": true,
    #     "oauth_settings": {...}
    # }
    connection_details: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    # Generic metadata field for extensibility
    meta_data: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    # Foreign keys
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="trackers")
    organizations: Mapped[List["Organization"]] = relationship(
        "Organization", back_populates="tracker", cascade="all, delete-orphan"
    )
    issues: Mapped[List["Issue"]] = relationship(
        "Issue", back_populates="tracker", cascade="all, delete-orphan"
    )

    # Validation status
    is_valid: Mapped[bool] = mapped_column(default=False)
    last_validation: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    validation_message: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True
    )

    # Timestamps
    created: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @validates("tracker_type")
    def validate_tracker_type(self, key, type_):
        """Validate that tracker_type is one of the allowed values."""
        if type_ not in [t.value for t in TrackerType]:
            raise ValueError(
                f"Invalid tracker type: {type_}. Must be one of: {', '.join([t.value for t in TrackerType])}"
            )
        return type_

    @validates("url")
    def validate_url(self, key, url):
        """Validate URL is provided for Jira trackers."""
        if self.tracker_type == TrackerType.JIRA.value and not url:
            raise ValueError("URL is required for Jira trackers")
        return url
