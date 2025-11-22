"""Tests for MCP server schema serialization."""

import uuid
from datetime import datetime, timezone


from spacemodels.models.mcp_server import MCPServer
from spacemodels.schemas.mcp_server import MCPServerResponse, MCPServerCreate


def test_mcp_server_response_serializes_uuids():
    """Test that MCPServerResponse correctly serializes UUID fields to strings.

    This test verifies the fix for the bug where account_id (a UUID in the model)
    was not being properly serialized to a string in the response schema.
    """
    # Create a mock MCPServer with UUID fields
    test_id = uuid.uuid4()
    test_account_id = uuid.uuid4()

    server = MCPServer(
        id=test_id,
        name="Test Server",
        url="http://localhost:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_account_id,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # This should not raise a ValidationError
    response = MCPServerResponse.model_validate(server)

    # Verify the fields are properly set
    assert response.name == "Test Server"
    assert response.url == "http://localhost:8080/mcp"
    assert response.status == "active"

    # Verify UUID fields are serialized to strings when dumped
    response_dict = response.model_dump()
    assert isinstance(response_dict["id"], str)
    assert isinstance(response_dict["account_id"], str)
    assert response_dict["id"] == str(test_id)
    assert response_dict["account_id"] == str(test_account_id)


def test_mcp_server_response_serializes_to_json():
    """Test that MCPServerResponse can be serialized to JSON.

    This verifies that all UUID fields are properly serialized and
    the schema can be used in FastAPI responses.
    """
    test_id = uuid.uuid4()
    test_account_id = uuid.uuid4()

    server = MCPServer(
        id=test_id,
        name="Test Server",
        url="http://localhost:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_account_id,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    response = MCPServerResponse.model_validate(server)

    # This should not raise a TypeError about UUID not being JSON serializable
    json_str = response.model_dump_json()

    # Verify the JSON contains string representations of UUIDs
    assert str(test_id) in json_str
    assert str(test_account_id) in json_str


def test_mcp_server_create_schema():
    """Test that MCPServerCreate schema validates correctly."""
    create_data = {
        "name": "New Server",
        "url": "http://localhost:8080/mcp",
        "transport": "http-streaming",
        "auth_type": "none",
    }

    schema = MCPServerCreate(**create_data)
    assert schema.name == "New Server"
    assert schema.url == "http://localhost:8080/mcp"
    assert schema.transport == "http-streaming"
    assert schema.auth_type == "none"


def test_mcp_server_create_with_optional_fields():
    """Test MCPServerCreate with optional fields."""
    create_data = {
        "name": "New Server",
        "url": "http://localhost:8080/mcp",
        "transport": "sse",
        "auth_type": "bearer",
        "auth_config": {"token": "secret-token"},
        "status": "disabled",
    }

    schema = MCPServerCreate(**create_data)
    assert schema.name == "New Server"
    assert schema.url == "http://localhost:8080/mcp"
    assert schema.transport == "sse"
    assert schema.auth_type == "bearer"
    assert schema.auth_config == {"token": "secret-token"}
    assert schema.status == "disabled"


def test_mcp_server_response_handles_none_values():
    """Test that MCPServerResponse handles None values for optional fields."""
    test_id = uuid.uuid4()
    test_account_id = uuid.uuid4()

    server = MCPServer(
        id=test_id,
        name="Test Server",
        url="http://localhost:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_account_id,
        status="active",
        last_scan_at=None,
        last_error=None,
        auth_config=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    response = MCPServerResponse.model_validate(server)
    response_dict = response.model_dump()

    assert response_dict["last_scan_at"] is None
    assert response_dict["last_error"] is None
    assert response_dict["auth_config"] is None


def test_mcp_server_response_with_error_state():
    """Test MCPServerResponse with error status and error message."""
    test_id = uuid.uuid4()
    test_account_id = uuid.uuid4()

    server = MCPServer(
        id=test_id,
        name="Failing Server",
        url="http://unreachable:8080/mcp",
        transport="http-streaming",
        auth_type="none",
        account_id=test_account_id,
        status="error",
        last_error="Connection refused",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    response = MCPServerResponse.model_validate(server)
    response_dict = response.model_dump()

    assert response_dict["status"] == "error"
    assert response_dict["last_error"] == "Connection refused"
    assert isinstance(response_dict["id"], str)
    assert isinstance(response_dict["account_id"], str)
