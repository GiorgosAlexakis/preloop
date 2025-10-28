"""Tests for approval_policy CRUD operations."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from spacemodels.crud.approval_policy import CRUDApprovalPolicy


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_approval_policy():
    """Fixture for a CRUDApprovalPolicy instance."""
    return CRUDApprovalPolicy()


def test_get(crud_approval_policy, mock_db_session):
    """Test retrieving an approval policy by ID."""
    # Arrange
    policy_id = uuid4()
    account_id = str(uuid4())
    mock_policy = MagicMock()
    mock_policy.id = policy_id
    mock_policy.account_id = account_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_policy

    # Act
    result = crud_approval_policy.get(
        mock_db_session, id=policy_id, account_id=account_id
    )

    # Assert
    assert result.id == policy_id
    assert result.account_id == account_id


def test_get_by_name(crud_approval_policy, mock_db_session):
    """Test retrieving an approval policy by name and account."""
    # Arrange
    account_id = str(uuid4())
    policy_name = "test-policy"
    mock_policy = MagicMock()
    mock_policy.name = policy_name
    mock_policy.account_id = account_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_policy

    # Act
    result = crud_approval_policy.get_by_name(
        mock_db_session, account_id=account_id, name=policy_name
    )

    # Assert
    assert result.name == policy_name
    assert result.account_id == account_id


def test_get_multi_by_account(crud_approval_policy, mock_db_session):
    """Test retrieving approval policies for a specific account."""
    # Arrange
    account_id = str(uuid4())
    mock_policy1 = MagicMock()
    mock_policy1.account_id = account_id
    mock_policy2 = MagicMock()
    mock_policy2.account_id = account_id
    mock_policies = [mock_policy1, mock_policy2]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_policies

    # Act
    result = crud_approval_policy.get_multi_by_account(
        mock_db_session, account_id=account_id, skip=0, limit=100
    )

    # Assert
    assert len(result) == 2
    assert all(policy.account_id == account_id for policy in result)


def test_remove(crud_approval_policy, mock_db_session):
    """Test removing an approval policy by ID."""
    # Arrange
    policy_id = uuid4()
    account_id = str(uuid4())
    mock_policy = MagicMock()
    mock_policy.id = policy_id
    mock_policy.account_id = account_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_policy
    mock_db_session.delete = MagicMock()
    mock_db_session.commit = MagicMock()

    # Act
    result = crud_approval_policy.remove(
        mock_db_session, id=policy_id, account_id=account_id
    )

    # Assert
    assert result.id == policy_id
    mock_db_session.delete.assert_called_once_with(mock_policy)
    mock_db_session.commit.assert_called_once()


def test_remove_not_found(crud_approval_policy, mock_db_session):
    """Test removing a non-existent approval policy."""
    # Arrange
    policy_id = uuid4()
    account_id = str(uuid4())

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_db_session.delete = MagicMock()
    mock_db_session.commit = MagicMock()

    # Act
    result = crud_approval_policy.remove(
        mock_db_session, id=policy_id, account_id=account_id
    )

    # Assert
    assert result is None
    mock_db_session.delete.assert_not_called()
    mock_db_session.commit.assert_not_called()
