"""API usage tracking model for analytics."""

import uuid
from datetime import datetime

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime, Float, Integer, String

from sqlalchemy.dialects.postgresql import UUID

from .base import Base

if TYPE_CHECKING:
    from .user import User


class ApiUsage(Base):
    """API usage model for tracking API requests and resource consumption.

    Attributes:
        id: The unique identifier for the usage record.
        user_id: The ID of the user making the request (nullable for anonymous requests).
        endpoint: The API endpoint being accessed.
        method: The HTTP method used (GET, POST, etc.).
        status_code: The HTTP status code of the response.
        duration: The time taken to process the request in seconds.
        action_type: The type of action (create_issue, update_issue, etc.).
        timestamp: When the request was made.
    """

    __tablename__ = "api_usage"

    # Request details
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    action_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="api_usages")

    def __repr__(self) -> str:
        """Return a string representation of the usage record.

        Returns:
            String representation of the usage record.
        """
        return f"<ApiUsage {self.method} {self.endpoint} by user {self.user_id} at {self.timestamp}>"
