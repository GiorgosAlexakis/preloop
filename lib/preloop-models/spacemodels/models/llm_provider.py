"""LLM Provider model for storing provider configurations."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

from sqlalchemy import DateTime, ForeignKey, String, func, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .account import Account


class LLMProvider(Base):
    """Stores LLM provider configurations linked to an account."""

    __tablename__ = "llm_provider"

    # id is inherited from Base

    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credentials: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="llm_providers"  # Correct: points to Account.llm_providers
    )
