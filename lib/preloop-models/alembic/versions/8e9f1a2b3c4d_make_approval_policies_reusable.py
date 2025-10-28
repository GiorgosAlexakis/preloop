"""make_approval_policies_reusable

Revision ID: 8e9f1a2b3c4d
Revises: 7a8b9c0d1e2f
Create Date: 2025-10-16 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8e9f1a2b3c4d"
down_revision: Union[str, None] = "7a8b9c0d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: make approval policies reusable across tools."""

    # Step 1: Add approval_policy_id to tool_configuration (nullable for now)
    op.add_column(
        "tool_configuration",
        sa.Column(
            "approval_policy_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Reference to approval policy (if requires_approval=True)",
        ),
    )

    # Step 2: Add new columns to approval_policy
    op.add_column(
        "approval_policy",
        sa.Column(
            "account_id",
            sa.String(36),
            nullable=True,  # Temporarily nullable for migration
            comment="The account this policy belongs to",
        ),
    )
    op.add_column(
        "approval_policy",
        sa.Column(
            "name",
            sa.String(255),
            nullable=True,  # Temporarily nullable for migration
            comment="Human-readable name for the policy",
        ),
    )
    op.add_column(
        "approval_policy",
        sa.Column(
            "description",
            sa.String(),
            nullable=True,
            comment="Optional description of what this policy does",
        ),
    )

    # Step 3: Migrate existing data
    # For each existing approval_policy, copy account_id from its tool_configuration
    # and set name to "Legacy Policy {id}"
    op.execute("""
        UPDATE approval_policy ap
        SET
            account_id = tc.account_id,
            name = 'Policy ' || SUBSTRING(ap.id::text FROM 1 FOR 8)
        FROM tool_configuration tc
        WHERE ap.tool_configuration_id = tc.id
    """)

    # Step 4: Copy approval_policy_id references to tool_configuration
    # For each tool that has an approval policy, set approval_policy_id
    op.execute("""
        UPDATE tool_configuration tc
        SET approval_policy_id = ap.id
        FROM approval_policy ap
        WHERE ap.tool_configuration_id = tc.id
    """)

    # Step 5: Make account_id and name NOT NULL now that we've migrated data
    op.alter_column("approval_policy", "account_id", nullable=False)
    op.alter_column("approval_policy", "name", nullable=False)

    # Step 6: Drop the old relationship columns and indexes
    op.drop_index(
        "ix_approval_policy_tool_configuration_id", table_name="approval_policy"
    )
    op.drop_constraint(
        "approval_policy_tool_configuration_id_fkey",
        "approval_policy",
        type_="foreignkey",
    )
    op.drop_column("approval_policy", "tool_configuration_id")

    # Step 7: Add new foreign key and indexes
    op.create_foreign_key(
        "fk_approval_policy_account_id",
        "approval_policy",
        "account",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "fk_tool_configuration_approval_policy_id",
        "tool_configuration",
        "approval_policy",
        ["approval_policy_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create indexes
    op.create_index(
        "ix_approval_policy_account_id",
        "approval_policy",
        ["account_id"],
    )
    op.create_index(
        "ix_approval_policy_name",
        "approval_policy",
        ["name"],
    )
    op.create_index(
        "ix_tool_configuration_approval_policy_id",
        "tool_configuration",
        ["approval_policy_id"],
    )

    # Step 8: Create unique constraint for policy names within account
    op.create_unique_constraint(
        "uq_account_policy_name",
        "approval_policy",
        ["account_id", "name"],
    )


def downgrade() -> None:
    """Downgrade schema: revert to 1-to-1 relationship."""

    # Drop new unique constraint
    op.drop_constraint("uq_account_policy_name", "approval_policy", type_="unique")

    # Drop new indexes
    op.drop_index(
        "ix_tool_configuration_approval_policy_id", table_name="tool_configuration"
    )
    op.drop_index("ix_approval_policy_name", table_name="approval_policy")
    op.drop_index("ix_approval_policy_account_id", table_name="approval_policy")

    # Drop new foreign keys
    op.drop_constraint(
        "fk_tool_configuration_approval_policy_id",
        "tool_configuration",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_approval_policy_account_id",
        "approval_policy",
        type_="foreignkey",
    )

    # Add back tool_configuration_id column
    op.add_column(
        "approval_policy",
        sa.Column(
            "tool_configuration_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,  # Nullable for migration
            comment="Reference to the tool configuration",
        ),
    )

    # Migrate data back: for tools with approval_policy_id, create a policy reference
    # This is lossy - we can only keep one tool per policy
    op.execute("""
        UPDATE approval_policy ap
        SET tool_configuration_id = (
            SELECT tc.id
            FROM tool_configuration tc
            WHERE tc.approval_policy_id = ap.id
            LIMIT 1
        )
    """)

    # Make tool_configuration_id NOT NULL and unique
    op.alter_column("approval_policy", "tool_configuration_id", nullable=False)

    # Recreate old foreign key and index
    op.create_foreign_key(
        "approval_policy_tool_configuration_id_fkey",
        "approval_policy",
        "tool_configuration",
        ["tool_configuration_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_approval_policy_tool_configuration_id",
        "approval_policy",
        ["tool_configuration_id"],
        unique=True,
    )

    # Drop new columns from approval_policy
    op.drop_column("approval_policy", "description")
    op.drop_column("approval_policy", "name")
    op.drop_column("approval_policy", "account_id")

    # Drop approval_policy_id from tool_configuration
    op.drop_column("tool_configuration", "approval_policy_id")
