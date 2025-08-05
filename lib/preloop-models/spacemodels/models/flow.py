import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, Text, JSON  # Added JSON

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import TimestampMixin


class Flow(Base, TimestampMixin):
    __tablename__ = "flow"

    id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )  # Changed from UUID
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    trigger_event_source = Column(String, nullable=False)
    trigger_event_type = Column(String, nullable=False)
    trigger_config = Column(JSON, nullable=True)  # Changed from JSONB
    prompt_template = Column(Text, nullable=False)
    ai_model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_model.id"),
        nullable=True,
    )
    openhands_agent_config = Column(JSON, nullable=False)  # Changed from JSONB
    allowed_mcp_servers = Column(
        JSON,
        nullable=False,
        default=[],  # Changed from JSONB
    )  # Assuming JSON Array of strings
    allowed_mcp_tools = Column(
        JSON,
        nullable=False,
        default=[],  # Changed from JSONB
    )  # Assuming JSON Array of objects
    is_preset = Column(Boolean, default=False, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(
        String(36),
        nullable=True,  # Changed from UUID
    )  # TODO: Add ForeignKeyConstraint to user.id when User model is finalized and available
    organization_id = Column(
        String(36),
        ForeignKey("organization.id"),
        nullable=False,  # Changed from UUID
    )

    organization = relationship("Organization")
    ai_model = relationship("AIModel", back_populates="flows")

    def __repr__(self) -> str:
        return f"<Flow(id={self.id}, name='{self.name}')>"
