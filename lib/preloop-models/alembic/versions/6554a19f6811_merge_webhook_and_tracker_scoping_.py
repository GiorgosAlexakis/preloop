"""merge webhook and tracker scoping branches

Revision ID: 6554a19f6811
Revises: dbd4003e5eef, 20250617145000
Create Date: 2025-06-25 17:20:30.335541

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "6554a19f6811"
down_revision: Union[str, None] = ("dbd4003e5eef", "20250617145000")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
