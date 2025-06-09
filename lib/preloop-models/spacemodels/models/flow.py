import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import TimestampMixin


class Flow(Base, TimestampMixin):
    __tablename__ = "flow"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    trigger_event_source = Column(String, nullable=False)
    trigger_event_type = Column(String, nullable=False)
    trigger_config = Column(JSONB, nullable=True)
    prompt_template = Column(Text, nullable=False)
    model_configuration_id = Column(
        UUID(as_uuid=True), nullable=True
    )  # TODO: Add ForeignKeyConstraint to model_configuration.id when ModelConfiguration model is created (Issue #60)
    openhands_agent_config = Column(JSONB, nullable=False)
    allowed_mcp_servers = Column(
        JSONB, nullable=False, default=[]
    )  # Assuming JSON Array of strings
    allowed_mcp_tools = Column(
        JSONB, nullable=False, default=[]
    )  # Assuming JSON Array of objects
    is_preset = Column(Boolean, default=False, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(
        UUID(as_uuid=True), nullable=True
    )  # TODO: Add ForeignKeyConstraint to user.id when User model is finalized and available
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False
    )

    organization = relationship("Organization")

    def __repr__(self) -> str:
        return f"<Flow(id={self.id}, name='{self.name}')>"
