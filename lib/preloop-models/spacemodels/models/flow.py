from sqlalchemy import Boolean, Column, ForeignKey, String, Text, JSON  # Added JSON

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import TimestampMixin


class Flow(Base, TimestampMixin):
    __tablename__ = "flow"

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    trigger_event_source = Column(String, nullable=False)
    trigger_event_type = Column(String, nullable=False)
    trigger_config = Column(JSON, nullable=True)  # Changed from JSONB
    prompt_template = Column(Text, nullable=False)
    ai_model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_model.id"),
        nullable=True,
    )
    agent_type = Column(String, nullable=False, default="openhands")
    agent_config = Column(JSON, nullable=False)  # Changed from JSONB
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
    account_id = Column(
        String(36),
        ForeignKey("account.id"),
        nullable=True,
        index=True,
    )

    ai_model = relationship("AIModel", back_populates="flows")
    account = relationship("Account", back_populates="flows", foreign_keys=[account_id])
    executions = relationship(
        "FlowExecution", back_populates="flow", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Flow(id={self.id}, name='{self.name}')>"
