"""API key model for storing API access keys."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, String, DateTime, Boolean

from ..db.vector_types import SQLiteUUID

from .base import Base

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .account import Account


class ApiKey(Base):
    """API key model for authenticated API access.

    Attributes:
        id: The unique identifier for the key.
        name: A user-friendly name for the key.
        key: The actual key value.
        created_at: When the key was created.
        expires_at: When the key expires (optional).
        last_used_at: When the key was last used (optional).
        created_by: The username of the user who created the key.
        scopes: The list of scopes/permissions the key has.
        is_active: Whether the key is active.
    """

    __tablename__ = "api_key"

    # Override id field to use UUID instead of string
    id: Mapped[uuid.UUID] = mapped_column(
        SQLiteUUID, primary_key=True, default=uuid.uuid4
    )

    # Key details
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Security fields
    created_by: Mapped[str] = mapped_column(
        String(50), ForeignKey("account.username"), nullable=False
    )
    scopes: Mapped[List] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    creator: Mapped["Account"] = relationship("Account", back_populates="api_keys")

    def __repr__(self) -> str:
        """Return a string representation of the key.

        Returns:
            String representation of the key.
        """
        return f"<ApiKey {self.name} created by {self.created_by}>"

    def is_expired(self) -> bool:
        """Check if the key is expired.

        Returns:
            True if the key has an expiration date and it's in the past.
        """
        if self.expires_at is None:
            return False
        return self.expires_at < datetime.utcnow()

    def is_valid(self) -> bool:
        """Check if the key is valid.

        Returns:
            True if the key is active and not expired.
        """
        return self.is_active and not self.is_expired()

    def update_last_used(self) -> None:
        """Update the last_used_at timestamp to now."""
        self.last_used_at = datetime.utcnow()
