import pytest
import json
from unittest.mock import MagicMock
from pytest_mock import MockerFixture

from spacebridge.api.endpoints.issue_dependencies import (
    detect_issue_dependencies,
    DependencyRequest,
    DependencyResponse,
)
from spacemodels.models import Issue, AIModel, Project, Account


@pytest.fixture
def mock_project() -> MagicMock:
    """Provides a mock Project object."""
    project = MagicMock(spec=Project)
    project.name = "TEST-PROJ"
    return project


@pytest.fixture
def mock_issues(mock_project: MagicMock) -> list[MagicMock]:
    """Provides a list of mock Issue objects for testing."""
    issues = []
    for i, issue_id in enumerate(
        [
            "0000890a-99a1-4d47-ba8b-21b8292bbdc3",
            "00e6a411-f125-4079-ae01-79b5c35048b8",
            "00e8e485-d7e0-4d3d-b55c-be754213ab3b",
        ]
    ):
        issue = MagicMock(spec=Issue)
        issue.id = issue_id
        issue.title = f"Test Issue {i + 1}"
        issue.description = f"Description for issue {i + 1}."
        issue.project = mock_project
        issues.append(issue)
    return issues


def test_detect_issue_dependencies_success(
    mock_issues: list[MagicMock], mocker: MockerFixture
):
    """Tests successful dependency detection between a list of issues."""
    # Arrange
    issue_ids = [issue.id for issue in mock_issues]
    request = DependencyRequest(issue_ids=issue_ids)
    mock_user = MagicMock(spec=Account)
    mock_user.id = "user-123"
    mock_user.account_id = "account-123"

    # Mock CRUD operations
    mock_crud_issue = mocker.patch(
        "spacebridge.api.endpoints.issue_dependencies.crud_issue"
    )
    mock_crud_issue.get.side_effect = mock_issues

    mock_crud_ai_model = mocker.patch(
        "spacebridge.api.endpoints.issue_dependencies.crud_ai_model"
    )
    mock_ai_model = MagicMock(spec=AIModel)
    mock_ai_model.model_identifier = "gpt-4"
    mock_ai_model.api_key = "fake-key"
    mock_crud_ai_model.get_default_active_model.return_value = mock_ai_model

    # Mock IssueSet to simulate a cache miss
    mock_crud_issue_set = mocker.patch(
        "spacebridge.api.endpoints.issue_dependencies.crud_issue_set"
    )
    mock_crud_issue_set.get_supersets_by_issues.return_value = []

    # Mock OpenAI client
    mock_openai_client = mocker.patch(
        "spacebridge.api.endpoints.issue_dependencies.openai.OpenAI"
    )
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"dependencies": []})))
    ]
    mock_openai_client.return_value.chat.completions.create.return_value = (
        mock_completion
    )

    mock_settings = MagicMock()
    mock_settings.PROMPTS_FILE = "/path/to/prompts.yml"
    mocker.patch(
        "spacebridge.api.endpoints.issue_dependencies.load_dependencies_prompts_config",
        return_value={"dependency_detection_v1": {"system": "Test prompt"}},
    )

    # Act
    result = detect_issue_dependencies(
        request=request, db=MagicMock(), current_user=mock_user, settings=mock_settings
    )

    # Assert
    assert isinstance(result, DependencyResponse)
    assert result.dependencies == []

    # Verify mocks were called
    assert mock_crud_issue.get.call_count == len(issue_ids)
    mock_crud_ai_model.get_default_active_model.assert_called_once_with(
        mocker.ANY, account_id=mock_user.account_id
    )
    mock_openai_client.return_value.chat.completions.create.assert_called_once()
    mock_crud_issue_set.create_and_remove_subsets.assert_called_once()
