"""AIModel model for storing model configurations."""

import uuid
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .account import Account
    from .flow import Flow
    from .issue_set import IssueSet


class AIModel(Base):
    """
    Stores AI model configurations.
    """

    __tablename__ = "ai_model"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Provider and model details
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_identifier: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    api_endpoint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    api_key: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Stored unencrypted for now

    # Ownership and sharing
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account.id"), nullable=True, index=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Additional parameters
    model_parameters: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)
    meta_data: Mapped[Optional[Dict]] = mapped_column(
        JSONB, nullable=True, default=dict
    )

    # Relationships
    account: Mapped[Optional["Account"]] = relationship(back_populates="ai_models")
    flows: Mapped[List["Flow"]] = relationship(back_populates="ai_model")
    issue_sets: Mapped[List["IssueSet"]] = relationship(back_populates="ai_model")

    def __repr__(self):
        return f"<AIModel(id={self.id}, name='{self.name}')>"
