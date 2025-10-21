"""MCP Servers router for managing external MCP server connections."""

import logging
from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from spacebridge.api.common import get_account_for_user
from spacebridge.services.mcp_tool_discovery import (
    get_cached_tools_for_server,
    scan_mcp_server_tools,
)
from spacemodels.crud import crud_mcp_server
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.mcp_server import MCPServer
from spacemodels.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
)
from spacemodels.schemas.mcp_tool import MCPToolResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/mcp-servers", status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    server_data: MCPServerCreate,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> MCPServerResponse:
    """Create a new external MCP server configuration.

    Args:
        server_data: MCP server configuration data
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Created MCP server

    Raises:
        HTTPException: If creation fails or validation fails
    """
    logger.info(f"User {account.username} creating MCP server: {server_data.name}")

    # Check if server with same name already exists for this account
    existing_server = crud_mcp_server.get_by_name(
        db, account_id=str(account.id), name=server_data.name
    )

    if existing_server:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MCP server with name '{server_data.name}' already exists",
        )

    # Validate connection to the MCP server before saving
    from spacebridge.services.mcp_client_pool import MCPClient

    validation_error = None
    try:
        logger.info(f"Validating connection to MCP server at {server_data.url}")
        test_client = MCPClient(
            url=server_data.url,
            auth_type=server_data.auth_type or "none",
            auth_config=server_data.auth_config,
            transport=server_data.transport or "http-streaming",
        )

        # Try to connect and initialize
        await test_client.connect()
        logger.info(f"✓ Successfully validated MCP server at {server_data.url}")
        await test_client.close()

    except Exception as e:
        validation_error = str(e)
        logger.warning(f"Failed to validate MCP server at {server_data.url}: {e}")
        # Don't raise here - we'll store the error and mark status as 'error'

    # Create new MCP server
    try:
        new_server = MCPServer(
            account_id=str(account.id),
            name=server_data.name,
            url=server_data.url,
            transport=server_data.transport or "http-streaming",
            auth_type=server_data.auth_type or "none",
            auth_config=server_data.auth_config,
            status="error" if validation_error else "active",
            last_error=validation_error if validation_error else None,
        )

        db.add(new_server)
        db.commit()
        db.refresh(new_server)

        if validation_error:
            logger.warning(
                f"Created MCP server {new_server.id} with error status: {validation_error}"
            )
        else:
            logger.info(
                f"Created MCP server {new_server.id} for user {account.username}"
            )

            # Automatically scan for tools on successful creation
            try:
                logger.info(f"Auto-scanning MCP server {new_server.id} for tools")
                tools = await scan_mcp_server_tools(new_server.id, db)
                logger.info(
                    f"Auto-scan complete: discovered {len(tools)} tools for {new_server.name}"
                )
            except Exception as e:
                logger.warning(f"Auto-scan failed for {new_server.id}: {e}")
                # Don't fail the creation if scan fails - user can manually rescan

        return MCPServerResponse.model_validate(new_server)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating MCP server: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating MCP server: {str(e)}",
        )


@router.get("/mcp-servers", response_model=List[MCPServerResponse])
async def list_mcp_servers(
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> List[MCPServerResponse]:
    """List all MCP servers for the current user.

    Args:
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        List of MCP servers
    """
    servers = crud_mcp_server.get_multi_by_account(db, account_id=str(account.id))

    return [MCPServerResponse.model_validate(server) for server in servers]


@router.get("/mcp-servers/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> MCPServerResponse:
    """Get a specific MCP server by ID.

    Args:
        server_id: MCP server ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        MCP server details

    Raises:
        HTTPException: If server not found or access denied
    """
    server = crud_mcp_server.get(db, id=server_id, account_id=str(account.id))

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found or access denied",
        )

    return MCPServerResponse.model_validate(server)


@router.put("/mcp-servers/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: UUID,
    server_update: MCPServerUpdate,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> MCPServerResponse:
    """Update an existing MCP server configuration.

    Args:
        server_id: MCP server ID
        server_update: Updated server data
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Updated MCP server

    Raises:
        HTTPException: If server not found or update fails
    """
    server = crud_mcp_server.get(db, id=server_id, account_id=str(account.id))

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found or access denied",
        )

    # Update fields
    update_data = server_update.model_dump(exclude_unset=True)

    try:
        for field, value in update_data.items():
            setattr(server, field, value)

        db.commit()
        db.refresh(server)

        logger.info(f"Updated MCP server {server_id} for user {account.username}")

        return MCPServerResponse.model_validate(server)

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating MCP server {server_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating MCP server: {str(e)}",
        )


@router.delete("/mcp-servers/{server_id}", status_code=status.HTTP_200_OK)
async def delete_mcp_server(
    server_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, str]:
    """Delete an MCP server.

    Args:
        server_id: MCP server ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If server not found or deletion fails
    """
    server = crud_mcp_server.get(db, id=server_id, account_id=str(account.id))

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found or access denied",
        )

    try:
        db.delete(server)
        db.commit()

        logger.info(f"Deleted MCP server {server_id} for user {account.username}")

        return {"message": "MCP server deleted successfully"}

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting MCP server {server_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting MCP server: {str(e)}",
        )


@router.post("/mcp-servers/{server_id}/scan", status_code=status.HTTP_200_OK)
async def scan_mcp_server(
    server_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, str]:
    """Trigger a tool discovery scan for an MCP server.

    Args:
        server_id: MCP server ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        Success message with tool count

    Raises:
        HTTPException: If server not found or scan fails
    """
    server = crud_mcp_server.get(db, id=server_id, account_id=str(account.id))

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found or access denied",
        )

    try:
        logger.info(
            f"User {account.username} triggering scan for MCP server {server_id}"
        )

        tools = await scan_mcp_server_tools(server_id, db)

        logger.info(
            f"Scan complete for MCP server {server_id}: {len(tools)} tools discovered"
        )

        return {
            "message": f"Scan completed successfully. Discovered {len(tools)} tools.",
            "tool_count": str(len(tools)),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error scanning MCP server {server_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scanning MCP server: {str(e)}",
        )


@router.get("/mcp-servers/{server_id}/tools", response_model=List[MCPToolResponse])
async def list_mcp_server_tools(
    server_id: UUID,
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> List[MCPToolResponse]:
    """List discovered tools for an MCP server.

    Args:
        server_id: MCP server ID
        account: Current user's account (from dependency)
        db: Database session

    Returns:
        List of discovered tools

    Raises:
        HTTPException: If server not found or access denied
    """
    server = crud_mcp_server.get(db, id=server_id, account_id=str(account.id))

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found or access denied",
        )

    try:
        tools = await get_cached_tools_for_server(server_id, db)

        return [MCPToolResponse.model_validate(tool) for tool in tools]

    except Exception as e:
        logger.error(
            f"Error listing tools for MCP server {server_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing tools: {str(e)}",
        )
