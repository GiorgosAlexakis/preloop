"""Account and AccountOrganization models."""

from datetime import datetime

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .base import Base

if TYPE_CHECKING:
    from .api_key import ApiKey
    from .api_usage import ApiUsage
    from .organization import Organization
    from .tracker import Tracker
    from .client_version_log import ClientVersionLog


class Account(Base):
    """Account model for user authentication and authorization."""

    # Account details
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email_verified: Mapped[bool] = mapped_column(default=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Authentication
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)

    # OAuth information
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Generic metadata field for extensibility
    meta_data: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    trackers: Mapped[List["Tracker"]] = relationship(
        "Tracker", back_populates="account", cascade="all, delete-orphan"
    )
    # Organizations this account is a member of (but not necessarily the owner)
    organization_memberships: Mapped[List["AccountOrganization"]] = relationship(
        "AccountOrganization", back_populates="account", cascade="all, delete-orphan"
    )
    api_keys: Mapped[List["ApiKey"]] = relationship(
        "ApiKey", back_populates="creator", cascade="all, delete-orphan"
    )
    api_usages: Mapped[List["ApiUsage"]] = relationship(
        "ApiUsage", back_populates="user", cascade="all, delete-orphan"
    )
    client_version_logs: Mapped[List["ClientVersionLog"]] = relationship(
        "ClientVersionLog", back_populates="account", cascade="all, delete-orphan"
    )

    # Many-to-many relationship helper for organizational roles
    organization_roles: Mapped[Dict[str, str]] = association_proxy(
        "organization_memberships",
        "role",
        creator=lambda k, v: AccountOrganization(organization_id=k, role=v),
    )

    # Property to get organizations this account owns through trackers
    @property
    def owned_organizations(self) -> List["Organization"]:
        """Get organizations owned by this account through trackers."""
        owned_orgs = []
        for tracker in self.trackers:
            owned_orgs.extend(tracker.organizations)
        return owned_orgs


class AccountOrganization(Base):
    """Join table for accounts and organizations with roles.

    This represents memberships/collaborations in an organization, separate from
    ownership which is determined by the tracker relationship.
    """

    __tablename__ = "accountorganization"

    # Composite primary key
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("account.id", ondelete="CASCADE"), primary_key=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), primary_key=True
    )

    # Role in the organization
    role: Mapped[str] = mapped_column(String(50), default="member")

    # Add timestamps manually since we're not inheriting from Base
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="organization_memberships"
    )
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="members"
    )
