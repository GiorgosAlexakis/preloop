"""rename_openhands_fields_to_agent_fields

Revision ID: 97d779394715
Revises: 98b2c8291a52
Create Date: 2025-10-07 06:21:40.237291

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "97d779394715"
down_revision: Union[str, None] = "98b2c8291a52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: rename OpenHands-specific fields to generic agent fields."""
    # Add agent_type column to flow table with default value 'openhands'
    op.add_column(
        "flow",
        sa.Column(
            "agent_type", sa.String(), nullable=False, server_default="openhands"
        ),
    )

    # Rename openhands_agent_config to agent_config in flow table
    op.alter_column("flow", "openhands_agent_config", new_column_name="agent_config")

    # Rename openhands_session_reference to agent_session_reference in flow_execution table
    op.alter_column(
        "flow_execution",
        "openhands_session_reference",
        new_column_name="agent_session_reference",
    )


def downgrade() -> None:
    """Downgrade schema: revert agent fields to OpenHands-specific names."""
    # Rename agent_session_reference back to openhands_session_reference in flow_execution table
    op.alter_column(
        "flow_execution",
        "agent_session_reference",
        new_column_name="openhands_session_reference",
    )

    # Rename agent_config back to openhands_agent_config in flow table
    op.alter_column("flow", "agent_config", new_column_name="openhands_agent_config")

    # Drop agent_type column from flow table
    op.drop_column("flow", "agent_type")
