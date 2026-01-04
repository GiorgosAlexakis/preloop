"""Service for creating and managing flow presets.

Flow presets are global templates (account_id=None) that are available to all accounts.
They are NOT copied to individual accounts - instead, users clone them when they want
to use them, which creates an account-specific flow based on the preset.
"""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from preloop.models import schemas
from preloop.models.crud import crud_flow
from preloop.models.db.session import get_session_factory
from preloop.flow_presets import FLOW_PRESETS

logger = logging.getLogger(__name__)


def ensure_global_presets_exist(db: Session) -> List[schemas.FlowResponse]:
    """
    Ensure global flow presets exist in the database.

    Global presets have account_id=None and are available to all accounts.
    This function creates any missing presets but does not update existing ones.
    Use the sync_flow_presets.py script for updates.

    Returns:
        List of created flow preset responses
    """
    created_flows = []

    for preset_config in FLOW_PRESETS:
        preset_name = preset_config["name"]

        # Check if global preset already exists
        existing = crud_flow.get_global_preset_by_name(db, name=preset_name)
        if existing:
            logger.debug(f"Global preset '{preset_name}' already exists")
            continue

        try:
            # Create a copy of the preset config
            flow_data = preset_config.copy()

            # Global presets have no account_id
            flow_data.pop("account_id", None)

            # Presets are disabled by default - user enables after cloning
            flow_data["is_enabled"] = False
            flow_data["is_preset"] = True

            # Create the flow using Pydantic schema (account_id=None for global)
            flow_in = schemas.FlowCreate(**flow_data)
            flow = crud_flow.create(db=db, flow_in=flow_in, account_id=None)

            created_flows.append(flow)
            logger.info(f"Created global preset flow '{flow.name}'")

        except Exception as e:
            logger.error(
                f"Failed to create global preset '{preset_name}': {e}",
                exc_info=True,
            )
            # Continue with other presets even if one fails
            continue

    if created_flows:
        logger.info(f"Created {len(created_flows)} global preset flows")
    return created_flows


# Keep the old function name as an alias for backwards compatibility
# but it now just ensures global presets exist (doesn't create per-account copies)
def create_default_presets_for_account(
    db: Session,
    account_id: UUID,
    tracker_id: Optional[UUID] = None,
) -> List[schemas.FlowResponse]:
    """
    DEPRECATED: Presets are now global and not copied per-account.

    This function now just ensures global presets exist.
    Users should clone presets when they want to use them.

    Args:
        db: Database session
        account_id: Ignored (kept for backwards compatibility)
        tracker_id: Ignored (kept for backwards compatibility)

    Returns:
        List of created global preset flows (if any were missing)
    """
    logger.warning(
        "create_default_presets_for_account is deprecated. "
        "Presets are now global. Use ensure_global_presets_exist() instead."
    )
    return ensure_global_presets_exist(db)


def get_preset_names() -> List[str]:
    """Get list of available preset names."""
    return [preset["name"] for preset in FLOW_PRESETS]


def get_preset_by_name(name: str) -> Optional[dict]:
    """Get preset configuration by name."""
    for preset in FLOW_PRESETS:
        if preset["name"] == name:
            return preset.copy()
    return None


def ensure_global_presets_exist_background() -> None:
    """
    Background task-safe wrapper for ensuring global presets exist.

    Creates its own database session to avoid issues with request-scoped sessions
    being closed before the background task runs.
    """
    session_factory = get_session_factory()
    db = session_factory()
    try:
        ensure_global_presets_exist(db=db)
        db.commit()
        logger.info("Background task: Successfully ensured global presets exist")
    except Exception as e:
        logger.error(
            f"Background task: Failed to ensure global presets: {e}",
            exc_info=True,
        )
        db.rollback()
    finally:
        db.close()


# Keep old function for backwards compatibility
def create_default_presets_for_account_background(
    account_id: UUID,
    tracker_id: Optional[UUID] = None,
) -> None:
    """
    DEPRECATED: Use ensure_global_presets_exist_background() instead.

    This now just ensures global presets exist (ignores account_id and tracker_id).
    """
    logger.warning(
        "create_default_presets_for_account_background is deprecated. "
        "Presets are now global. Use ensure_global_presets_exist_background() instead."
    )
    ensure_global_presets_exist_background()
