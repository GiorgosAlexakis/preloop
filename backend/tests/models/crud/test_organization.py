import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from preloop.models.crud.organization import CRUDOrganization
from preloop.models.models.organization import Organization


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_organization():
    """Fixture for a CRUDOrganization instance."""
    return CRUDOrganization(Organization)


def test_get_by_identifier(crud_organization, mock_db_session):
    """Test retrieving an organization by identifier."""
    # Arrange
    identifier = "test-org"
    account_id = str(uuid4())
    mock_organization = Organization(id=str(uuid4()), identifier=identifier)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.first.return_value = mock_organization

    # Act
    result = crud_organization.get_by_identifier(
        mock_db_session, identifier=identifier, account_id=account_id
    )

    # Assert
    assert result.identifier == identifier


def test_get_by_name(crud_organization, mock_db_session):
    """Test retrieving an organization by name."""
    # Arrange
    name = "Test Organization"
    tracker_id = str(uuid4())
    mock_organization = Organization(id=str(uuid4()), name=name)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_organization

    # Act
    result = crud_organization.get_by_name(
        mock_db_session, name=name, tracker_id=tracker_id
    )

    # Assert
    assert result.name == name


def test_count(crud_organization, mock_db_session):
    """Test counting organizations."""
    # Arrange
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.count.return_value = 5

    # Act
    result = crud_organization.count(mock_db_session)

    # Assert
    assert result == 5


def test_get_for_tracker(crud_organization, mock_db_session):
    """Test retrieving organizations for a tracker."""
    # Arrange
    tracker_id = str(uuid4())
    mock_organizations = [Organization(id=str(uuid4())) for _ in range(2)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_organizations

    # Act
    result = crud_organization.get_for_tracker(mock_db_session, tracker_id=tracker_id)

    # Assert
    assert len(result) == 2


def test_get_active(crud_organization, mock_db_session):
    """Test retrieving active organizations."""
    # Arrange
    mock_organizations = [Organization(id=str(uuid4()), is_active=True)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_organizations

    # Act
    result = crud_organization.get_active(mock_db_session)

    # Assert
    assert len(result) == 1
    assert result[0].is_active


def test_get_for_account(crud_organization, mock_db_session):
    """Test retrieving organizations for an account."""
    # Arrange
    account_id = str(uuid4())
    mock_organizations = [Organization(id=str(uuid4())) for _ in range(3)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_organizations

    # Act
    result = crud_organization.get_for_account(mock_db_session, account_id=account_id)

    # Assert
    assert len(result) == 3


def test_deactivate(crud_organization, mock_db_session):
    """Test deactivating an organization."""
    # Arrange
    org_id = str(uuid4())
    mock_organization = Organization(id=org_id, is_active=True)

    crud_organization.get = MagicMock(return_value=mock_organization)

    # Act
    result = crud_organization.deactivate(mock_db_session, id=org_id)

    # Assert
    assert not result.is_active
    mock_db_session.add.assert_called_once_with(mock_organization)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_organization)


def test_get_by_name_with_account_id(crud_organization, mock_db_session):
    """Test retrieving an organization by name with account filter."""
    # Arrange
    name = "Test Organization"
    tracker_id = str(uuid4())
    account_id = str(uuid4())
    mock_organization = Organization(id=str(uuid4()), name=name)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.first.return_value = mock_organization

    # Act
    result = crud_organization.get_by_name(
        mock_db_session, name=name, tracker_id=tracker_id, account_id=account_id
    )

    # Assert
    assert result.name == name
    assert mock_query.join.called


def test_count_with_account_id(crud_organization, mock_db_session):
    """Test counting organizations with account filter."""
    # Arrange
    account_id = str(uuid4())

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 3

    # Act
    result = crud_organization.count(mock_db_session, account_id=account_id)

    # Assert
    assert result == 3
    assert mock_query.join.called


def test_count_with_additional_filters(crud_organization, mock_db_session):
    """Test counting organizations with additional attribute filters."""
    # Arrange
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 2

    # Act
    result = crud_organization.count(mock_db_session, is_active=True)

    # Assert
    assert result == 2


def test_get_for_tracker_with_account_id(crud_organization, mock_db_session):
    """Test retrieving organizations for a tracker with account filter."""
    # Arrange
    tracker_id = str(uuid4())
    account_id = str(uuid4())
    mock_organizations = [Organization(id=str(uuid4())) for _ in range(2)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_organizations

    # Act
    result = crud_organization.get_for_tracker(
        mock_db_session, tracker_id=tracker_id, account_id=account_id
    )

    # Assert
    assert len(result) == 2
    assert mock_query.join.called


def test_get_by_identifier_and_tracker(crud_organization, mock_db_session):
    """Test retrieving organization by identifier and tracker ID."""
    # Arrange
    identifier = "org-123"
    tracker_id = str(uuid4())
    mock_organization = Organization(id=str(uuid4()), identifier=identifier)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_organization

    # Act
    result = crud_organization.get_by_identifier_and_tracker(
        mock_db_session, identifier=identifier, tracker_id=tracker_id
    )

    # Assert
    assert result.identifier == identifier


def test_get_by_identifier_and_tracker_not_found(crud_organization, mock_db_session):
    """Test retrieving non-existent organization by identifier and tracker."""
    # Arrange
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    # Act
    result = crud_organization.get_by_identifier_and_tracker(
        mock_db_session, identifier="non-existent", tracker_id=str(uuid4())
    )

    # Assert
    assert result is None


def test_get_with_tracker(crud_organization, mock_db_session):
    """Test retrieving organization by ID with tracker eagerly loaded."""
    # Arrange
    org_id = str(uuid4())
    mock_organization = Organization(id=org_id)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_organization

    # Act
    result = crud_organization.get_with_tracker(mock_db_session, id=org_id)

    # Assert
    assert result is not None
    assert result.id == org_id
    mock_query.options.assert_called_once()


def test_get_with_tracker_with_account_filter(crud_organization, mock_db_session):
    """Test retrieving organization with tracker and account filter."""
    # Arrange
    org_id = str(uuid4())
    account_id = str(uuid4())
    mock_organization = Organization(id=org_id)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.first.return_value = mock_organization

    # Act
    result = crud_organization.get_with_tracker(
        mock_db_session, id=org_id, account_id=account_id
    )

    # Assert
    assert result is not None
    mock_query.join.assert_called()


def test_get_with_tracker_not_found(crud_organization, mock_db_session):
    """Test retrieving non-existent organization with tracker."""
    # Arrange
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    # Act
    result = crud_organization.get_with_tracker(mock_db_session, id=str(uuid4()))

    # Assert
    assert result is None


def test_get_for_trackers(crud_organization, mock_db_session):
    """Test retrieving organizations for multiple trackers with pagination."""
    # Arrange
    tracker_ids = [str(uuid4()), str(uuid4())]
    mock_organizations = [Organization(id=str(uuid4())) for _ in range(5)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 5
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_organizations

    # Act
    organizations, total = crud_organization.get_for_trackers(
        mock_db_session, tracker_ids=tracker_ids, skip=0, limit=100
    )

    # Assert
    assert len(organizations) == 5
    assert total == 5


def test_get_for_trackers_with_pagination(crud_organization, mock_db_session):
    """Test retrieving organizations for multiple trackers with specific pagination."""
    # Arrange
    tracker_ids = [str(uuid4())]
    mock_organizations = [Organization(id=str(uuid4())) for _ in range(2)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 10  # Total is higher than returned
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_organizations

    # Act
    organizations, total = crud_organization.get_for_trackers(
        mock_db_session, tracker_ids=tracker_ids, skip=5, limit=2
    )

    # Assert
    assert len(organizations) == 2
    assert total == 10
    mock_query.offset.assert_called()
    mock_query.limit.assert_called()


def test_get_for_trackers_empty(crud_organization, mock_db_session):
    """Test retrieving organizations for trackers when none exist."""
    # Arrange
    tracker_ids = [str(uuid4())]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 0
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []

    # Act
    organizations, total = crud_organization.get_for_trackers(
        mock_db_session, tracker_ids=tracker_ids
    )

    # Assert
    assert organizations == []
    assert total == 0


def test_get_for_trackers_with_account_filter(crud_organization, mock_db_session):
    """Test retrieving organizations for trackers with account filter."""
    # Arrange
    tracker_ids = [str(uuid4())]
    account_id = str(uuid4())
    mock_organizations = [Organization(id=str(uuid4()))]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.count.return_value = 1
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_organizations

    # Act
    organizations, total = crud_organization.get_for_trackers(
        mock_db_session, tracker_ids=tracker_ids, account_id=account_id
    )

    # Assert
    assert len(organizations) == 1
    assert total == 1
    mock_query.join.assert_called()


def test_deactivate_not_found(crud_organization, mock_db_session):
    """Test deactivating a non-existent organization."""
    # Arrange
    org_id = str(uuid4())
    crud_organization.get = MagicMock(return_value=None)

    # Act
    result = crud_organization.deactivate(mock_db_session, id=org_id)

    # Assert
    assert result is None
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


def test_get_active_with_account_id(crud_organization, mock_db_session):
    """Test retrieving active organizations with account filter."""
    # Arrange
    account_id = str(uuid4())
    mock_organizations = [Organization(id=str(uuid4()), is_active=True)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_organizations

    # Act
    result = crud_organization.get_active(mock_db_session, account_id=account_id)

    # Assert
    assert len(result) == 1
    mock_query.join.assert_called()


def test_get_by_identifier_without_account_id(crud_organization, mock_db_session):
    """Test retrieving organization by identifier without account filter."""
    # Arrange
    identifier = "test-org"
    mock_organization = Organization(id=str(uuid4()), identifier=identifier)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_organization

    # Act
    result = crud_organization.get_by_identifier(mock_db_session, identifier=identifier)

    # Assert
    assert result.identifier == identifier
    mock_query.join.assert_not_called()


def test_get_by_name_without_tracker_id(crud_organization, mock_db_session):
    """Test retrieving organization by name without tracker filter."""
    # Arrange
    name = "Test Organization"
    mock_organization = Organization(id=str(uuid4()), name=name)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_organization

    # Act
    result = crud_organization.get_by_name(mock_db_session, name=name)

    # Assert
    assert result.name == name
