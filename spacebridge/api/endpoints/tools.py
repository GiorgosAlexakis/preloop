"""Tools router for managing available tools and their configurations."""

import logging
from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from spacebridge.api.common import get_account_for_user
from spacemodels.crud import (
    crud_approval_policy,
    crud_mcp_server,
    crud_mcp_tool,
    crud_tool_configuration,
)
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.tool_configuration import ApprovalPolicy, ToolConfiguration
from spacemodels.schemas.tool_configuration import (
    ApprovalPolicyCreate,
    ApprovalPolicyResponse,
    ApprovalPolicyUpdate,
    ToolConfigurationCreate,
    ToolConfigurationResponse,
    ToolConfigurationUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Define builtin tools metadata
BUILTIN_TOOLS = [
    {
        "name": "get_issue",
        "description": "Get detailed information about an issue by its identifier (URL, key, or ID)",
        "source": "builtin",
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
        "schema": {
            "type": "object",
            "properties": {
                "issues": {"type": "array", "items": {"type": "string"}},
                "compliance_metric": {"type": "string", "default": "DoR"},
            },
            "required": ["issues"],
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

    tools = []

    # Add builtin tools
    for builtin_tool in BUILTIN_TOOLS:
        config = config_map.get((builtin_tool["name"], "builtin", None))
        tools.append(
            {
                "name": builtin_tool["name"],
                "description": builtin_tool["description"],
                "source": "builtin",
                "source_id": None,
                "source_name": "Built-in",
                "schema": builtin_tool["schema"],
                "is_enabled": config.is_enabled if config else True,
                "requires_approval": config.requires_approval if config else False,
                "has_approval_policy": config.approval_policy_id is not None
                if config
                else False,
                "approval_policy_id": str(config.approval_policy_id)
                if config and config.approval_policy_id
                else None,
                "config_id": str(config.id) if config else None,
            }
        )

    # Add external MCP tools
    mcp_servers = crud_mcp_server.get_active_by_account(db, account_id=str(account.id))

    for server in mcp_servers:
        mcp_tools = crud_mcp_tool.get_by_server(db, server_id=server.id)

        for mcp_tool in mcp_tools:
            config = config_map.get((mcp_tool.name, "mcp", str(server.id)))
            tools.append(
                {
                    "name": mcp_tool.name,
                    "description": mcp_tool.description or "",
                    "source": "mcp",
                    "source_id": str(server.id),
                    "source_name": server.name,
                    "schema": mcp_tool.input_schema,
                    "is_enabled": config.is_enabled if config else True,
                    "requires_approval": config.requires_approval if config else False,
                    "has_approval_policy": config.approval_policy_id is not None
                    if config
                    else False,
                    "approval_policy_id": str(config.approval_policy_id)
                    if config and config.approval_policy_id
                    else None,
                    "config_id": str(config.id) if config else None,
                }
            )

    logger.info(
        f"Returning {len(tools)} tools for user {account.username} "
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
            requires_approval=config_data.requires_approval
            if config_data.requires_approval is not None
            else False,
            tool_description=config_data.tool_description,
            tool_schema=config_data.tool_schema,
            custom_config=config_data.custom_config,
        )

        db.add(new_config)
        db.commit()
        db.refresh(new_config)

        logger.info(
            f"Created tool configuration for {config_data.tool_name} "
            f"(user: {account.username})"
        )

        return ToolConfigurationResponse.model_validate(new_config)

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

        logger.info(
            f"Updated tool configuration {config_id} for user {account.username}"
        )

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

        logger.info(
            f"Deleted tool configuration {config_id} for user {account.username}"
        )

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

    logger.info(
        f"Returning {len(policies)} approval policies for user {account.username}"
    )

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
        new_policy = ApprovalPolicy(
            account_id=str(account.id),
            name=policy_data.name,
            description=policy_data.description,
            approval_type=policy_data.approval_type,
            channel=policy_data.channel,
            user=policy_data.user,
            approval_config=policy_data.approval_config,
            timeout_seconds=policy_data.timeout_seconds or 300,
            require_reason=policy_data.require_reason
            if policy_data.require_reason is not None
            else False,
        )

        db.add(new_policy)
        db.commit()
        db.refresh(new_policy)

        logger.info(
            f"Created approval policy '{policy_data.name}' (user: {account.username})"
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

        for field, value in update_data.items():
            setattr(policy, field, value)

        db.commit()
        db.refresh(policy)

        logger.info(f"Updated approval policy {policy_id} for user {account.username}")

        return ApprovalPolicyResponse.model_validate(policy)

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

        db.delete(policy)
        db.commit()

        logger.info(
            f"Deleted approval policy {policy_id} (was used by {tool_count} tools) "
            f"for user {account.username}"
        )

        return {
            "message": f"Approval policy deleted successfully. {tool_count} tool(s) were using this policy."
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting approval policy {policy_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting approval policy: {str(e)}",
        )
