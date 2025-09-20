import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from spacebridge.tools.issue.search_issues import search_issues, IssueInfo
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
    return proj


@pytest.mark.asyncio
@patch("spacebridge.tools.issue.search_issues.get_db")
@patch("spacebridge.tools.issue.search_issues.CRUDOrganization")
@patch("spacebridge.tools.issue.search_issues.CRUDProject")
@patch("spacebridge.tools.issue.search_issues.TrackerFactory")
async def test_search_issues_happy_path(
    mock_tracker_factory_class,
    mock_crud_project_class,
    mock_crud_organization_class,
    mock_get_db,
    mock_db_session,
    mock_crud_organization,
    mock_crud_project,
    mock_organization,
    mock_project,
):
    """Test the successful search of an issue."""
    # Arrange
    mock_get_db.return_value = iter([mock_db_session])
    mock_crud_organization_class.return_value = mock_crud_organization
    mock_crud_project_class.return_value = mock_crud_project

    mock_crud_organization.get_by_identifier.return_value = mock_organization
    mock_crud_project.get_by_slug_or_identifier.return_value = [mock_project]
    mock_crud_project.get_by_name.return_value = []

    mock_tracker_client = AsyncMock()
    mock_tracker_client.search_issues.return_value = (
        [
            IssueInfo(
                id="123",
                title="Test Issue",
                description="Test Description",
                source="github",
            )
        ],
        1,
    )
    mock_tracker_factory_class.create_client = AsyncMock(
        return_value=mock_tracker_client
    )

    # Act
    result = await search_issues(
        organization="test-org",
        project="test-proj",
        query="Test",
    )

    # Assert
    assert result["total_results"] == 1
    assert result["combined_results"][0]["title"] == "Test Issue"
    assert "github" in result["results_by_tracker"]
    mock_tracker_client.search_issues.assert_called_once()


@pytest.mark.asyncio
@patch("spacebridge.tools.issue.search_issues.get_db")
@patch("spacebridge.tools.issue.search_issues.CRUDOrganization")
async def test_search_issues_organization_not_found(
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
    result = await search_issues(
        organization="non-existent-org",
        project="test-proj",
        query="Test",
    )

    # Assert
    assert result["error"] == "not_found"
    assert "Organization 'non-existent-org' not found" in result["message"]


@pytest.mark.asyncio
@patch("spacebridge.tools.issue.search_issues.get_db")
@patch("spacebridge.tools.issue.search_issues.CRUDOrganization")
@patch("spacebridge.tools.issue.search_issues.CRUDProject")
async def test_search_issues_project_not_found(
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
    mock_crud_project.get_by_slug_or_identifier.return_value = []
    mock_crud_project.get_by_name.return_value = []

    # Act
    result = await search_issues(
        organization="test-org",
        project="non-existent-proj",
        query="Test",
    )

    # Assert
    assert result["error"] == "not_found"
    assert "Project 'non-existent-proj' not found" in result["message"]


@pytest.mark.asyncio
@patch("spacebridge.tools.issue.search_issues.get_db")
@patch("spacebridge.tools.issue.search_issues.CRUDOrganization")
@patch("spacebridge.tools.issue.search_issues.CRUDProject")
async def test_search_issues_no_trackers_configured(
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
    mock_crud_project.get_by_slug_or_identifier.return_value = [mock_project]
    mock_crud_project.get_by_name.return_value = []

    # Act
    result = await search_issues(
        organization="test-org",
        project="test-proj",
        query="Test",
    )

    # Assert
    assert result["error"] == "no_trackers"
    assert "Project 'test-proj' has no configured trackers" in result["message"]
