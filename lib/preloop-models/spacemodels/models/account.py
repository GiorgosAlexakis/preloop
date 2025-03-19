"""Account and AccountOrganization models."""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .base import Base

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tracker import Tracker
    from .organization import Organization
    from .api_key import ApiKey
    from .api_usage import ApiUsage


class Account(Base):
    """Account model for user authentication and authorization."""

    # Account details
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email_verified: Mapped[bool] = mapped_column(default=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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
    organizations: Mapped[List["AccountOrganization"]] = relationship(
        "AccountOrganization", back_populates="account", cascade="all, delete-orphan"
    )
    api_keys: Mapped[List["ApiKey"]] = relationship(
        "ApiKey", back_populates="creator", cascade="all, delete-orphan"
    )
    api_usages: Mapped[List["ApiUsage"]] = relationship(
        "ApiUsage", back_populates="user", cascade="all, delete-orphan"
    )

    # Many-to-many relationship helper
    organization_roles: Mapped[Dict[str, str]] = association_proxy(
        "organizations",
        "role",
        creator=lambda k, v: AccountOrganization(organization_id=k, role=v),
    )


class AccountOrganization(Base):
    """Join table for accounts and organizations with roles."""

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
    account: Mapped["Account"] = relationship("Account", back_populates="organizations")
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="accounts"
    )
