import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session

from spacemodels.crud.issue_duplicate import CRUDIssueDuplicate
from spacemodels.models.issue_duplicate import IssueDuplicate


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_issue_duplicate():
    """Fixture for a CRUDIssueDuplicate instance."""
    return CRUDIssueDuplicate(IssueDuplicate)


def test_create(crud_issue_duplicate, mock_db_session):
    """Test creating an issue duplicate."""
    # Arrange
    issue1_id = str(uuid4())
    issue2_id = str(uuid4())
    obj_in = {"issue1_id": issue1_id, "issue2_id": issue2_id}

    # Act
    crud_issue_duplicate.create(mock_db_session, obj_in=obj_in)

    # Assert
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


def test_update_resolution(crud_issue_duplicate, mock_db_session):
    """Test updating the resolution of an issue duplicate."""
    # Arrange
    mock_duplicate = IssueDuplicate(id=str(uuid4()))
    resolution = "MERGED"
    resolution_reason = "Issues are the same."

    # Act
    result = crud_issue_duplicate.update_resolution(
        mock_db_session,
        db_obj=mock_duplicate,
        resolution=resolution,
        resolution_reason=resolution_reason,
    )

    # Assert
    assert result.resolution == resolution
    assert result.resolution_reason == resolution_reason
    assert isinstance(result.resolution_at, datetime)
    mock_db_session.add.assert_called_once_with(mock_duplicate)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_duplicate)


def test_get_by_issue_ids(crud_issue_duplicate, mock_db_session):
    """Test retrieving an issue duplicate by issue IDs."""
    # Arrange
    issue1_id = str(uuid4())
    issue2_id = str(uuid4())
    mock_duplicate = IssueDuplicate(id=str(uuid4()))

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_duplicate

    # Act
    result = crud_issue_duplicate.get_by_issue_ids(
        mock_db_session, issue1_id=issue1_id, issue2_id=issue2_id
    )

    # Assert
    assert result == mock_duplicate


def test_get_all_for_issue(crud_issue_duplicate, mock_db_session):
    """Test retrieving all duplicates for an issue."""
    # Arrange
    issue_id = str(uuid4())
    mock_duplicates = [IssueDuplicate(id=str(uuid4())) for _ in range(3)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_duplicates

    # Act
    result = crud_issue_duplicate.get_all_for_issue(mock_db_session, issue_id=issue_id)

    # Assert
    assert len(result) == 3


def test_remove_by_issue_id(crud_issue_duplicate, mock_db_session):
    """Test removing all duplicates for an issue."""
    # Arrange
    issue_id = str(uuid4())

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query

    # Act
    crud_issue_duplicate.remove_by_issue_id(mock_db_session, issue_id=issue_id)

    # Assert
    mock_query.delete.assert_called_once()
    mock_db_session.commit.assert_called_once()


def test_get_by_issue_ids_with_account_id(crud_issue_duplicate, mock_db_session):
    """Test retrieving an issue duplicate by issue IDs with account filter."""
    # Arrange
    issue1_id = str(uuid4())
    issue2_id = str(uuid4())
    account_id = str(uuid4())
    mock_duplicate = IssueDuplicate(id=str(uuid4()))

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.first.return_value = mock_duplicate

    # Act
    result = crud_issue_duplicate.get_by_issue_ids(
        mock_db_session, issue1_id=issue1_id, issue2_id=issue2_id, account_id=account_id
    )

    # Assert
    assert result == mock_duplicate
    assert mock_query.join.called


def test_get_all_for_issue_with_account_id(crud_issue_duplicate, mock_db_session):
    """Test retrieving all duplicates for an issue with account filter."""
    # Arrange
    issue_id = str(uuid4())
    account_id = str(uuid4())
    mock_duplicates = [IssueDuplicate(id=str(uuid4())) for _ in range(2)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.all.return_value = mock_duplicates

    # Act
    result = crud_issue_duplicate.get_all_for_issue(
        mock_db_session, issue_id=issue_id, account_id=account_id
    )

    # Assert
    assert len(result) == 2
    assert mock_query.join.called
