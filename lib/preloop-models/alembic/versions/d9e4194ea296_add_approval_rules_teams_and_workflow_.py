"""add_approval_rules_teams_and_workflow_fields

Revision ID: d9e4194ea296
Revises: 5ddda083abc0
Create Date: 2025-10-30 12:52:35.411953

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d9e4194ea296"
down_revision: Union[str, None] = "5ddda083abc0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create team table
    op.create_table(
        "team",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier for the team",
        ),
        sa.Column(
            "account_id",
            sa.String(length=36),
            nullable=False,
            comment="The account this team belongs to",
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
            comment="Human-readable name for the team",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional description of the team's purpose",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the team was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the team was last modified",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "name", name="uq_account_team_name"),
    )
    op.create_index(op.f("ix_team_account_id"), "team", ["account_id"], unique=False)
    op.create_index(op.f("ix_team_name"), "team", ["name"], unique=False)

    # Create team_member table
    op.create_table(
        "team_member",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier for the team membership",
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the team",
        ),
        sa.Column(
            "account_id",
            sa.String(length=36),
            nullable=False,
            comment="The account this membership belongs to",
        ),
        sa.Column(
            "user_email",
            sa.String(length=255),
            nullable=False,
            comment="Email of the user/approver",
        ),
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=True,
            comment="Optional role within the team (e.g., 'member', 'lead')",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the user was added to the team",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "user_email", name="uq_team_user_email"),
    )
    op.create_index(
        op.f("ix_team_member_account_id"), "team_member", ["account_id"], unique=False
    )
    op.create_index(
        op.f("ix_team_member_team_id"), "team_member", ["team_id"], unique=False
    )
    op.create_index(
        op.f("ix_team_member_user_email"), "team_member", ["user_email"], unique=False
    )

    # Create approval_rule table
    op.create_table(
        "approval_rule",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier for the approval rule",
        ),
        sa.Column(
            "account_id",
            sa.String(length=36),
            nullable=False,
            comment="The account this rule belongs to",
        ),
        sa.Column(
            "tool_configuration_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the tool configuration",
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
            comment="Human-readable name for the rule",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional description of what this rule does",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Whether the rule is currently active",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Order of evaluation (lower = higher priority)",
        ),
        sa.Column(
            "condition_type",
            sa.String(length=50),
            nullable=False,
            server_default="argument",
            comment="Type of condition evaluator: 'argument', 'state', 'risk'",
        ),
        sa.Column(
            "condition_config",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            comment="Configuration for the condition evaluator (e.g., CEL expression)",
        ),
        sa.Column(
            "approval_policy_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to approval policy when condition matches",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the rule was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the rule was last modified",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["approval_policy_id"], ["approval_policy.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tool_configuration_id"], ["tool_configuration.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_approval_rule_account_id"),
        "approval_rule",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_rule_condition_type"),
        "approval_rule",
        ["condition_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_rule_is_enabled"),
        "approval_rule",
        ["is_enabled"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_rule_name"), "approval_rule", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_approval_rule_priority"), "approval_rule", ["priority"], unique=False
    )
    op.create_index(
        op.f("ix_approval_rule_tool_configuration_id"),
        "approval_rule",
        ["tool_configuration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_rule_approval_policy_id"),
        "approval_rule",
        ["approval_policy_id"],
        unique=False,
    )

    # Add workflow_type and workflow_config columns to approval_policy table
    op.add_column(
        "approval_policy",
        sa.Column(
            "workflow_type",
            sa.String(length=50),
            nullable=False,
            server_default="simple",
            comment="Type of approval workflow: 'simple', 'multi_stage', 'consensus'",
        ),
    )
    op.add_column(
        "approval_policy",
        sa.Column(
            "workflow_config",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment="Configuration for the approval workflow (stages, teams, voting rules)",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop workflow columns from approval_policy table
    op.drop_column("approval_policy", "workflow_config")
    op.drop_column("approval_policy", "workflow_type")

    # Drop approval_rule table
    op.drop_index(
        op.f("ix_approval_rule_approval_policy_id"), table_name="approval_rule"
    )
    op.drop_index(
        op.f("ix_approval_rule_tool_configuration_id"), table_name="approval_rule"
    )
    op.drop_index(op.f("ix_approval_rule_priority"), table_name="approval_rule")
    op.drop_index(op.f("ix_approval_rule_name"), table_name="approval_rule")
    op.drop_index(op.f("ix_approval_rule_is_enabled"), table_name="approval_rule")
    op.drop_index(op.f("ix_approval_rule_condition_type"), table_name="approval_rule")
    op.drop_index(op.f("ix_approval_rule_account_id"), table_name="approval_rule")
    op.drop_table("approval_rule")

    # Drop team_member table
    op.drop_index(op.f("ix_team_member_user_email"), table_name="team_member")
    op.drop_index(op.f("ix_team_member_team_id"), table_name="team_member")
    op.drop_index(op.f("ix_team_member_account_id"), table_name="team_member")
    op.drop_table("team_member")

    # Drop team table
    op.drop_index(op.f("ix_team_name"), table_name="team")
    op.drop_index(op.f("ix_team_account_id"), table_name="team")
    op.drop_table("team")
