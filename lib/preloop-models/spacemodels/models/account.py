"""Account model."""

from datetime import datetime

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import DateTime, func, String  # Added String back
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .base import Base

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from .api_key import ApiKey
    from .api_usage import ApiUsage
    from .organization import Organization
    from .tracker import Tracker
    from .client_version_log import ClientVersionLog
    from .ai_model import AIModel
    from .plan import Subscription
    from .flow import Flow
    from .tool_configuration import ToolConfiguration


class Account(Base):
    """Account model for user authentication and authorization."""

    __tablename__ = "account"

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
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True
    )

    # Relationships
    trackers: Mapped[List["Tracker"]] = relationship(
        "Tracker", back_populates="account", cascade="all, delete-orphan"
    )
    # Organizations this account is a member of (but not necessarily the owner)
    ai_models: Mapped[List["AIModel"]] = relationship(
        "AIModel", back_populates="account", cascade="all, delete-orphan"
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
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription", back_populates="account", cascade="all, delete-orphan"
    )
    flows: Mapped[List["Flow"]] = relationship(
        "Flow",
        back_populates="account",
        cascade="all, delete-orphan",
        foreign_keys="[Flow.account_id]",
    )
    tool_configurations: Mapped[List["ToolConfiguration"]] = relationship(
        "ToolConfiguration", back_populates="account", cascade="all, delete-orphan"
    )

    # Many-to-many relationship helper for organizational roles

    # Property to get organizations this account owns through trackers
    @property
    def owned_organizations(self) -> List["Organization"]:
        """Get organizations owned by this account through trackers."""
        owned_orgs = []
        for tracker in self.trackers:
            owned_orgs.extend(tracker.organizations)
        return owned_orgs

    def get_active_subscription(
        self, db_session: "Session"
    ) -> Optional["Subscription"]:
        """Returns the active subscription for the account, if one exists."""
        from .plan import Subscription

        return (
            db_session.query(Subscription)
            .filter(Subscription.account_id == self.id, Subscription.status == "active")
            .first()
        )
