"""Issue, EmbeddingModel, and IssueEmbedding models."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime, JSON


# Check if our vector type module is available
try:
    from ..db.vector_types import VectorType  # noqa: F401

    VECTOR_TYPE_AVAILABLE = True
except ImportError:
    VECTOR_TYPE_AVAILABLE = False

from .base import Base

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .project import Project
    from .tracker import Tracker


class Issue(Base):
    """Issue model - represents a task, bug, or feature in a project."""

    # Issue details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False, default="task")

    # External issue identifiers
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Foreign keys
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tracker_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tracker.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="issues")
    tracker: Mapped["Tracker"] = relationship("Tracker", back_populates="issues")
    embeddings: Mapped[List["IssueEmbedding"]] = relationship(
        "IssueEmbedding", back_populates="issue", cascade="all, delete-orphan"
    )

    # Metadata stored as JSON (for custom fields, labels, etc.)
    meta_data: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    # Timestamps for issue-specific events
    last_updated_external: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EmbeddingModel(Base):
    """Model to track different embedding models used in the system."""

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )

    # Embedding model details
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # 'openai', 'google', etc.
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Additional embedding model properties
    meta_data: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    embeddings: Mapped[List["IssueEmbedding"]] = relationship(
        "IssueEmbedding", back_populates="embedding_model"
    )

    __table_args__ = (
        # Enforce unique composite key for provider+version
        UniqueConstraint("provider", "version", name="uix_provider_version"),
    )


class IssueEmbedding(Base):
    """Model to store embeddings for issues.

    This flexible design supports embeddings of different dimensions.
    """

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )

    # Foreign keys
    issue_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("issue.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("embeddingmodel.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The actual embedding vector (PostgreSQL vector type)
    # Use JSON type for now to ensure compatibility
    embedding: Mapped[Dict] = mapped_column(
        JSON, nullable=False, comment="Embedding vector, stored as JSON array"
    )

    # Metadata about how this embedding was created
    meta_data: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)

    # When this embedding was created
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="embeddings")
    embedding_model: Mapped["EmbeddingModel"] = relationship(
        "EmbeddingModel", back_populates="embeddings"
    )

    __table_args__ = (
        # Enforce one embedding per issue per model
        UniqueConstraint(
            "issue_id", "embedding_model_id", name="uix_issue_embedding_model"
        ),
    )


# Event listener to set the embedding column type - commented out for now
# @event.listens_for(IssueEmbedding, 'instrument_class')
# def set_embedding_type(mapper, cls):
#     """Set the correct type for the embedding column based on environment."""
#     if VECTOR_TYPE_AVAILABLE:
#         # Query the embedding model to get dimensions - default to 1536 if not found
#         default_dimensions = 1536
#         embedding_column = cls.__table__.c.embedding
#
#         # Use our custom VectorType
#         embedding_column.type = VectorType(dimensions=default_dimensions)
