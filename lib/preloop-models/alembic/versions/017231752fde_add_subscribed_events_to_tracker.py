"""add_subscribed_events_to_tracker

Revision ID: 017231752fde
Revises: 4e94694b4381
Create Date: 2025-06-08 15:07:19.730417

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "017231752fde"
down_revision: Union[str, None] = "4e94694b4381"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tracker",
        sa.Column(
            "subscribed_events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
            comment="List of specific webhook event names to subscribe to (e.g., ['push', 'issues']). Empty or None might imply default/all events based on client logic.",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tracker", "subscribed_events")
