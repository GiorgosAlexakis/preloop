"""LLM Model model for storing model configurations."""

from typing import TYPE_CHECKING, Dict

from sqlalchemy import ForeignKey, String, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .account import Account


class LLMModel(Base):
    """Stores LLM model configurations linked to an account."""

    __tablename__ = "llm_model"

    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(255), nullable=True)
    api_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Metadata stored as JSON (for custom fields, labels, etc.)
    meta_data: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="llm_models",
    )
