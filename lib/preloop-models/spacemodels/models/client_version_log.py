from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class ClientVersionLog(Base):
    """Database model for logging client versions."""

    __tablename__ = "client_version_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ip_address: Mapped[str] = mapped_column(String, nullable=False, index=True)
    client_version: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    account_id: Mapped[
        Optional[str]
    ] = mapped_column(  # Changed type hint to Optional[str]
        String(36),
        ForeignKey("account.id"),
        nullable=True,
        index=True,  # Changed type to String(36)
    )
    organization_identifier: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    project_identifier: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )

    # Relationship to Account (optional)
    account = relationship("Account", back_populates="client_version_logs")
