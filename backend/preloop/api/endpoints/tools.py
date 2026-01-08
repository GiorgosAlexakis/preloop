"""Tools router for managing available tools and their configurations.

IMPORTANT: BUILTIN_TOOLS metadata must match the tool implementations in
preloop/services/initialize_mcp.py to ensure consistency between REST API and MCP.
"""

import logging
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from preloop.api.common import get_account_for_user
from preloop.models.crud import (
    crud_approval_policy,
    crud_mcp_server,
    crud_mcp_tool,
    crud_tool_configuration,
    tool_approval_condition,
)
from preloop.models.db.session import get_db_session
from preloop.models.models.account import Account
from preloop.models.models.tool_configuration import ToolConfiguration
from preloop.models.schemas.tool_configuration import (
    ApprovalPolicyCreate,
    ApprovalPolicyResponse,
    ApprovalPolicyUpdate,
    ToolConfigurationCreate,
    ToolConfigurationResponse,
    ToolConfigurationUpdate,
)
from preloop.schemas.tool_approval_condition import (
    ToolApprovalConditionCreate,
    ToolApprovalConditionResponse,
    ConditionTestRequest,
    ConditionTestResponse,
)
from preloop.services.tool_approval_evaluator import evaluate_cel_expression

logger = logging.getLogger(__name__)
router = APIRouter()

# Define builtin tools metadata
# NOTE: These must match the @mcp.tool() decorators in initialize_mcp.py
BUILTIN_TOOLS = [
    {
        "name": "request_approval",
        "description": "Request approval for an operation before executing it",
        "source": "builtin",
        "requires_tracker": False,
        "required_tracker_types": [],
        "schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Description of the operation requiring approval",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context about the situation",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of why this operation is needed",
                },
                "caller": {
                    "type": "string",
                    "description": "Optional: Name of the agent or flow requesting approval (auto-populated if not specified)",
                },
                "approval_policy": {
                    "type": "string",
                    "description": "Optional name of the approval policy to use",
                },
            },
            "required": ["operation", "context", "reasoning"],
        },
    },
    {
        "name": "get_issue",
        "description": "Get detailed information about an issue by its identifier (URL, key, or ID)",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": [],
        "schema": {
            "type": "object",
            "properties": {
                "issue": {
                    "type": "string",
                    "description": "Issue identifier (URL, key, or ID)",
                }
            },
            "required": ["issue"],
        },
    },
    {
        "name": "create_issue",
        "description": "Create a new issue in a project",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": [],
        "schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project identifier"},
                "title": {"type": "string", "description": "Issue title"},
                "description": {"type": "string", "description": "Issue description"},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Issue labels",
                },
                "assignee": {"type": "string", "description": "Assignee username"},
                "priority": {"type": "string", "description": "Issue priority"},
                "status": {"type": "string", "description": "Issue status"},
            },
            "required": ["project", "title", "description"],
        },
    },
    {
        "name": "update_issue",
        "description": "Update an existing issue",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": [],
        "schema": {
            "type": "object",
            "properties": {
                "issue": {"type": "string", "description": "Issue identifier"},
                "title": {"type": "string", "description": "New title"},
                "description": {"type": "string", "description": "New description"},
                "status": {"type": "string", "description": "New status"},
                "priority": {"type": "string", "description": "New priority"},
                "assignee": {"type": "string", "description": "New assignee"},
                "labels": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["issue"],
        },
    },
    {
        "name": "search",
        "description": "Search for issues and comments using similarity or fulltext search",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": [],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "project": {"type": "string", "description": "Project identifier"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum results",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "estimate_compliance",
        "description": "Estimate compliance for a list of issues provided as URLs or issue keys",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": [],
        "schema": {
            "type": "object",
            "properties": {
                "issues": {"type": "array", "items": {"type": "string"}},
                "compliance_metric": {"type": "string", "default": "DoR"},
            },
            "required": ["issues"],
        },
    },
    {
        "name": "improve_compliance",
        "description": "Get suggestions to improve compliance for a list of issues",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": [],
        "schema": {
            "type": "object",
            "properties": {
                "issues": {"type": "array", "items": {"type": "string"}},
                "compliance_metric": {"type": "string", "default": "DoR"},
            },
            "required": ["issues"],
        },
    },
    {
        "name": "add_comment",
        "description": "Add a comment to an issue, pull request, or merge request",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": [],
        "schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Issue, PR, or MR identifier (URL, key, or ID)",
                },
                "comment": {"type": "string", "description": "Comment text"},
            },
            "required": ["target", "comment"],
        },
    },
    {
        "name": "get_pull_request",
        "description": "Get details of a GitHub pull request",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": ["github"],
        "schema": {
            "type": "object",
            "properties": {
                "pull_request": {
                    "type": "string",
                    "description": "PR identifier (URL, slug, or number)",
                }
            },
            "required": ["pull_request"],
        },
    },
    {
        "name": "get_merge_request",
        "description": "Get details of a GitLab merge request",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": ["gitlab"],
        "schema": {
            "type": "object",
            "properties": {
                "merge_request": {
                    "type": "string",
                    "description": "MR identifier (URL, slug, or IID)",
                }
            },
            "required": ["merge_request"],
        },
    },
    {
        "name": "update_pull_request",
        "description": "Update a GitHub pull request",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": ["github"],
        "schema": {
            "type": "object",
            "properties": {
                "pull_request": {
                    "type": "string",
                    "description": "PR identifier (URL, slug, or number)",
                },
                "title": {"type": "string", "description": "New PR title"},
                "description": {"type": "string", "description": "New PR description"},
                "state": {"type": "string", "description": "New state (open/closed)"},
                "assignees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Assignee usernames",
                },
                "reviewers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Reviewer usernames",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Label names",
                },
                "draft": {"type": "boolean", "description": "Mark as draft"},
            },
            "required": ["pull_request"],
        },
    },
    {
        "name": "update_merge_request",
        "description": "Update a GitLab merge request",
        "source": "builtin",
        "requires_tracker": True,
        "required_tracker_types": ["gitlab"],
        "schema": {
            "type": "object",
            "properties": {
                "merge_request": {
                    "type": "string",
                    "description": "MR identifier (URL, slug, or IID)",
                },
                "title": {"type": "string", "description": "New MR title"},
                "description": {"type": "string", "description": "New MR description"},
                "state_event": {
                    "type": "string",
                    "description": "State event (close/reopen)",
                },
                "assignee_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Assignee user IDs",
                },
                "reviewer_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Reviewer user IDs",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Label names",
                },
                "draft": {"type": "boolean", "description": "Mark as draft/WIP"},
            },
            "required": ["merge_request"],
        },
    },
]


@router.get("/tools", response_model=List[Dict])
async def list_all_tools(
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> List[Dict]:
    """List all available tools (builtin + external) with their configuration status.

    Returns a comprehensive list of:
    - All builtin tools
    - All tools from active MCP servers
    - Configuration status for each tool (enabled/disabled, preloop)

    Args:
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        List of tool dictionaries with metadata and configuration
    """
    # Get all tool configurations for this account
    tool_configs = crud_tool_configuration.get_multi_by_account(
        db, account_id=str(account.id)
    )

    # Create a lookup map: (tool_name, source, mcp_server_id) -> config
    config_map = {
        (
            tc.tool_name,
            tc.tool_source,
            str(tc.mcp_server_id) if tc.mcp_server_id else None,
        ): tc
        for tc in tool_configs
    }

    # Get all approval conditions to check which tools have them
    from sqlalchemy import select
    from preloop.models import models

    result = db.execute(
        select(models.ToolApprovalCondition).where(
            models.ToolApprovalCondition.account_id == str(account.id),
            models.ToolApprovalCondition.is_enabled,
        )
    )
    approval_conditions = result.scalars().all()

    # Create map of config_id -> has condition
    condition_map = {
        str(cond.tool_configuration_id): True
        for cond in approval_conditions
        if cond.condition_expression
    }

    from preloop.models.crud import crud_tracker

    trackers = crud_tracker.get_for_account(db, account_id=str(account.id))
    tracker_types = list(set(tracker.tracker_type for tracker in trackers))
    has_tracker = len(tracker_types) > 0

    tools = []

    # Add builtin tools
    for builtin_tool in BUILTIN_TOOLS:
        config = config_map.get((builtin_tool["name"], "builtin", None))
        config_id = str(config.id) if config else None

        requires_tracker = builtin_tool.get("requires_tracker", False)
        required_tracker_types = builtin_tool.get("required_tracker_types") or []

        is_supported = True
        unsupported_reason = None
        if requires_tracker and not has_tracker:
            is_supported = False
            unsupported_reason = "Add a tracker to enable this tool"
        elif required_tracker_types and not any(
            t in tracker_types for t in required_tracker_types
        ):
            is_supported = False
            required_str = ", ".join(required_tracker_types)
            unsupported_reason = f"Add a {required_str} tracker to enable this tool"

        tools.append(
            {
                "name": builtin_tool["name"],
                "description": builtin_tool["description"],
                "source": "builtin",
                "source_id": None,
                "source_name": "Built-in",
                "schema": builtin_tool["schema"],
                "is_enabled": config.is_enabled if config else True,
                "requires_tracker": requires_tracker,
                "required_tracker_types": required_tracker_types,
                "is_supported": is_supported,
                "unsupported_reason": unsupported_reason,
                "approval_policy_id": str(config.approval_policy_id)
                if config and config.approval_policy_id
                else None,
                "config_id": config_id,
                "has_approval_condition": condition_map.get(config_id, False)
                if config_id
                else False,
            }
        )

    # Add external MCP tools
    mcp_servers = crud_mcp_server.get_active_by_account(db, account_id=str(account.id))

    for server in mcp_servers:
        mcp_tools = crud_mcp_tool.get_by_server(db, server_id=server.id)

        for mcp_tool in mcp_tools:
            config = config_map.get((mcp_tool.name, "mcp", str(server.id)))
            config_id = str(config.id) if config else None
            tools.append(
                {
                    "name": mcp_tool.name,
                    "description": mcp_tool.description or "",
                    "source": "mcp",
                    "source_id": str(server.id),
                    "source_name": server.name,
                    "schema": mcp_tool.input_schema,
                    "is_enabled": config.is_enabled if config else True,
                    "requires_tracker": False,
                    "required_tracker_types": [],
                    "is_supported": True,
                    "unsupported_reason": None,
                    "approval_policy_id": str(config.approval_policy_id)
                    if config and config.approval_policy_id
                    else None,
                    "config_id": config_id,
                    "has_approval_condition": condition_map.get(config_id, False)
                    if config_id
                    else False,
                }
            )

    logger.info(
        f"Returning {len(tools)} tools for account {account.id} "
        f"({len(BUILTIN_TOOLS)} builtin, {len(tools) - len(BUILTIN_TOOLS)} external)"
    )

    return tools


@router.post("/tool-configurations", status_code=status.HTTP_201_CREATED)
async def create_tool_configuration(
    config_data: ToolConfigurationCreate,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ToolConfigurationResponse:
    """Create a new tool configuration.

    Args:
        config_data: Tool configuration data
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Created tool configuration

    Raises:
        HTTPException: If configuration already exists or creation fails
    """
    # Check if configuration already exists
    # Get all configs and filter in Python since we need multi-field matching
    all_configs = crud_tool_configuration.get_multi_by_account(
        db, account_id=str(account.id), limit=1000
    )
    existing_config = next(
        (
            c
            for c in all_configs
            if c.tool_name == config_data.tool_name
            and c.tool_source == config_data.tool_source
            and c.mcp_server_id == config_data.mcp_server_id
        ),
        None,
    )

    if existing_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration for tool '{config_data.tool_name}' already exists",
        )

    try:
        new_config = ToolConfiguration(
            account_id=str(account.id),
            tool_name=config_data.tool_name,
            tool_source=config_data.tool_source,
            mcp_server_id=config_data.mcp_server_id,
            http_endpoint_id=config_data.http_endpoint_id,
            is_enabled=config_data.is_enabled
            if config_data.is_enabled is not None
            else True,
            approval_policy_id=config_data.approval_policy_id
            if hasattr(config_data, "approval_policy_id")
            else None,
            tool_description=config_data.tool_description,
            tool_schema=config_data.tool_schema,
            custom_config=config_data.custom_config,
        )

        db.add(new_config)
        db.commit()
        db.refresh(new_config)

        logger.info(
            f"Created tool configuration for {config_data.tool_name} "
            f"(user: {account.id})"
        )

        return ToolConfigurationResponse.model_validate(new_config)

    except IntegrityError as e:
        db.rollback()
        logger.info(
            f"Tool configuration for {config_data.tool_name} already exists, fetching existing config"
        )

        # Fetch the existing configuration
        existing_config = crud_tool_configuration.get_by_tool_name_and_source(
            db,
            account_id=str(account.id),
            tool_name=config_data.tool_name,
            tool_source=config_data.tool_source,
        )

        if existing_config:
            # Configuration already exists - return it (idempotent behavior)
            # This handles race conditions where multiple requests try to create the same config
            logger.info(
                f"Returning existing tool configuration for {config_data.tool_name} "
                f"(idempotent behavior for race condition)"
            )
            return ToolConfigurationResponse.model_validate(existing_config)

        # If we still can't find it, something went wrong
        logger.error(f"IntegrityError but config not found for {config_data.tool_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating tool configuration: {str(e)}",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating tool configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating tool configuration: {str(e)}",
        )


@router.get(
    "/tool-configurations/{config_id}", response_model=ToolConfigurationResponse
)
async def get_tool_configuration(
    config_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ToolConfigurationResponse:
    """Get a specific tool configuration.

    Args:
        config_id: Tool configuration ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Tool configuration details

    Raises:
        HTTPException: If configuration not found or access denied
    """
    config = crud_tool_configuration.get(
        db, id=str(config_id), account_id=str(account.id)
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool configuration not found or access denied",
        )

    return ToolConfigurationResponse.model_validate(config)


@router.put(
    "/tool-configurations/{config_id}", response_model=ToolConfigurationResponse
)
async def update_tool_configuration(
    config_id: UUID,
    config_update: ToolConfigurationUpdate,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ToolConfigurationResponse:
    """Update an existing tool configuration.

    Args:
        config_id: Tool configuration ID
        config_update: Updated configuration data
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Updated tool configuration

    Raises:
        HTTPException: If configuration not found or update fails
    """
    config = crud_tool_configuration.get(
        db, id=str(config_id), account_id=str(account.id)
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool configuration not found or access denied",
        )

    # Update fields
    update_data = config_update.model_dump(exclude_unset=True)

    try:
        for field, value in update_data.items():
            setattr(config, field, value)

        db.commit()
        db.refresh(config)

        logger.info(f"Updated tool configuration {config_id} for user {account.id}")

        return ToolConfigurationResponse.model_validate(config)

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error updating tool configuration {config_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating tool configuration: {str(e)}",
        )


@router.put(
    "/tool-configurations/{config_id}/condition",
    response_model=ToolConfigurationResponse,
)
async def update_tool_approval_condition(
    config_id: UUID,
    condition_data: Dict[str, Any],
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ToolConfigurationResponse:
    """Update or create approval condition for a tool configuration.

    Args:
        config_id: Tool configuration ID
        condition_data: Condition data with 'approval_condition' field
        account: Current user's account
        db: Database session

    Returns:
        Updated tool configuration

    Raises:
        HTTPException: If configuration not found or update fails
    """
    from preloop.models.crud import tool_approval_condition
    from preloop.models.models import ToolApprovalCondition

    config = crud_tool_configuration.get(
        db, id=str(config_id), account_id=str(account.id)
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool configuration not found or access denied",
        )

    approval_condition_expr = condition_data.get("approval_condition")

    try:
        # Get existing condition
        existing_condition = tool_approval_condition.get_by_tool_configuration(
            db, tool_configuration_id=config_id, account_id=account.id
        )

        if approval_condition_expr:
            # Create or update condition
            if existing_condition:
                # Update existing condition
                existing_condition.condition_expression = approval_condition_expr
                existing_condition.is_enabled = True
                db.commit()
                logger.info(f"Updated approval condition for tool config {config_id}")
            else:
                # Create new condition
                new_condition = ToolApprovalCondition(
                    tool_configuration_id=config_id,
                    account_id=account.id,
                    condition_type="argument",  # Default to argument-based
                    condition_expression=approval_condition_expr,
                    is_enabled=True,
                )
                db.add(new_condition)
                db.commit()
                logger.info(f"Created approval condition for tool config {config_id}")
        else:
            # Delete condition if expression is empty
            if existing_condition:
                db.delete(existing_condition)
                db.commit()
                logger.info(f"Deleted approval condition for tool config {config_id}")

        db.refresh(config)
        return ToolConfigurationResponse.model_validate(config)

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error updating approval condition for {config_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating approval condition: {str(e)}",
        )


@router.delete("/tool-configurations/{config_id}", status_code=status.HTTP_200_OK)
async def delete_tool_configuration(
    config_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, str]:
    """Delete a tool configuration.

    Args:
        config_id: Tool configuration ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If configuration not found or deletion fails
    """
    config = crud_tool_configuration.get(
        db, id=str(config_id), account_id=str(account.id)
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool configuration not found or access denied",
        )

    try:
        db.delete(config)
        db.commit()

        logger.info(f"Deleted tool configuration {config_id} for user {account.id}")

        return {"message": "Tool configuration deleted successfully"}

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error deleting tool configuration {config_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting tool configuration: {str(e)}",
        )


# Approval Policy endpoints


@router.get("/approval-policies", response_model=List[ApprovalPolicyResponse])
async def list_approval_policies(
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> List[ApprovalPolicyResponse]:
    """List all approval policies for the current user's account.

    Args:
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        List of approval policies
    """
    policies = crud_approval_policy.get_multi_by_account(db, account_id=str(account.id))

    logger.info(f"Returning {len(policies)} approval policies for user {account.id}")

    return [ApprovalPolicyResponse.model_validate(p) for p in policies]


@router.post("/approval-policies", status_code=status.HTTP_201_CREATED)
async def create_approval_policy(
    policy_data: ApprovalPolicyCreate,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ApprovalPolicyResponse:
    """Create a reusable approval policy.

    Args:
        policy_data: Approval policy data
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Created approval policy

    Raises:
        HTTPException: If policy with same name already exists or creation fails
    """
    # Check if policy with same name already exists
    existing_policy = crud_approval_policy.get_by_name(
        db, account_id=str(account.id), name=policy_data.name
    )

    if existing_policy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval policy with name '{policy_data.name}' already exists",
        )

    try:
        # Use CRUD layer for proper default policy handling
        new_policy = crud_approval_policy.create(
            db, obj_in=policy_data, account_id=str(account.id)
        )

        logger.info(
            f"Created approval policy '{policy_data.name}' (user: {account.id}, is_default: {new_policy.is_default})"
        )

        return ApprovalPolicyResponse.model_validate(new_policy)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating approval policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating approval policy: {str(e)}",
        )


@router.get("/approval-policies/{policy_id}", response_model=ApprovalPolicyResponse)
async def get_approval_policy(
    policy_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ApprovalPolicyResponse:
    """Get an approval policy by ID.

    Args:
        policy_id: Approval policy ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Approval policy details

    Raises:
        HTTPException: If policy not found or access denied
    """
    policy = crud_approval_policy.get(db, id=policy_id, account_id=str(account.id))

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval policy not found or access denied",
        )

    return ApprovalPolicyResponse.model_validate(policy)


@router.put("/approval-policies/{policy_id}", response_model=ApprovalPolicyResponse)
async def update_approval_policy(
    policy_id: UUID,
    policy_update: ApprovalPolicyUpdate,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ApprovalPolicyResponse:
    """Update an approval policy.

    Args:
        policy_id: Approval policy ID
        policy_update: Updated policy data
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Updated approval policy

    Raises:
        HTTPException: If policy not found or update fails
    """
    policy = crud_approval_policy.get(db, id=policy_id, account_id=str(account.id))

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval policy not found or access denied",
        )

    # Update fields
    update_data = policy_update.model_dump(exclude_unset=True)

    try:
        # Check if name is being updated and if it conflicts
        if "name" in update_data and update_data["name"] != policy.name:
            existing_policy = crud_approval_policy.get_by_name(
                db, account_id=str(account.id), name=update_data["name"]
            )
            if existing_policy and existing_policy.id != policy_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Approval policy with name '{update_data['name']}' already exists",
                )

        # Use CRUD layer for proper default policy handling
        updated_policy = crud_approval_policy.update(
            db, db_obj=policy, obj_in=policy_update
        )

        logger.info(
            f"Updated approval policy {policy_id} for user {account.id} (is_default: {updated_policy.is_default})"
        )

        return ApprovalPolicyResponse.model_validate(updated_policy)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating approval policy {policy_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating approval policy: {str(e)}",
        )


@router.delete("/approval-policies/{policy_id}", status_code=status.HTTP_200_OK)
async def delete_approval_policy(
    policy_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, str]:
    """Delete an approval policy.

    Note: This will set approval_policy_id to NULL for any tool configurations
    using this policy (due to ondelete="SET NULL").

    Args:
        policy_id: Approval policy ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If policy not found or deletion fails
    """
    policy = crud_approval_policy.get(db, id=policy_id, account_id=str(account.id))

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval policy not found or access denied",
        )

    try:
        # Count how many tool configurations use this policy
        tool_count = crud_tool_configuration.count_by_policy(
            db, policy_id=str(policy_id)
        )

        # Use CRUD layer for proper default policy handling
        deleted_policy = crud_approval_policy.remove(
            db, id=policy_id, account_id=str(account.id)
        )

        if not deleted_policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval policy not found or already deleted",
            )

        logger.info(
            f"Deleted approval policy {policy_id} (was used by {tool_count} tools) "
            f"for user {account.id}"
        )

        return {
            "message": f"Approval policy deleted successfully. {tool_count} tool(s) were using this policy."
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting approval policy {policy_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting approval policy: {str(e)}",
        )


# Tool Approval Condition endpoints


@router.get(
    "/tool-configurations/{config_id}/approval-condition",
    response_model=ToolApprovalConditionResponse,
)
async def get_tool_approval_condition(
    config_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ToolApprovalConditionResponse:
    """Get the approval condition for a tool configuration.

    Args:
        config_id: Tool configuration ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Tool approval condition

    Raises:
        HTTPException: If tool configuration not found or condition not found
    """
    # Verify tool configuration exists and belongs to account
    config = crud_tool_configuration.get(
        db, id=str(config_id), account_id=str(account.id)
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool configuration not found or access denied",
        )

    # Get approval condition
    condition = tool_approval_condition.get_by_tool_configuration(
        db, tool_configuration_id=config_id, account_id=account.id
    )

    if not condition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No approval condition found for this tool configuration",
        )

    return ToolApprovalConditionResponse.model_validate(condition)


@router.put(
    "/tool-configurations/{config_id}/approval-condition",
    response_model=ToolApprovalConditionResponse,
)
async def create_or_update_tool_approval_condition(
    config_id: UUID,
    condition_in: ToolApprovalConditionCreate,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ToolApprovalConditionResponse:
    """Create or update the approval condition for a tool configuration.

    Args:
        config_id: Tool configuration ID
        condition_in: Condition data
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Created or updated tool approval condition

    Raises:
        HTTPException: If tool configuration not found or creation fails
    """
    # Verify tool configuration exists and belongs to account
    config = crud_tool_configuration.get(
        db, id=str(config_id), account_id=str(account.id)
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool configuration not found or access denied",
        )

    # Validate CEL expression if provided (proprietary feature)
    if condition_in.condition_expression:
        try:
            # Test with empty args to check syntax
            evaluate_cel_expression(condition_in.condition_expression, {})
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid CEL expression: {str(e)}",
            )

    try:
        # Create or update condition
        condition = tool_approval_condition.create_or_update(
            db,
            tool_configuration_id=config_id,
            account_id=account.id,
            name=condition_in.name,
            description=condition_in.description,
            is_enabled=condition_in.is_enabled,
            condition_type=condition_in.condition_type,
            condition_expression=condition_in.condition_expression,
            condition_config=condition_in.condition_config,
        )

        db.commit()
        db.refresh(condition)

        logger.info(
            f"Created/updated approval condition for tool config {config_id} "
            f"(account: {account.id})"
        )

        return ToolApprovalConditionResponse.model_validate(condition)

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error creating/updating approval condition for tool config {config_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating/updating approval condition: {str(e)}",
        )


@router.delete(
    "/tool-configurations/{config_id}/approval-condition",
    status_code=status.HTTP_200_OK,
)
async def delete_tool_approval_condition(
    config_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, str]:
    """Delete the approval condition for a tool configuration.

    Args:
        config_id: Tool configuration ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If tool configuration not found or condition not found
    """
    # Verify tool configuration exists and belongs to account
    config = crud_tool_configuration.get(
        db, id=str(config_id), account_id=str(account.id)
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool configuration not found or access denied",
        )

    # Get and delete approval condition
    condition = tool_approval_condition.get_by_tool_configuration(
        db, tool_configuration_id=config_id, account_id=account.id
    )

    if not condition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No approval condition found for this tool configuration",
        )

    try:
        tool_approval_condition.remove(db, id=condition.id)
        db.commit()

        logger.info(
            f"Deleted approval condition for tool config {config_id} "
            f"(account: {account.id})"
        )

        return {"message": "Approval condition deleted successfully"}

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error deleting approval condition for tool config {config_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting approval condition: {str(e)}",
        )


@router.post(
    "/tool-configurations/{config_id}/approval-condition/test",
    response_model=ConditionTestResponse,
)
async def test_approval_condition(
    config_id: UUID,
    test_request: ConditionTestRequest,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> ConditionTestResponse:
    """Test a CEL expression against sample arguments.

    This endpoint allows testing approval conditions before saving them.
    It's a proprietary feature for validating CEL expressions.

    Args:
        config_id: Tool configuration ID
        test_request: Test request with expression and sample args
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Test result with match status and evaluation context

    Raises:
        HTTPException: If tool configuration not found or evaluation fails
    """
    # Verify tool configuration exists and belongs to account
    config = crud_tool_configuration.get(
        db, id=str(config_id), account_id=str(account.id)
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool configuration not found or access denied",
        )

    try:
        # Evaluate CEL expression
        matches = evaluate_cel_expression(
            test_request.expression, test_request.sample_args
        )

        return ConditionTestResponse(
            matches=matches,
            error=None,
            evaluation_context={
                "expression": test_request.expression,
                "sample_args": test_request.sample_args,
                "result": matches,
            },
        )

    except Exception as e:
        logger.warning(
            f"CEL expression evaluation failed for tool config {config_id}: {e}"
        )

        return ConditionTestResponse(
            matches=False,
            error=str(e),
            evaluation_context={
                "expression": test_request.expression,
                "sample_args": test_request.sample_args,
            },
        )
