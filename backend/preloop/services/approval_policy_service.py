"""Service for managing default approval policies.

This service provides functions to create default approval policies for accounts
when they are first created. In the open-source edition, each account has a
single default "Standard" approval policy that is used for all tool approvals.
"""

import logging
from uuid import UUID

from preloop.models.crud import crud_approval_policy
from preloop.models.db.session import get_session_factory

logger = logging.getLogger(__name__)


def create_default_approval_policy_for_account(
    account_id: UUID, user_id: UUID | None = None
) -> None:
    """
    Create a default approval policy for a newly created account.

    This ensures every account has a default "Standard" policy that can be
    used for tool approvals. In the open-source edition, this is the only
    policy the account will need.

    Args:
        account_id: The UUID of the account to create the policy for.
        user_id: The UUID of the user to set as the default approver.
                 In single-user mode, this should be the account owner.
    """
    session_factory = get_session_factory()
    db = session_factory()

    try:
        # Check if a default policy already exists
        existing_default = crud_approval_policy.get_default(
            db, account_id=str(account_id)
        )

        if existing_default:
            logger.debug(
                f"Default approval policy already exists for account {account_id}"
            )
            return

        # Check if any policies exist at all
        existing_policies = crud_approval_policy.get_multi_by_account(
            db, account_id=str(account_id), limit=1
        )

        if existing_policies:
            logger.debug(
                f"Approval policies already exist for account {account_id}, "
                "skipping default creation"
            )
            return

        # Create the default policy with the user as the approver
        policy_data = {
            "name": "Default Approval Policy",
            "description": (
                "Default policy for tool approval requests. "
                "Approval requests will be shown in the Preloop UI."
            ),
            "approval_type": "standard",
            "is_default": True,
            "approvals_required": 1,
            "notification_channels": ["email", "mobile_push"],
        }

        # In single-user/open-source mode, set the account owner as the approver
        if user_id:
            policy_data["approver_user_ids"] = [str(user_id)]

        crud_approval_policy.create(
            db,
            obj_in=policy_data,
            account_id=str(account_id),
        )

        logger.info(
            f"Created default approval policy for account {account_id} "
            f"with approver user_id={user_id}"
        )

    except Exception as e:
        logger.error(
            f"Failed to create default approval policy for account {account_id}: {e}",
            exc_info=True,
        )
    finally:
        db.close()


def create_default_approval_policy_background(
    account_id: UUID, user_id: UUID | None = None
) -> None:
    """
    Background task wrapper for creating default approval policy.

    This function is designed to be called via FastAPI's BackgroundTasks
    to avoid blocking the registration response.

    Args:
        account_id: The UUID of the account to create the policy for.
        user_id: The UUID of the user to set as the default approver.
    """
    try:
        create_default_approval_policy_for_account(account_id, user_id)
    except Exception as e:
        # Log but don't raise - this is a background task
        logger.error(
            f"Background task failed to create default approval policy "
            f"for account {account_id}: {e}",
            exc_info=True,
        )
