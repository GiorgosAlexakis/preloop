"""merge approval policy branches

Revision ID: 9f557696858b
Revises: 0be6b535384a, 8e9f1a2b3c4d
Create Date: 2025-10-16 01:15:56.404393

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "9f557696858b"
down_revision: Union[str, None] = ("0be6b535384a", "8e9f1a2b3c4d")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
