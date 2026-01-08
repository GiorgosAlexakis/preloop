#!/usr/bin/env python3
"""
Script to sync global flow presets.

Global presets are system-wide templates (account_id=None) that are available
to all accounts. Users clone these presets to create account-specific flows.

Usage:
    # Sync global presets (create/update)
    python scripts/sync_flow_presets.py

    # Dry run (no changes)
    python scripts/sync_flow_presets.py --dry-run

    # Cleanup: Delete account-specific presets that overlap with global presets
    python scripts/sync_flow_presets.py --cleanup

    # Cleanup with dry run (show what would be deleted)
    python scripts/sync_flow_presets.py --cleanup --dry-run

Environment Variables:
    PRELOOP_PRESETS_PATH: Path to the presets directory. Defaults to the
                          open-source presets directory. Set to /app/presets
                          in the EE Docker image.
"""

import argparse
import logging
import sys

from dotenv import load_dotenv
from typing import List, Tuple

from sqlalchemy.orm import Session

from preloop.models.db.session import get_db_session
from preloop.models.crud.flow import CRUDFlow
from preloop.models.models.flow import Flow
from preloop.models import schemas
from preloop.flow_presets import FLOW_PRESETS, PRESETS_DIR

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

logger.info(f"Loading presets from: {PRESETS_DIR}")
logger.info(f"Found {len(FLOW_PRESETS)} preset definitions")


def sync_global_presets(db: Session, dry_run: bool = False) -> int:
    """
    Sync global flow presets (account_id=None).

    Creates new presets and updates existing ones to match the preset definitions.

    Args:
        db: Database session
        dry_run: If True, only log what would be done without making changes

    Returns:
        Number of presets created/updated
    """
    crud_flow = CRUDFlow()
    changes_count = 0

    # Get existing global presets
    existing_global_presets = crud_flow.get_global_presets(db, limit=1000)
    existing_by_name = {flow.name: flow for flow in existing_global_presets}

    logger.info(f"Found {len(existing_by_name)} existing global presets")

    # Process each preset definition
    for preset_def in FLOW_PRESETS:
        preset_name = preset_def["name"]
        existing_flow = existing_by_name.get(preset_name)

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

            # Check if preset incorrectly has an account_id (should be None)
            if existing_flow.account_id is not None:
                needs_update = True
                update_fields.append("account_id (should be NULL)")
                logger.warning(
                    f"  Global preset '{preset_name}' has account_id={existing_flow.account_id}, will be fixed"
                )

            if needs_update:
                logger.info(
                    f"  Updating global preset '{preset_name}' (fields: {', '.join(update_fields)})"
                )
                if not dry_run:
                    # Update the preset - set account_id to None explicitly
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
                        "is_enabled": False,  # Global presets are always disabled
                    }
                    # Update directly to ensure account_id stays NULL
                    for field, value in update_data.items():
                        if hasattr(existing_flow, field):
                            setattr(existing_flow, field, value)
                    existing_flow.account_id = None  # Ensure it's NULL
                    db.add(existing_flow)
                    db.commit()
                changes_count += 1
            else:
                logger.debug(f"  Global preset '{preset_name}' is up to date")
        else:
            # Create new global preset
            logger.info(f"  Creating new global preset '{preset_name}'")
            if not dry_run:
                # Prepare preset data
                preset_data = preset_def.copy()
                preset_data.pop("account_id", None)  # Ensure no account_id
                preset_data["trigger_event_source"] = None
                preset_data["trigger_event_type"] = preset_def.get("trigger_event_type")
                preset_data["is_preset"] = True
                preset_data["is_enabled"] = False

                flow_create = schemas.FlowCreate(**preset_data)
                crud_flow.create(db=db, flow_in=flow_create, account_id=None)
            changes_count += 1

    logger.info(f"Total global preset changes: {changes_count}")
    return changes_count


def find_account_presets_overlapping_global(
    db: Session,
) -> List[Tuple[Flow, str]]:
    """
    Find account-specific presets that have the same name as global presets.

    These are problematic because they shadow the global presets and should
    be cleaned up.

    Returns:
        List of (flow, preset_name) tuples for overlapping presets
    """
    global_preset_names = {preset["name"] for preset in FLOW_PRESETS}

    # Find all account-specific flows that are presets with names matching global presets
    overlapping = []
    query = db.query(Flow).filter(
        Flow.is_preset,
        Flow.account_id.isnot(None),
        Flow.name.in_(global_preset_names),
    )

    for flow in query.all():
        overlapping.append((flow, flow.name))

    return overlapping


def cleanup_overlapping_presets(db: Session, dry_run: bool = False) -> int:
    """
    Delete account-specific presets that overlap with global presets.

    Args:
        db: Database session
        dry_run: If True, only log what would be done without making changes

    Returns:
        Number of presets deleted
    """
    overlapping = find_account_presets_overlapping_global(db)

    if not overlapping:
        logger.info("No overlapping account-specific presets found")
        return 0

    logger.info(
        f"Found {len(overlapping)} account-specific presets overlapping with global presets:"
    )
    for flow, preset_name in overlapping:
        logger.info(f"  - '{preset_name}' (account_id={flow.account_id}, id={flow.id})")

    if dry_run:
        logger.info("DRY RUN - No presets will be deleted")
        return len(overlapping)

    # Confirm deletion
    print(f"\nThis will delete {len(overlapping)} account-specific presets.")
    print("These presets overlap with global presets and should be removed.")
    print("Users will still have access to the global presets after deletion.")
    response = input("\nProceed with deletion? [y/N]: ").strip().lower()

    if response != "y":
        logger.info("Deletion cancelled by user")
        return 0

    deleted_count = 0
    for flow, preset_name in overlapping:
        logger.info(f"  Deleting '{preset_name}' (id={flow.id})")
        db.delete(flow)
        deleted_count += 1

    db.commit()
    logger.info(f"Deleted {deleted_count} overlapping account-specific presets")
    return deleted_count


def main():
    parser = argparse.ArgumentParser(
        description="Sync global flow presets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Sync global presets (create/update)
    python scripts/sync_flow_presets.py

    # Dry run (show what would be done)
    python scripts/sync_flow_presets.py --dry-run

    # Cleanup overlapping account-specific presets
    python scripts/sync_flow_presets.py --cleanup

    # Cleanup with dry run
    python scripts/sync_flow_presets.py --cleanup --dry-run
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete account-specific presets that overlap with global presets (requires confirmation)",
    )

    args = parser.parse_args()

    # Get database session
    db_gen = get_db_session()
    db = next(db_gen)

    try:
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")

        if args.cleanup:
            # Cleanup mode: delete overlapping account-specific presets
            deleted = cleanup_overlapping_presets(db, dry_run=args.dry_run)
            if not args.dry_run and deleted > 0:
                logger.info(f"Cleanup complete: deleted {deleted} overlapping presets")
        else:
            # Normal mode: sync global presets
            changes = sync_global_presets(db, dry_run=args.dry_run)
            if not args.dry_run:
                logger.info(
                    f"Successfully synced global flow presets ({changes} changes)"
                )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
