"""Tests for MCP server management endpoints."""

import pytest
import uuid
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from spacemodels.models.mcp_server import MCPServer


@pytest.fixture(autouse=True)
def mock_event_bus_connect():
    """Auto-mock the event bus connect method to avoid NATS connection attempts."""
    with patch(
        "spacesync.services.event_bus.EventBus.connect", new_callable=AsyncMock
    ) as mock_connect:
        yield mock_connect


@pytest.fixture(autouse=True)
def mock_mcp_client():
    """Auto-mock MCPClient to avoid actual connection attempts."""
    with patch("spacebridge.services.mcp_client_pool.MCPClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_instance.connect = AsyncMock()
        mock_instance.close = AsyncMock()
        mock_client_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_tool_scan():
    """Auto-mock tool scanning to avoid actual MCP server connections."""
    with patch(
        "spacebridge.api.endpoints.mcp_servers.scan_mcp_server_tools",
        new_callable=AsyncMock,
    ) as mock_scan:
        mock_scan.return_value = []
        yield mock_scan


def test_list_mcp_servers_empty(client: TestClient, db_session):
    """Test listing MCP servers when none exist."""
    response = client.get("/api/v1/mcp-servers")
    assert response.status_code == 200
    assert response.json() == []


def test_list_mcp_servers_with_data(client: TestClient, db_session, test_user):
    """Test listing MCP servers with existing data.

    This test verifies that:
    1. MCP servers are properly retrieved from the database
    2. UUID fields (id, account_id) are correctly serialized to strings
    3. The response matches the MCPServerResponse schema
    """
    server = MCPServer(
        name="Test MCP Server",
        url="http://localhost:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_user.account_id,
        status="active",
    )
    db_session.add(server)
    db_session.commit()
    db_session.refresh(server)

    response = client.get("/api/v1/mcp-servers")
    assert response.status_code == 200

    response_json = response.json()
    assert len(response_json) == 1

    server_data = response_json[0]
    assert server_data["name"] == "Test MCP Server"
    assert server_data["url"] == "http://localhost:8080/mcp"

    # Critical: Verify UUID fields are serialized to strings, not UUID objects
    assert isinstance(server_data["id"], str)
    assert isinstance(server_data["account_id"], str)
    assert server_data["id"] == str(server.id)
    assert server_data["account_id"] == str(server.account_id)


def test_create_mcp_server_success(client: TestClient, db_session, test_user):
    """Test creating an MCP server successfully.

    This test specifically verifies the bug fix:
    - account_id should be serialized to string in the response
    - The schema should accept UUID from the model and serialize it
    """
    server_data = {
        "name": "New MCP Server",
        "url": "http://localhost:8080/mcp",
        "transport": "http-streaming",
        "auth_type": "none",
    }

    response = client.post("/api/v1/mcp-servers", json=server_data)
    assert response.status_code == 201

    response_json = response.json()
    assert response_json["name"] == "New MCP Server"
    assert response_json["url"] == "http://localhost:8080/mcp"
    assert response_json["status"] == "active"

    # Critical: Verify UUID serialization (this is the bug we're testing for)
    assert isinstance(response_json["id"], str)
    assert isinstance(response_json["account_id"], str)

    # Verify the UUID can be parsed
    try:
        uuid.UUID(response_json["id"])
        uuid.UUID(response_json["account_id"])
    except ValueError:
        pytest.fail("id or account_id is not a valid UUID string")

    # Verify it was actually saved to the database
    server_id = uuid.UUID(response_json["id"])
    db_server = db_session.query(MCPServer).filter(MCPServer.id == server_id).first()
    assert db_server is not None
    assert db_server.name == "New MCP Server"
    assert db_server.account_id == test_user.account_id


def test_create_mcp_server_duplicate_name(client: TestClient, db_session, test_user):
    """Test creating an MCP server with a duplicate name."""
    # Create first server
    server = MCPServer(
        name="Duplicate Server",
        url="http://localhost:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_user.account_id,
        status="active",
    )
    db_session.add(server)
    db_session.commit()

    # Try to create another with the same name
    server_data = {
        "name": "Duplicate Server",
        "url": "http://localhost:9090/mcp",
        "transport": "http-streaming",
        "auth_type": "none",
    }

    response = client.post("/api/v1/mcp-servers", json=server_data)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_mcp_server_with_connection_error(
    client: TestClient, db_session, test_user, mock_mcp_client
):
    """Test creating an MCP server when connection validation fails.

    The server should still be created but with error status.
    """
    # Make the mock client raise an error on connect
    mock_mcp_client.connect.side_effect = Exception("Connection refused")

    server_data = {
        "name": "Failing Server",
        "url": "http://unreachable:8080/mcp",
        "transport": "http-streaming",
        "auth_type": "none",
    }

    response = client.post("/api/v1/mcp-servers", json=server_data)
    assert response.status_code == 201

    response_json = response.json()
    assert response_json["name"] == "Failing Server"
    assert response_json["status"] == "error"
    assert response_json["last_error"] is not None
    assert "Connection refused" in response_json["last_error"]

    # Still verify UUID serialization works even with error status
    assert isinstance(response_json["id"], str)
    assert isinstance(response_json["account_id"], str)


def test_get_mcp_server_success(client: TestClient, db_session, test_user):
    """Test getting a single MCP server by ID."""
    server = MCPServer(
        name="Test Server",
        url="http://localhost:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_user.account_id,
        status="active",
    )
    db_session.add(server)
    db_session.commit()
    db_session.refresh(server)

    response = client.get(f"/api/v1/mcp-servers/{server.id}")
    assert response.status_code == 200

    response_json = response.json()
    assert response_json["name"] == "Test Server"
    assert isinstance(response_json["id"], str)
    assert isinstance(response_json["account_id"], str)


def test_get_mcp_server_not_found(client: TestClient, db_session, test_user):
    """Test getting a non-existent MCP server."""
    fake_id = uuid.uuid4()
    response = client.get(f"/api/v1/mcp-servers/{fake_id}")
    assert response.status_code == 404


def test_update_mcp_server_success(client: TestClient, db_session, test_user):
    """Test updating an MCP server."""
    server = MCPServer(
        name="Original Name",
        url="http://localhost:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_user.account_id,
        status="active",
    )
    db_session.add(server)
    db_session.commit()
    db_session.refresh(server)

    update_data = {
        "name": "Updated Name",
        "status": "disabled",
    }

    response = client.put(f"/api/v1/mcp-servers/{server.id}", json=update_data)
    assert response.status_code == 200

    response_json = response.json()
    assert response_json["name"] == "Updated Name"
    assert response_json["status"] == "disabled"

    # Verify UUID serialization on update
    assert isinstance(response_json["id"], str)
    assert isinstance(response_json["account_id"], str)


def test_delete_mcp_server_success(client: TestClient, db_session, test_user):
    """Test deleting an MCP server."""
    server = MCPServer(
        name="Server to Delete",
        url="http://localhost:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_user.account_id,
        status="active",
    )
    db_session.add(server)
    db_session.commit()
    db_session.refresh(server)

    response = client.delete(f"/api/v1/mcp-servers/{server.id}")
    assert response.status_code == 200

    # Verify the server is deleted from database
    deleted = db_session.query(MCPServer).filter(MCPServer.id == server.id).first()
    assert deleted is None


def test_delete_mcp_server_not_found(client: TestClient, db_session, test_user):
    """Test deleting a non-existent MCP server."""
    fake_id = uuid.uuid4()
    response = client.delete(f"/api/v1/mcp-servers/{fake_id}")
    assert response.status_code == 404


def test_schema_serialization_with_real_model(db_session, test_user):
    """Direct unit test for schema serialization with real database model.

    This test verifies the fix at the schema level:
    - MCPServer model has account_id as UUID
    - MCPServerResponse schema should accept UUID and serialize to string
    """
    from spacemodels.schemas.mcp_server import MCPServerResponse

    # Create a real MCPServer model instance with UUID account_id
    server = MCPServer(
        name="Schema Test Server",
        url="http://localhost:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_user.account_id,  # This is a UUID
        status="active",
    )
    db_session.add(server)
    db_session.commit()
    db_session.refresh(server)

    # Verify the model has UUID types
    assert isinstance(server.id, uuid.UUID)
    assert isinstance(server.account_id, uuid.UUID)

    # This should not raise a ValidationError anymore
    response = MCPServerResponse.model_validate(server)

    # Verify the response has serialized UUIDs to strings
    response_dict = response.model_dump()
    assert isinstance(response_dict["id"], str)
    assert isinstance(response_dict["account_id"], str)
    assert response_dict["id"] == str(server.id)
    assert response_dict["account_id"] == str(server.account_id)
