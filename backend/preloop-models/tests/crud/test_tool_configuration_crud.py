"""Tests for tool_configuration CRUD operations."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from preloop_models.crud.tool_configuration import CRUDToolConfiguration
from preloop_models.schemas.tool_configuration import (
    ToolConfigurationCreate,
    ToolConfigurationUpdate,
)


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_tool_config():
    """Fixture for a CRUDToolConfiguration instance."""
    return CRUDToolConfiguration()


def test_get(crud_tool_config, mock_db_session):
    """Test retrieving a tool configuration by ID."""
    # Arrange
    config_id = str(uuid4())
    account_id = str(uuid4())
    mock_config = MagicMock()
    mock_config.id = config_id
    mock_config.account_id = account_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_config

    # Act
    result = crud_tool_config.get(mock_db_session, id=config_id, account_id=account_id)

    # Assert
    assert result.id == config_id
    assert result.account_id == account_id


def test_get_by_tool_name_and_source(crud_tool_config, mock_db_session):
    """Test retrieving a tool configuration by tool name and source."""
    # Arrange
    account_id = str(uuid4())
    tool_name = "create_issue"
    tool_source = "builtin"
    mock_config = MagicMock()
    mock_config.account_id = account_id
    mock_config.tool_name = tool_name
    mock_config.tool_source = tool_source

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_config

    # Act
    result = crud_tool_config.get_by_tool_name_and_source(
        mock_db_session,
        account_id=account_id,
        tool_name=tool_name,
        tool_source=tool_source,
    )

    # Assert
    assert result.tool_name == tool_name
    assert result.tool_source == tool_source
    assert result.account_id == account_id


def test_create(crud_tool_config, mock_db_session):
    """Test creating a tool configuration."""
    # Arrange
    config_in = ToolConfigurationCreate(
        account_id=str(uuid4()),
        tool_name="create_issue",
        tool_source="builtin",
        is_enabled=True,
    )
    mock_db_session.add = MagicMock()
    mock_db_session.commit = MagicMock()
    mock_db_session.refresh = MagicMock(
        side_effect=lambda obj: setattr(obj, "id", uuid4())
    )

    # Act
    result = crud_tool_config.create(mock_db_session, config_in=config_in)
    assert result.id is not None

    # Assert
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


def test_update(crud_tool_config, mock_db_session):
    """Test updating a tool configuration."""
    # Arrange
    db_obj = MagicMock()
    db_obj.id = uuid4()
    db_obj.account_id = str(uuid4())
    db_obj.is_enabled = False
    config_in = ToolConfigurationUpdate(is_enabled=True)

    mock_db_session.add = MagicMock()
    mock_db_session.commit = MagicMock()
    mock_db_session.refresh = MagicMock()

    # Act
    result = crud_tool_config.update(
        mock_db_session, db_obj=db_obj, config_in=config_in
    )

    # Assert
    assert result.is_enabled is True
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


def test_remove(crud_tool_config, mock_db_session):
    """Test removing a tool configuration."""
    # Arrange
    config_id = str(uuid4())
    account_id = str(uuid4())
    mock_config = MagicMock()
    mock_config.id = config_id
    mock_config.account_id = account_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_config
    mock_db_session.delete = MagicMock()
    mock_db_session.commit = MagicMock()

    # Act
    result = crud_tool_config.remove(
        mock_db_session, id=config_id, account_id=account_id
    )

    # Assert
    assert result.id == config_id
    mock_db_session.delete.assert_called_once_with(mock_config)
    mock_db_session.commit.assert_called_once()


def test_remove_not_found(crud_tool_config, mock_db_session):
    """Test removing a non-existent tool configuration."""
    # Arrange
    config_id = str(uuid4())
    account_id = str(uuid4())

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_db_session.delete = MagicMock()
    mock_db_session.commit = MagicMock()

    # Act
    result = crud_tool_config.remove(
        mock_db_session, id=config_id, account_id=account_id
    )

    # Assert
    assert result is None
    mock_db_session.delete.assert_not_called()
    mock_db_session.commit.assert_not_called()


def test_get_by_source(crud_tool_config, mock_db_session):
    """Test retrieving tool configurations by source."""
    # Arrange
    account_id = str(uuid4())
    tool_source = "mcp"
    mock_config1 = MagicMock()
    mock_config1.account_id = account_id
    mock_config1.tool_source = tool_source
    mock_config2 = MagicMock()
    mock_config2.account_id = account_id
    mock_config2.tool_source = tool_source
    mock_configs = [mock_config1, mock_config2]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_configs

    # Act
    result = crud_tool_config.get_by_source(
        mock_db_session, account_id=account_id, tool_source=tool_source
    )

    # Assert
    assert len(result) == 2
    assert all(config.tool_source == tool_source for config in result)


def test_count_by_policy(crud_tool_config, mock_db_session):
    """Test counting tool configurations by policy."""
    # Arrange
    policy_id = str(uuid4())
    expected_count = 5

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = expected_count

    # Act
    result = crud_tool_config.count_by_policy(mock_db_session, policy_id=policy_id)

    # Assert
    assert result == expected_count
