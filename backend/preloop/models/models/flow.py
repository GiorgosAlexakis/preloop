from sqlalchemy import Boolean, Column, ForeignKey, String, Text, JSON  # Added JSON

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class Flow(Base):
    __tablename__ = "flow"

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    # For tracker triggers: source = tracker_id, type = event_type
    # For webhook triggers: source = 'webhook', type = 'webhook'
    trigger_event_source = Column(String, nullable=True)
    trigger_event_type = Column(String, nullable=True)
    trigger_organization_id = Column(
        String, nullable=True
    )  # Organization to scope trigger
    trigger_project_id = Column(String, nullable=True)  # Project to scope trigger
    trigger_config = Column(JSON, nullable=True)  # Changed from JSONB
    # Webhook-specific configuration
    # Structure: {
    #     "webhook_secret": str - secret token for authenticating webhook requests
    # }
    webhook_config = Column(JSON, nullable=True, default=None)
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

    # Git clone configuration for flows that need source code
    # Structure: {
    #     "enabled": bool,
    #     "repositories": [
    #         {
    #             "tracker_id": str,
    #             "project_id": str (optional),
    #             "repository_url": str (optional - uses project's default if not specified),
    #             "clone_path": str (relative path where to clone, default: "workspace"),
    #             "branch": str (optional - branch to clone, for backwards compatibility)
    #         }
    #     ],
    #     "git_user_name": str (default: "Preloop"),
    #     "git_user_email": str (default: "git@preloop.ai"),
    #     "source_branch": str (branch to checkout, default: "main"),
    #     "target_branch": str (branch to create for commits, optional - auto-generated if empty),
    #     "create_pull_request": bool (create PR/MR after commits, default: False),
    #     "pull_request_title": str (optional - title for PR/MR),
    #     "pull_request_description": str (optional - description for PR/MR)
    # }
    git_clone_config = Column(JSON, nullable=True, default=None)

    # Custom commands to run before agent starts (admin-only feature)
    # Security: Only users with is_superuser=True can configure this
    # Structure: {
    #     "enabled": bool,
    #     "commands": List[str] - list of shell commands to execute
    # }
    custom_commands = Column(JSON, nullable=True, default=None)

    is_preset = Column(Boolean, default=False, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    account_id = Column(
        UUID(as_uuid=True),
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
