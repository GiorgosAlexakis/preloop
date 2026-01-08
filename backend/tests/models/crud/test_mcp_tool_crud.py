"""Tests for mcp_tool CRUD operations."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from preloop.models.crud.mcp_tool import CRUDMCPTool


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_mcp_tool():
    """Fixture for a CRUDMCPTool instance."""
    return CRUDMCPTool()


def test_get(crud_mcp_tool, mock_db_session):
    """Test retrieving an MCP tool by ID."""
    # Arrange
    tool_id = uuid4()
    mock_tool = MagicMock()
    mock_tool.id = tool_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_tool

    # Act
    result = crud_mcp_tool.get(mock_db_session, id=tool_id)

    # Assert
    assert result.id == tool_id
    mock_db_session.query.assert_called_once()


def test_get_by_server(crud_mcp_tool, mock_db_session):
    """Test retrieving all tools for a specific MCP server."""
    # Arrange
    server_id = uuid4()
    mock_tool1 = MagicMock()
    mock_tool1.mcp_server_id = server_id
    mock_tool2 = MagicMock()
    mock_tool2.mcp_server_id = server_id
    mock_tools = [mock_tool1, mock_tool2]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_tools

    # Act
    result = crud_mcp_tool.get_by_server(mock_db_session, server_id=server_id)

    # Assert
    assert len(result) == 2
    assert all(tool.mcp_server_id == server_id for tool in result)


def test_get_by_server_and_name(crud_mcp_tool, mock_db_session):
    """Test retrieving a tool by server ID and tool name."""
    # Arrange
    server_id = uuid4()
    tool_name = "create_issue"
    mock_tool = MagicMock()
    mock_tool.mcp_server_id = server_id
    mock_tool.name = tool_name

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_tool

    # Act
    result = crud_mcp_tool.get_by_server_and_name(
        mock_db_session, server_id=server_id, name=tool_name
    )

    # Assert
    assert result.mcp_server_id == server_id
    assert result.name == tool_name


def test_get_multi(crud_mcp_tool, mock_db_session):
    """Test retrieving multiple MCP tools."""
    # Arrange
    mock_tools = [MagicMock(), MagicMock(), MagicMock()]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_tools

    # Act
    result = crud_mcp_tool.get_multi(mock_db_session, skip=0, limit=100)

    # Assert
    assert len(result) == 3


def test_remove(crud_mcp_tool, mock_db_session):
    """Test removing an MCP tool by ID."""
    # Arrange
    tool_id = uuid4()
    mock_tool = MagicMock()
    mock_tool.id = tool_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_tool
    mock_db_session.delete = MagicMock()
    mock_db_session.commit = MagicMock()

    # Act
    result = crud_mcp_tool.remove(mock_db_session, id=tool_id)

    # Assert
    assert result.id == tool_id
    mock_db_session.delete.assert_called_once_with(mock_tool)
    mock_db_session.commit.assert_called_once()


def test_remove_not_found(crud_mcp_tool, mock_db_session):
    """Test removing a non-existent MCP tool."""
    # Arrange
    tool_id = uuid4()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_db_session.delete = MagicMock()
    mock_db_session.commit = MagicMock()

    # Act
    result = crud_mcp_tool.remove(mock_db_session, id=tool_id)

    # Assert
    assert result is None
    mock_db_session.delete.assert_not_called()
    mock_db_session.commit.assert_not_called()


def test_remove_by_server(crud_mcp_tool, mock_db_session):
    """Test removing all tools for a specific MCP server."""
    # Arrange
    server_id = uuid4()
    expected_delete_count = 3

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.delete.return_value = expected_delete_count
    mock_db_session.commit = MagicMock()

    # Act
    result = crud_mcp_tool.remove_by_server(mock_db_session, server_id=server_id)

    # Assert
    assert result == expected_delete_count
    mock_db_session.commit.assert_called_once()
