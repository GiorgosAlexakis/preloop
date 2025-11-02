"""Data migration script for multi-user architecture.

This script performs the data migration from single-user to multi-user
accounts. It must be run AFTER the Alembic schema migration.

Steps:
1. Create system roles and permissions
2. For each Account, create a User with the account's credentials
3. Assign Owner role to each created user
4. Update ApiKey records to reference the new user_id
5. Update Account.primary_user_id to the created user
6. Drop old user-specific columns from Account table
7. Make api_key.user_id NOT NULL and drop created_by column

Usage:
    python -m spacemodels.scripts.migrate_to_multi_user

Environment variables:
    DATABASE_URL: PostgreSQL connection string
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from spacemodels.models import (
    Permission,
    Role,
    RolePermission,
)


# System roles and their permissions
SYSTEM_ROLES = {
    "owner": {
        "description": "Full access including billing, user management, and account closure",
        "permissions": [
            "manage_billing",
            "view_billing",
            "manage_users",
            "invite_users",
            "view_users",
            "create_flows",
            "edit_flows",
            "delete_flows",
            "execute_flows",
            "view_flows",
            "create_tools",
            "edit_tools",
            "delete_tools",
            "execute_tools",
            "view_tools",
            "create_trackers",
            "edit_trackers",
            "delete_trackers",
            "sync_trackers",
            "view_trackers",
            "manage_teams",
            "view_teams",
            "manage_projects",
            "view_projects",
            "use_compliance",
            "use_dependencies",
            "use_duplicates",
            "manage_account",
            "close_account",
        ],
    },
    "admin": {
        "description": "Full access except billing and account closure",
        "permissions": [
            "view_billing",
            "manage_users",
            "invite_users",
            "view_users",
            "create_flows",
            "edit_flows",
            "delete_flows",
            "execute_flows",
            "view_flows",
            "create_tools",
            "edit_tools",
            "delete_tools",
            "execute_tools",
            "view_tools",
            "create_trackers",
            "edit_trackers",
            "delete_trackers",
            "sync_trackers",
            "view_trackers",
            "manage_teams",
            "view_teams",
            "manage_projects",
            "view_projects",
            "use_compliance",
            "use_dependencies",
            "use_duplicates",
            "manage_account",
        ],
    },
    "editor": {
        "description": "Create/edit flows, tools, trackers, and projects",
        "permissions": [
            "create_flows",
            "edit_flows",
            "delete_flows",
            "view_flows",
            "create_tools",
            "edit_tools",
            "delete_tools",
            "view_tools",
            "create_trackers",
            "edit_trackers",
            "delete_trackers",
            "sync_trackers",
            "view_trackers",
            "manage_projects",
            "view_projects",
            "use_compliance",
            "use_dependencies",
            "use_duplicates",
        ],
    },
    "executor": {
        "description": "Execute flows and tools",
        "permissions": [
            "execute_flows",
            "view_flows",
            "execute_tools",
            "view_tools",
            "view_trackers",
            "view_projects",
        ],
    },
    "tracker_manager": {
        "description": "Add/edit trackers and sync data",
        "permissions": [
            "create_trackers",
            "edit_trackers",
            "delete_trackers",
            "sync_trackers",
            "view_trackers",
            "view_projects",
        ],
    },
    "analyst": {
        "description": "Read-only access plus analytics tools",
        "permissions": [
            "view_flows",
            "view_tools",
            "view_trackers",
            "view_projects",
            "view_teams",
            "use_compliance",
            "use_dependencies",
            "use_duplicates",
        ],
    },
    "viewer": {
        "description": "Read-only access to all resources",
        "permissions": [
            "view_flows",
            "view_tools",
            "view_trackers",
            "view_projects",
            "view_teams",
        ],
    },
}

# Permission definitions by category
PERMISSIONS = {
    "billing": [
        ("manage_billing", "Manage billing and subscriptions"),
        ("view_billing", "View billing information"),
    ],
    "users": [
        ("manage_users", "Manage users (create, edit, delete, assign roles)"),
        ("invite_users", "Invite new users to the account"),
        ("view_users", "View users in the account"),
    ],
    "flows": [
        ("create_flows", "Create new flows"),
        ("edit_flows", "Edit existing flows"),
        ("delete_flows", "Delete flows"),
        ("execute_flows", "Execute flows"),
        ("view_flows", "View flows"),
    ],
    "tools": [
        ("create_tools", "Create new tools"),
        ("edit_tools", "Edit existing tools"),
        ("delete_tools", "Delete tools"),
        ("execute_tools", "Execute tools"),
        ("view_tools", "View tools"),
    ],
    "trackers": [
        ("create_trackers", "Create new trackers"),
        ("edit_trackers", "Edit existing trackers"),
        ("delete_trackers", "Delete trackers"),
        ("sync_trackers", "Sync tracker data"),
        ("view_trackers", "View trackers"),
    ],
    "teams": [
        ("manage_teams", "Manage teams (create, edit, delete, assign roles)"),
        ("view_teams", "View teams"),
    ],
    "projects": [
        ("manage_projects", "Manage projects"),
        ("view_projects", "View projects"),
    ],
    "analytics": [
        ("use_compliance", "Use compliance analysis tools"),
        ("use_dependencies", "Use dependency analysis tools"),
        ("use_duplicates", "Use duplicate detection tools"),
    ],
    "account": [
        ("manage_account", "Manage account settings"),
        ("close_account", "Close/delete the account"),
    ],
}


def create_permissions(session: Session) -> Dict[str, uuid.UUID]:
    """Create all permission definitions.

    Returns:
        Dict mapping permission name to permission ID
    """
    print("Creating permissions...")
    permission_ids = {}

    for category, perms in PERMISSIONS.items():
        for perm_name, perm_description in perms:
            # Check if permission already exists
            existing = session.query(Permission).filter_by(name=perm_name).first()
            if existing:
                print(f"  Permission '{perm_name}' already exists, skipping...")
                permission_ids[perm_name] = existing.id
                continue

            perm = Permission(
                id=uuid.uuid4(),
                name=perm_name,
                description=perm_description,
                category=category,
                is_active=True,
            )
            session.add(perm)
            permission_ids[perm_name] = perm.id
            print(f"  Created permission: {perm_name} ({category})")

    session.commit()
    return permission_ids


def create_system_roles(
    session: Session, permission_ids: Dict[str, uuid.UUID]
) -> Dict[str, uuid.UUID]:
    """Create system roles with their permissions.

    Returns:
        Dict mapping role name to role ID
    """
    print("\nCreating system roles...")
    role_ids = {}

    for role_name, role_info in SYSTEM_ROLES.items():
        # Check if role already exists
        existing = (
            session.query(Role).filter_by(name=role_name, is_system_role=True).first()
        )
        if existing:
            print(f"  System role '{role_name}' already exists, skipping...")
            role_ids[role_name] = existing.id
            continue

        role = Role(
            id=uuid.uuid4(),
            account_id=None,  # System role
            name=role_name,
            description=role_info["description"],
            is_system_role=True,
        )
        session.add(role)
        role_ids[role_name] = role.id
        print(f"  Created system role: {role_name}")

        # Assign permissions to role
        for perm_name in role_info["permissions"]:
            perm_id = permission_ids.get(perm_name)
            if not perm_id:
                print(
                    f"    WARNING: Permission '{perm_name}' not found for role '{role_name}'"
                )
                continue

            role_perm = RolePermission(
                id=uuid.uuid4(),
                role_id=role.id,
                permission_id=perm_id,
            )
            session.add(role_perm)
        print(
            f"    Assigned {len(role_info['permissions'])} permissions to {role_name}"
        )

    session.commit()
    return role_ids


def migrate_accounts_to_users(
    session: Session, owner_role_id: uuid.UUID
) -> Dict[str, uuid.UUID]:
    """Migrate Account data to User model.

    For each Account:
    1. Create a User with the account's credentials
    2. Assign Owner role to the user
    3. Update Account.primary_user_id

    Returns:
        Dict mapping account.id to user.id
    """
    print("\nMigrating accounts to users...")
    account_to_user = {}

    # Get all accounts with their user fields
    accounts = session.execute(
        text("""
            SELECT id, username, email, email_verified, full_name,
                   hashed_password, is_active, oauth_provider, oauth_id
            FROM account
        """)
    ).fetchall()

    print(f"Found {len(accounts)} accounts to migrate")

    for account in accounts:
        account_id = account[0]
        username = account[1]
        email = account[2]
        email_verified = account[3]
        full_name = account[4]
        hashed_password = account[5]
        is_active = account[6]
        oauth_provider = account[7]
        oauth_id = account[8]

        # Determine user_source
        user_source = "local"
        if oauth_provider:
            user_source = "oauth"

        # Create user
        user_id = uuid.uuid4()
        session.execute(
            text("""
                INSERT INTO "user"
                (id, account_id, username, email, email_verified, full_name,
                 hashed_password, is_active, user_source, oauth_provider, oauth_id,
                 created_at, updated_at)
                VALUES
                (:id, :account_id, :username, :email, :email_verified, :full_name,
                 :hashed_password, :is_active, :user_source, :oauth_provider, :oauth_id,
                 :created_at, :updated_at)
            """),
            {
                "id": user_id,
                "account_id": account_id,
                "username": username,
                "email": email,
                "email_verified": email_verified,
                "full_name": full_name,
                "hashed_password": hashed_password,
                "is_active": is_active,
                "user_source": user_source,
                "oauth_provider": oauth_provider,
                "oauth_id": oauth_id,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )

        # Assign Owner role
        session.execute(
            text("""
                INSERT INTO user_role (id, user_id, role_id, granted_at)
                VALUES (:id, :user_id, :role_id, :granted_at)
            """),
            {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "role_id": owner_role_id,
                "granted_at": datetime.now(timezone.utc),
            },
        )

        # Update Account.primary_user_id
        session.execute(
            text("""
                UPDATE account
                SET primary_user_id = :user_id
                WHERE id = :account_id
            """),
            {"user_id": user_id, "account_id": account_id},
        )

        account_to_user[account_id] = user_id
        print(f"  Created user {username} for account {account_id}")

    session.commit()
    return account_to_user


def migrate_api_keys(session: Session, account_to_user: Dict[str, uuid.UUID]) -> None:
    """Migrate ApiKey records from created_by (username) to user_id.

    Args:
        account_to_user: Dict mapping account.id to user.id
    """
    print("\nMigrating API keys...")

    # Get all API keys with their creator's account
    api_keys = session.execute(
        text("""
            SELECT ak.id, ak.created_by, a.id as account_id
            FROM api_key ak
            JOIN account a ON a.username = ak.created_by
        """)
    ).fetchall()

    print(f"Found {len(api_keys)} API keys to migrate")

    for api_key in api_keys:
        api_key_id = api_key[0]
        account_id = api_key[2]
        user_id = account_to_user.get(account_id)

        if not user_id:
            print(
                f"  WARNING: No user found for account {account_id}, skipping API key {api_key_id}"
            )
            continue

        # Update api_key.user_id
        session.execute(
            text("""
                UPDATE api_key
                SET user_id = :user_id
                WHERE id = :api_key_id
            """),
            {"user_id": user_id, "api_key_id": api_key_id},
        )

    session.commit()
    print(f"  Migrated {len(api_keys)} API keys")


def finalize_schema_changes(session: Session) -> None:
    """Finalize schema changes after data migration.

    1. Make api_key.user_id NOT NULL
    2. Drop api_key.created_by column
    3. Drop old Account user fields
    """
    print("\nFinalizing schema changes...")

    # Make api_key.user_id NOT NULL
    print("  Making api_key.user_id NOT NULL...")
    session.execute(text("ALTER TABLE api_key ALTER COLUMN user_id SET NOT NULL"))

    # Add foreign key constraint to api_key.user_id
    print("  Adding foreign key constraint to api_key.user_id...")
    session.execute(
        text("""
            ALTER TABLE api_key
            ADD CONSTRAINT fk_api_key_user
            FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE
        """)
    )

    # Drop api_key.created_by column
    print("  Dropping api_key.created_by column...")
    session.execute(text("ALTER TABLE api_key DROP COLUMN created_by"))

    # Drop old Account user fields
    print("  Dropping old Account user fields...")
    session.execute(text("ALTER TABLE account DROP COLUMN IF EXISTS username"))
    session.execute(text("ALTER TABLE account DROP COLUMN IF EXISTS hashed_password"))
    session.execute(text("ALTER TABLE account DROP COLUMN IF EXISTS full_name"))
    session.execute(text("ALTER TABLE account DROP COLUMN IF EXISTS oauth_provider"))
    session.execute(text("ALTER TABLE account DROP COLUMN IF EXISTS oauth_id"))

    session.commit()
    print("  Schema finalization complete")


def main():
    """Run the data migration."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    print("Connecting to database...")
    engine = create_engine(database_url)
    session = Session(engine)

    try:
        print("\n" + "=" * 60)
        print("Multi-User Architecture Data Migration")
        print("=" * 60)

        # Step 1: Create permissions
        permission_ids = create_permissions(session)

        # Step 2: Create system roles
        role_ids = create_system_roles(session, permission_ids)

        # Step 3: Migrate accounts to users
        owner_role_id = role_ids["owner"]
        account_to_user = migrate_accounts_to_users(session, owner_role_id)

        # Step 4: Migrate API keys
        migrate_api_keys(session, account_to_user)

        # Step 5: Finalize schema changes
        finalize_schema_changes(session)

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print("\nSummary:")
        print(f"  - Created {len(permission_ids)} permissions")
        print(f"  - Created {len(role_ids)} system roles")
        print(f"  - Migrated {len(account_to_user)} accounts to users")
        print("  - All users assigned Owner role")
        print("  - API keys updated with user references")
        print("  - Schema finalized")

    except Exception as e:
        print(f"\nERROR during migration: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
