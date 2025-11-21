"""Service for creating and managing flow presets."""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from spacemodels import schemas
from spacemodels.crud import crud_flow
from spacemodels.db.session import get_session_factory
from spacebridge.flow_presets import FLOW_PRESETS

logger = logging.getLogger(__name__)


def create_default_presets_for_account(
    db: Session,
    account_id: UUID,
    tracker_id: Optional[UUID] = None,
) -> List[schemas.FlowResponse]:
    """
    Create default flow presets for a new account.

    Args:
        db: Database session
        account_id: ID of the account to create presets for
        tracker_id: Optional tracker ID to associate with tracker-based flows
                   If provided, presets will be enabled by default

    Returns:
        List of created flow preset responses
    """
    created_flows = []

    for preset_config in FLOW_PRESETS:
        try:
            # Create a copy of the preset config
            flow_data = preset_config.copy()

            # Set account_id
            flow_data["account_id"] = str(account_id)

            # If trigger requires a tracker, set it if provided
            # Otherwise, leave the flow disabled until user configures it
            if flow_data.get("trigger_event_type") and tracker_id:
                flow_data["trigger_event_source"] = str(tracker_id)
                flow_data["is_enabled"] = True
            else:
                # Disable flows that require tracker configuration
                flow_data["is_enabled"] = False

            # Configure git clone repositories if needed
            if flow_data.get("git_clone_config") and tracker_id:
                git_config = flow_data["git_clone_config"].copy()
                # Set up default repository configuration
                if not git_config.get("repositories"):
                    git_config["repositories"] = [
                        {
                            "tracker_id": str(tracker_id),
                            "clone_path": "workspace",
                        }
                    ]
                flow_data["git_clone_config"] = git_config

            # Create the flow using Pydantic schema
            flow_in = schemas.FlowCreate(**flow_data)
            flow = crud_flow.create(db=db, flow_in=flow_in, account_id=account_id)

            created_flows.append(flow)
            logger.info(f"Created preset flow '{flow.name}' for account {account_id}")

        except Exception as e:
            logger.error(
                f"Failed to create preset '{preset_config.get('name')}' for account {account_id}: {e}",
                exc_info=True,
            )
            # Continue with other presets even if one fails
            continue

    logger.info(f"Created {len(created_flows)} preset flows for account {account_id}")
    return created_flows


def get_preset_names() -> List[str]:
    """Get list of available preset names."""
    return [preset["name"] for preset in FLOW_PRESETS]


def get_preset_by_name(name: str) -> Optional[dict]:
    """Get preset configuration by name."""
    for preset in FLOW_PRESETS:
        if preset["name"] == name:
            return preset.copy()
    return None


def create_default_presets_for_account_background(
    account_id: UUID,
    tracker_id: Optional[UUID] = None,
) -> None:
    """
    Background task-safe wrapper for creating default flow presets.

    Creates its own database session to avoid issues with request-scoped sessions
    being closed before the background task runs.

    Args:
        account_id: ID of the account to create presets for
        tracker_id: Optional tracker ID to associate with tracker-based flows
    """
    session_factory = get_session_factory()
    db = session_factory()
    try:
        create_default_presets_for_account(
            db=db, account_id=account_id, tracker_id=tracker_id
        )
        db.commit()
        logger.info(
            f"Background task: Successfully created default presets for account {account_id}"
        )
    except Exception as e:
        logger.error(
            f"Background task: Failed to create presets for account {account_id}: {e}",
            exc_info=True,
        )
        db.rollback()
    finally:
        db.close()
