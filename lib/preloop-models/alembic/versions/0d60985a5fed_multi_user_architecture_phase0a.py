"""multi_user_architecture_phase0a

Revision ID: 0d60985a5fed
Revises: d9e4194ea296
Create Date: 2025-10-30 14:38:40.640304

This migration transforms SpaceBridge from a single-user to multi-user
account architecture. It:
1. Creates User, Permission, Role, and related tables
2. Creates TeamMembership table (replaces TeamMember)
3. Creates UserInvitation table for email invitations
4. Updates Account model (removes user fields, adds org fields)
5. Updates ApiKey model (changes FK from username to user_id)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0d60985a5fed"
down_revision: Union[str, None] = "d9e4194ea296"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to multi-user architecture."""

    # Step 1: Create user table
    op.create_table(
        "user",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier for the user",
        ),
        sa.Column(
            "account_id",
            sa.String(length=36),
            nullable=False,
            comment="The account this user belongs to",
        ),
        sa.Column(
            "username",
            sa.String(length=255),
            nullable=False,
            comment="Unique username",
        ),
        sa.Column(
            "email",
            sa.String(length=255),
            nullable=False,
            comment="User's email address",
        ),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether the email has been verified",
        ),
        sa.Column(
            "full_name",
            sa.String(length=255),
            nullable=True,
            comment="User's full name",
        ),
        sa.Column(
            "hashed_password",
            sa.String(length=255),
            nullable=True,
            comment="Hashed password (null for external auth)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Whether the user account is active",
        ),
        sa.Column(
            "user_source",
            sa.String(length=50),
            nullable=False,
            server_default="'local'",
            comment="Source of authentication: 'local', 'ldap', 'ad', 'saml', 'oauth'",
        ),
        sa.Column(
            "oauth_provider",
            sa.String(length=50),
            nullable=True,
            comment="OAuth provider if user_source is 'oauth'",
        ),
        sa.Column(
            "oauth_id",
            sa.String(length=255),
            nullable=True,
            comment="OAuth provider's user ID",
        ),
        sa.Column(
            "external_id",
            sa.String(length=255),
            nullable=True,
            comment="External system's user ID (for LDAP/AD/SAML)",
        ),
        sa.Column(
            "last_login",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the user last logged in",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the user was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the user was last updated",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_account_id"), "user", ["account_id"])
    op.create_index(op.f("ix_user_email"), "user", ["email"])
    op.create_index(op.f("ix_user_external_id"), "user", ["external_id"])
    op.create_index(op.f("ix_user_user_source"), "user", ["user_source"])
    op.create_index(op.f("ix_user_username"), "user", ["username"], unique=True)

    # Step 2: Create permission table
    op.create_table(
        "permission",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier for the permission",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="Unique permission name",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            comment="Description of what this permission allows",
        ),
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
            comment="Category for grouping permissions",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Whether permission is active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the permission was created",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permission_category"), "permission", ["category"])
    op.create_index(op.f("ix_permission_name"), "permission", ["name"], unique=True)

    # Step 3: Create role table
    op.create_table(
        "role",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier for the role",
        ),
        sa.Column(
            "account_id",
            sa.String(length=36),
            nullable=True,
            comment="Account this role belongs to (null for system roles)",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="Role name",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Description of what this role allows",
        ),
        sa.Column(
            "is_system_role",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether this is a system-defined role",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the role was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the role was last updated",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "name", name="uq_account_role_name"),
    )
    op.create_index(op.f("ix_role_account_id"), "role", ["account_id"])
    op.create_index(op.f("ix_role_is_system_role"), "role", ["is_system_role"])
    op.create_index(op.f("ix_role_name"), "role", ["name"])

    # Step 4: Create role_permission table
    op.create_table(
        "role_permission",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the role",
        ),
        sa.Column(
            "permission_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the permission",
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When this permission was granted",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permission.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index(
        op.f("ix_role_permission_permission_id"), "role_permission", ["permission_id"]
    )
    op.create_index(op.f("ix_role_permission_role_id"), "role_permission", ["role_id"])

    # Step 5: Create user_role table
    op.create_table(
        "user_role",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the user",
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the role",
        ),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who granted this role",
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the role was granted",
        ),
        sa.ForeignKeyConstraint(["granted_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
    op.create_index(op.f("ix_user_role_role_id"), "user_role", ["role_id"])
    op.create_index(op.f("ix_user_role_user_id"), "user_role", ["user_id"])

    # Step 6: Create team_role table
    op.create_table(
        "team_role",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the team",
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the role",
        ),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who granted this role",
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the role was granted",
        ),
        sa.ForeignKeyConstraint(["granted_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "role_id", name="uq_team_role"),
    )
    op.create_index(op.f("ix_team_role_role_id"), "team_role", ["role_id"])
    op.create_index(op.f("ix_team_role_team_id"), "team_role", ["team_id"])

    # Step 7: Create team_membership table (replaces team_member)
    op.create_table(
        "team_membership",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier for the membership",
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the team",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the user",
        ),
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=True,
            comment="Optional role within the team (e.g., 'member', 'lead')",
        ),
        sa.Column(
            "added_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who added this member",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the user was added to the team",
        ),
        sa.ForeignKeyConstraint(["added_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )
    op.create_index(op.f("ix_team_membership_team_id"), "team_membership", ["team_id"])
    op.create_index(op.f("ix_team_membership_user_id"), "team_membership", ["user_id"])

    # Step 8: Create user_invitation table
    op.create_table(
        "user_invitation",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Unique identifier for the invitation",
        ),
        sa.Column(
            "account_id",
            sa.String(length=36),
            nullable=False,
            comment="The account the user is being invited to",
        ),
        sa.Column(
            "email",
            sa.String(length=255),
            nullable=False,
            comment="Email address of the invitee",
        ),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="User who sent the invitation",
        ),
        sa.Column(
            "token",
            sa.String(length=64),
            nullable=False,
            comment="Secure token for the invitation link",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="'pending'",
            comment="Current status of the invitation",
        ),
        sa.Column(
            "role_ids",
            sa.String(length=500),
            nullable=True,
            comment="Comma-separated role UUIDs to assign on acceptance",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the invitation was created",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the invitation expires",
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the invitation was accepted",
        ),
        sa.Column(
            "accepted_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User created when invitation was accepted",
        ),
        sa.ForeignKeyConstraint(["accepted_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_invitation_account_id"), "user_invitation", ["account_id"]
    )
    op.create_index(op.f("ix_user_invitation_email"), "user_invitation", ["email"])
    op.create_index(op.f("ix_user_invitation_status"), "user_invitation", ["status"])
    op.create_index(
        op.f("ix_user_invitation_token"), "user_invitation", ["token"], unique=True
    )

    # Step 9: Drop old team_member table (if exists)
    # Note: This table was created in previous migration but is now replaced by team_membership
    op.drop_table("team_member")

    # Step 10: Alter account table - add new fields first
    op.add_column(
        "account",
        sa.Column(
            "organization_name",
            sa.String(length=255),
            nullable=True,
            comment="Display name for the organization",
        ),
    )
    op.add_column(
        "account",
        sa.Column(
            "primary_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="The account owner/creator",
        ),
    )
    op.create_foreign_key(
        "fk_account_primary_user",
        "account",
        "user",
        ["primary_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Step 11: Alter api_key table - add user_id column
    op.add_column(
        "api_key",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,  # Temporarily nullable for migration
            comment="The user who created this API key",
        ),
    )
    op.create_index(op.f("ix_api_key_user_id"), "api_key", ["user_id"])

    # Note: Steps 12-14 below require a data migration to populate user table
    # and update api_key.user_id and account.primary_user_id.
    # These will be executed in a separate data migration script.

    # Step 12: After data migration, make user_id NOT NULL and drop old created_by
    # This will be done in downgrade by making created_by nullable again

    # Step 13: After data migration, drop old account user fields
    # These columns will be dropped after ensuring all data is migrated


def downgrade() -> None:
    """Downgrade schema from multi-user to single-user architecture."""

    # Note: This downgrade does NOT restore data - it only drops the new tables
    # and restores the old schema. A separate data migration would be needed
    # to restore single-user account data.

    # Remove foreign key from account.primary_user_id
    op.drop_constraint("fk_account_primary_user", "account", type_="foreignkey")

    # Remove new account columns
    op.drop_column("account", "primary_user_id")
    op.drop_column("account", "organization_name")

    # Remove user_id from api_key and restore created_by
    op.drop_index(op.f("ix_api_key_user_id"), table_name="api_key")
    op.drop_column("api_key", "user_id")

    # Recreate team_member table (simple version)
    op.create_table(
        "team_member",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Drop new tables in reverse order
    op.drop_table("user_invitation")
    op.drop_table("team_membership")
    op.drop_table("team_role")
    op.drop_table("user_role")
    op.drop_table("role_permission")
    op.drop_table("role")
    op.drop_table("permission")
    op.drop_table("user")
