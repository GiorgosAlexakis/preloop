import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from spacebridge.tools.project.test_connection import verify_connection
from spacebridge.schemas.tracker_models import TrackerConnection
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_crud_organization():
    """Fixture for a mock CRUDOrganization."""
    return MagicMock()


@pytest.fixture
def mock_crud_project():
    """Fixture for a mock CRUDProject."""
    return MagicMock()


@pytest.fixture
def mock_tracker_factory():
    """Fixture for a mock TrackerFactory."""
    return MagicMock()


@pytest.fixture
def mock_organization():
    """Fixture for a mock Organization."""
    org = MagicMock(spec=Organization)
    org.id = 1
    org.is_active = True
    org.name = "Test Org"
    org.identifier = "test-org"
    return org


@pytest.fixture
def mock_project():
    """Fixture for a mock Project."""
    proj = MagicMock(spec=Project)
    proj.id = 101
    proj.is_active = True
    proj.name = "Test Project"
    proj.identifier = "test-proj"
    proj.tracker_settings = {"github": {"api_key": "test-key"}}
    proj.tracker_id = "github"
    return proj


@pytest.mark.asyncio
@patch("spacebridge.tools.project.test_connection.get_db")
@patch("spacebridge.tools.project.test_connection.CRUDOrganization")
@patch("spacebridge.tools.project.test_connection.CRUDProject")
@patch("spacebridge.tools.project.test_connection.create_tracker_client")
async def test_connection_happy_path(
    mock_create_tracker_client,
    mock_crud_project_class,
    mock_crud_organization_class,
    mock_get_db,
    mock_db_session,
    mock_crud_organization,
    mock_crud_project,
    mock_organization,
    mock_project,
):
    """Test the successful connection to a tracker."""
    # Arrange
    mock_get_db.return_value = iter([mock_db_session])
    mock_crud_organization_class.return_value = mock_crud_organization
    mock_crud_project_class.return_value = mock_crud_project

    mock_crud_organization.get_by_identifier.return_value = mock_organization
    mock_crud_project.get_by_identifier.return_value = mock_project

    mock_tracker_client = AsyncMock()
    mock_tracker_client.test_connection.return_value = TrackerConnection(
        connected=True,
        message="Connection successful",
        rate_limit=None,
        server_info=None,
    )
    mock_create_tracker_client.return_value = mock_tracker_client

    # Act
    result = await verify_connection(
        organization="test-org",
        project="test-proj",
    )

    # Assert
    assert result["connection_results"]["github"]["connected"] is True
    mock_tracker_client.test_connection.assert_called_once()
