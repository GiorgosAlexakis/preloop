#!/usr/bin/env python3
"""
Script to sync flow presets for accounts.

Usage:
    # Sync presets for all accounts
    python scripts/sync_flow_presets.py

    # Sync presets for a specific account by email
    python scripts/sync_flow_presets.py --email user@example.com

    # Sync presets for a specific account by ID
    python scripts/sync_flow_presets.py --account-id <uuid>

    # Dry run (no changes)
    python scripts/sync_flow_presets.py --dry-run
"""

import argparse
import logging
import sys
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from spacemodels.db.session import get_db_session
from spacemodels.crud.account import CRUDAccount
from spacemodels.crud.flow import CRUDFlow
from spacemodels.models.account import Account
from spacemodels.models.flow import Flow
from spacemodels import schemas
from spacebridge.flow_presets import FLOW_PRESETS

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def sync_presets_for_account(
    db: Session,
    account_id: UUID,
    account_email: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """
    Sync flow presets for a specific account.

    Args:
        db: Database session
        account_id: Account ID to sync presets for
        account_email: Email for logging purposes (optional)
        dry_run: If True, only log what would be done without making changes

    Returns:
        Number of presets synced/updated
    """
    crud_flow = CRUDFlow(Flow)
    changes_count = 0

    account_label = account_email or str(account_id)
    logger.info(f"Processing account: {account_label}")

    # Get existing presets for this account
    existing_flows = crud_flow.get_multi(db, account_id=account_id, skip=0, limit=1000)
    existing_preset_names = {
        flow.name: flow for flow in existing_flows if flow.is_preset
    }

    logger.info(f"  Found {len(existing_preset_names)} existing presets")

    # Process each preset definition
    for preset_def in FLOW_PRESETS:
        preset_name = preset_def["name"]
        existing_flow = existing_preset_names.get(preset_name)

        if existing_flow:
            # Check if preset needs updating
            needs_update = False
            update_fields = []

            # Compare key fields that might have changed
            if existing_flow.description != preset_def.get("description"):
                needs_update = True
                update_fields.append("description")
            if existing_flow.icon != preset_def.get("icon"):
                needs_update = True
                update_fields.append("icon")
            if existing_flow.prompt_template != preset_def.get("prompt_template"):
                needs_update = True
                update_fields.append("prompt_template")
            if existing_flow.agent_type != preset_def.get("agent_type"):
                needs_update = True
                update_fields.append("agent_type")
            if existing_flow.agent_config != preset_def.get("agent_config"):
                needs_update = True
                update_fields.append("agent_config")
            if existing_flow.allowed_mcp_tools != preset_def.get("allowed_mcp_tools"):
                needs_update = True
                update_fields.append("allowed_mcp_tools")
            if existing_flow.git_clone_config != preset_def.get("git_clone_config"):
                needs_update = True
                update_fields.append("git_clone_config")

            if needs_update:
                logger.info(
                    f"  Updating preset '{preset_name}' (fields: {', '.join(update_fields)})"
                )
                if not dry_run:
                    # Create update schema
                    update_data = {
                        "name": preset_name,
                        "description": preset_def.get("description"),
                        "icon": preset_def.get("icon"),
                        "prompt_template": preset_def.get("prompt_template"),
                        "agent_type": preset_def.get("agent_type"),
                        "agent_config": preset_def.get("agent_config"),
                        "allowed_mcp_servers": preset_def.get(
                            "allowed_mcp_servers", []
                        ),
                        "allowed_mcp_tools": preset_def.get("allowed_mcp_tools", []),
                        "git_clone_config": preset_def.get("git_clone_config"),
                        "trigger_event_source": preset_def.get("trigger_event_source"),
                        "trigger_event_type": preset_def.get("trigger_event_type"),
                        "trigger_config": preset_def.get("trigger_config"),
                        "is_preset": True,
                        "is_enabled": existing_flow.is_enabled,  # Preserve user's enabled state
                    }
                    flow_update = schemas.FlowUpdate(**update_data)
                    crud_flow.update(
                        db=db,
                        db_obj=existing_flow,
                        flow_in=flow_update,
                        account_id=account_id,
                    )
                changes_count += 1
            else:
                logger.debug(f"  Preset '{preset_name}' is up to date")
        else:
            # Create new preset
            logger.info(f"  Creating new preset '{preset_name}'")
            if not dry_run:
                # Prepare preset data
                preset_data = preset_def.copy()
                # Set trigger_event_source to None (will be configured by user)
                preset_data["trigger_event_source"] = None
                preset_data["trigger_event_type"] = preset_def.get("trigger_event_type")
                preset_data["is_preset"] = True

                flow_create = schemas.FlowCreate(**preset_data)
                crud_flow.create(db=db, flow_in=flow_create, account_id=account_id)
            changes_count += 1

    logger.info(f"  Total changes for {account_label}: {changes_count}")
    return changes_count


def sync_all_accounts(db: Session, dry_run: bool = False) -> int:
    """
    Sync flow presets for all accounts.

    Args:
        db: Database session
        dry_run: If True, only log what would be done without making changes

    Returns:
        Total number of changes across all accounts
    """
    crud_account = CRUDAccount(Account)
    total_changes = 0

    # Get all accounts
    accounts = crud_account.get_multi(db, skip=0, limit=10000)
    logger.info(f"Found {len(accounts)} accounts to process")

    for account in accounts:
        # Get an email from the account for logging
        account_email = None
        if account.users:
            account_email = account.users[0].email

        changes = sync_presets_for_account(
            db, account.id, account_email=account_email, dry_run=dry_run
        )
        total_changes += changes

    return total_changes


def main():
    parser = argparse.ArgumentParser(description="Sync flow presets for accounts")
    parser.add_argument(
        "--email",
        type=str,
        help="Sync presets for account with this user email",
    )
    parser.add_argument(
        "--account-id",
        type=str,
        help="Sync presets for this specific account ID",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    # Get database session
    db_gen = get_db_session()
    db = next(db_gen)

    try:
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")

        if args.email:
            # Find account by user email
            crud_account = CRUDAccount(Account)
            account = crud_account.get_by_email(db, email=args.email)
            if not account:
                logger.error(f"No account found with email: {args.email}")
                sys.exit(1)

            changes = sync_presets_for_account(
                db, account.id, account_email=args.email, dry_run=args.dry_run
            )
            logger.info(f"Total changes: {changes}")

        elif args.account_id:
            # Sync specific account by ID
            try:
                account_id = UUID(args.account_id)
            except ValueError:
                logger.error(f"Invalid account ID format: {args.account_id}")
                sys.exit(1)

            changes = sync_presets_for_account(db, account_id, dry_run=args.dry_run)
            logger.info(f"Total changes: {changes}")

        else:
            # Sync all accounts
            total_changes = sync_all_accounts(db, dry_run=args.dry_run)
            logger.info(f"Total changes across all accounts: {total_changes}")

        if not args.dry_run:
            logger.info("Successfully synced flow presets")

    except Exception as e:
        logger.error(f"Error syncing flow presets: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
