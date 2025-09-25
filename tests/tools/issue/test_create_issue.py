import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from spacebridge.tools.issue.create_issue import create_issue
from spacebridge.schemas import tracker_models
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
@patch("spacebridge.tools.issue.create_issue.get_db")
@patch("spacebridge.tools.issue.create_issue.CRUDOrganization")
@patch("spacebridge.tools.issue.create_issue.CRUDProject")
@patch("spacebridge.tools.issue.create_issue.create_tracker_client")
async def test_create_issue_happy_path(
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
    """Test the successful creation of an issue."""
    # Arrange
    mock_get_db.return_value = iter([mock_db_session])
    mock_crud_organization_class.return_value = mock_crud_organization
    mock_crud_project_class.return_value = mock_crud_project

    mock_crud_organization.get_by_identifier.return_value = mock_organization
    mock_crud_project.get_by_identifier.return_value = mock_project

    mock_tracker_client = AsyncMock()
    mock_tracker_client.create_issue.return_value = tracker_models.Issue(
        id="123",
        key="TP-123",
        title="Test Issue",
        description="Test Description",
        status=tracker_models.IssueStatus(id="1", name="To Do", category="todo"),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        url="http://example.com/issue/123",
        api_url="http://example.com/api/issue/123",
        tracker_type="github",
        project_key="test-proj",
    )
    mock_create_tracker_client.return_value = mock_tracker_client

    # Act
    result = await create_issue(
        organization="test-org",
        project="test-proj",
        title="Test Issue",
        description="Test Description",
    )

    # Assert
    assert result["issue"]["title"] == "Test Issue"
    assert result["tracker"] == "github"
    mock_tracker_client.create_issue.assert_called_once()


@pytest.mark.asyncio
@patch("spacebridge.tools.issue.create_issue.get_db")
@patch("spacebridge.tools.issue.create_issue.CRUDOrganization")
async def test_create_issue_organization_not_found(
    mock_crud_organization_class,
    mock_get_db,
    mock_db_session,
    mock_crud_organization,
):
    """Test that an error is returned when the organization is not found."""
    # Arrange
    mock_get_db.return_value = iter([mock_db_session])
    mock_crud_organization_class.return_value = mock_crud_organization
    mock_crud_organization.get_by_identifier.return_value = None

    # Act
    result = await create_issue(
        organization="non-existent-org",
        project="test-proj",
        title="Test Issue",
        description="Test Description",
    )

    # Assert
    assert result["error"] == "not_found"
    assert "Organization 'non-existent-org' not found" in result["message"]


@pytest.mark.asyncio
@patch("spacebridge.tools.issue.create_issue.get_db")
@patch("spacebridge.tools.issue.create_issue.CRUDOrganization")
@patch("spacebridge.tools.issue.create_issue.CRUDProject")
async def test_create_issue_project_not_found(
    mock_crud_project_class,
    mock_crud_organization_class,
    mock_get_db,
    mock_db_session,
    mock_crud_organization,
    mock_crud_project,
    mock_organization,
):
    """Test that an error is returned when the project is not found."""
    # Arrange
    mock_get_db.return_value = iter([mock_db_session])
    mock_crud_organization_class.return_value = mock_crud_organization
    mock_crud_project_class.return_value = mock_crud_project

    mock_crud_organization.get_by_identifier.return_value = mock_organization
    mock_crud_project.get_by_identifier.return_value = None

    # Act
    result = await create_issue(
        organization="test-org",
        project="non-existent-proj",
        title="Test Issue",
        description="Test Description",
    )

    # Assert
    assert result["error"] == "not_found"
    assert "Project 'non-existent-proj' not found" in result["message"]


@pytest.mark.asyncio
@patch("spacebridge.tools.issue.create_issue.get_db")
@patch("spacebridge.tools.issue.create_issue.CRUDOrganization")
@patch("spacebridge.tools.issue.create_issue.CRUDProject")
async def test_create_issue_no_trackers_configured(
    mock_crud_project_class,
    mock_crud_organization_class,
    mock_get_db,
    mock_db_session,
    mock_crud_organization,
    mock_crud_project,
    mock_organization,
    mock_project,
):
    """Test that an error is returned when the project has no trackers."""
    # Arrange
    mock_get_db.return_value = iter([mock_db_session])
    mock_crud_organization_class.return_value = mock_crud_organization
    mock_crud_project_class.return_value = mock_crud_project

    mock_crud_organization.get_by_identifier.return_value = mock_organization
    mock_project.tracker_settings = {}
    mock_crud_project.get_by_identifier.return_value = mock_project

    # Act
    result = await create_issue(
        organization="test-org",
        project="test-proj",
        title="Test Issue",
        description="Test Description",
    )

    # Assert
    assert result["error"] == "no_trackers"
    assert "Project 'test-proj' has no configured trackers" in result["message"]


@pytest.mark.asyncio
@patch("spacebridge.tools.issue.create_issue.get_db")
@patch("spacebridge.tools.issue.create_issue.CRUDOrganization")
@patch("spacebridge.tools.issue.create_issue.CRUDProject")
async def test_create_issue_tracker_not_found(
    mock_crud_project_class,
    mock_crud_organization_class,
    mock_get_db,
    mock_db_session,
    mock_crud_organization,
    mock_crud_project,
    mock_organization,
    mock_project,
):
    """Test that an error is returned when the specified tracker is not found."""
    # Arrange
    mock_get_db.return_value = iter([mock_db_session])
    mock_crud_organization_class.return_value = mock_crud_organization
    mock_crud_project_class.return_value = mock_crud_project

    mock_crud_organization.get_by_identifier.return_value = mock_organization
    mock_crud_project.get_by_identifier.return_value = mock_project

    # Act
    result = await create_issue(
        organization="test-org",
        project="test-proj",
        title="Test Issue",
        description="Test Description",
        tracker="non-existent-tracker",
    )

    # Assert
    assert result["error"] == "tracker_not_found"
    assert "Tracker 'non-existent-tracker' is not configured" in result["message"]
