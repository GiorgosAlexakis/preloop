"""add_flow_executions_table

Revision ID: 5fd31a7ef8f2
Revises: 20250617145000
Create Date: 2025-06-10 19:47:55.384833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "5fd31a7ef8f2"
down_revision: Union[str, None] = "20250617145000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "flow_executions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("flow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_event_id", sa.String(), nullable=True),
        sa.Column(
            "trigger_event_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column(
            "start_time", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("resolved_input_prompt", sa.Text(), nullable=True),
        sa.Column("model_output_summary", sa.Text(), nullable=True),
        sa.Column(
            "actions_taken_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "mcp_usage_logs", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("openhands_session_reference", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        op.f("ix_flow_executions_flow_id"), "flow_executions", ["flow_id"], unique=False
    )
    op.create_index(
        op.f("ix_flow_executions_trigger_event_id"),
        "flow_executions",
        ["trigger_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_flow_executions_status"), "flow_executions", ["status"], unique=False
    )
    # Assuming 'flows' table exists and is managed by Alembic
    op.create_foreign_key(
        "fk_flow_executions_flow_id_flows",
        "flow_executions",
        "flows",
        ["flow_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_flow_executions_flow_id_flows", "flow_executions", type_="foreignkey"
    )
    op.drop_index(op.f("ix_flow_executions_status"), table_name="flow_executions")
    op.drop_index(
        op.f("ix_flow_executions_trigger_event_id"), table_name="flow_executions"
    )
    op.drop_index(op.f("ix_flow_executions_flow_id"), table_name="flow_executions")
    op.drop_table("flow_executions")
