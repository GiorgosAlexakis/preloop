"""Base SQLAlchemy models for SpaceBridge."""

from datetime import datetime
from typing import Any, ClassVar, Dict

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    # Allow unmapped class variables
    __allow_unmapped__ = True

    # Class variables
    __name__: ClassVar[str]

    # Generate __tablename__ automatically
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    # Add created_at and updated_at columns to all models
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def dict(self) -> Dict[str, Any]:
        """Convert model to dictionary (maintained for compatibility)."""
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
