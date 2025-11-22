import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session

from spacemodels.crud.issue import CRUDIssue
from spacemodels.models.issue import Issue


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_issue():
    """Fixture for a CRUDIssue instance."""
    return CRUDIssue(Issue)


def test_create_with_external(crud_issue, mock_db_session):
    """Test creating an issue with external sync."""
    # Arrange
    issue_in = {"title": "Test Issue", "project_id": str(uuid4())}
    mock_issue = Issue(**issue_in)

    with patch.object(crud_issue, "create", return_value=mock_issue) as mock_create:
        # Act
        result = crud_issue.create_with_external(mock_db_session, obj_in=issue_in)

        # Assert
        mock_create.assert_called_once_with(mock_db_session, obj_in=issue_in)
        assert result.title == issue_in["title"]


def test_get_by_title(crud_issue, mock_db_session):
    """Test retrieving an issue by title."""
    # Arrange
    title = "Test Issue"
    project_id = str(uuid4())
    mock_issue = Issue(id=str(uuid4()), title=title)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_issue

    # Act
    result = crud_issue.get_by_title(
        mock_db_session, title=title, project_id=project_id
    )

    # Assert
    assert result.title == title


def test_get_by_key(crud_issue, mock_db_session):
    """Test retrieving an issue by key."""
    # Arrange
    issue_key = "TEST-123"
    project_id = str(uuid4())
    account_id = str(uuid4())
    mock_issue = Issue(id=str(uuid4()), key=issue_key)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.first.return_value = mock_issue

    # Act
    result = crud_issue.get_by_key(
        mock_db_session, key=issue_key, project_id=project_id, account_id=account_id
    )

    # Assert
    assert result == mock_issue
    assert result.key == issue_key
    mock_db_session.query.assert_called_once_with(Issue)


def test_get_by_external_id(crud_issue, mock_db_session):
    """Test retrieving an issue by external ID."""
    # Arrange
    external_id = "JIRA-456"
    project_id = str(uuid4())
    account_id = str(uuid4())
    mock_issue = Issue(id=str(uuid4()), external_id=external_id)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.first.return_value = mock_issue

    # Act
    result = crud_issue.get_by_external_id(
        mock_db_session,
        project_id=project_id,
        external_id=external_id,
        account_id=account_id,
    )

    # Assert
    assert result == mock_issue
    assert result.external_id == external_id
    mock_db_session.query.assert_called_once_with(Issue)


def test_get_for_project(crud_issue, mock_db_session):
    """Test retrieving issues for a project."""
    # Arrange
    project_id = str(uuid4())
    mock_issues = [Issue(id=str(uuid4())) for _ in range(3)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_issues

    # Act
    result = crud_issue.get_for_project(mock_db_session, project_id=project_id)

    # Assert
    assert len(result) == 3


def test_get_issue_counts_per_project(crud_issue, mock_db_session):
    """Test getting issue counts per project."""
    # Arrange
    project_id = str(uuid4())
    mock_db_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
        (project_id, 10)
    ]

    # Act
    result = crud_issue.get_issue_counts_per_project(
        mock_db_session, project_ids=[project_id]
    )

    # Assert
    assert result[project_id]["total"] == 10


def test_get_issue_count(crud_issue, mock_db_session):
    """Test getting the total number of issues for an account."""
    # Arrange
    account_id = str(uuid4())
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.scalar.return_value = 5

    # Act
    result = crud_issue.get_issue_count(mock_db_session, account_id=account_id)

    # Assert
    assert result == 5


def test_update_status(crud_issue, mock_db_session):
    """Test updating an issue's status."""
    # Arrange
    issue_id = str(uuid4())
    new_status = "In Progress"
    mock_issue = Issue(id=issue_id, status="Open")

    crud_issue.get = MagicMock(return_value=mock_issue)

    # Act
    result = crud_issue.update_status(mock_db_session, id=issue_id, status=new_status)

    # Assert
    assert result.status == new_status
    mock_db_session.add.assert_called_once_with(mock_issue)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_issue)


def test_update_last_synced(crud_issue, mock_db_session):
    """Test updating an issue's last_synced timestamp."""
    # Arrange
    issue_id = str(uuid4())
    mock_issue = Issue(id=issue_id, last_synced=None)

    crud_issue.get = MagicMock(return_value=mock_issue)

    # Act
    result = crud_issue.update_last_synced(mock_db_session, id=issue_id)

    # Assert
    assert result.last_synced is not None
    assert isinstance(result.last_synced, datetime)
    mock_db_session.add.assert_called_once_with(mock_issue)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_issue)
