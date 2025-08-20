import pytest
import json
from unittest.mock import AsyncMock, MagicMock
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


@pytest.mark.asyncio
async def test_detect_issue_dependencies_success(
    mock_issues: list[MagicMock], mocker: MockerFixture
):
    """Tests successful dependency detection between a list of issues."""
    # Arrange
    issue_ids = [issue.id for issue in mock_issues]
    request = DependencyRequest(issue_ids=issue_ids)
    mock_user = MagicMock(spec=Account)
    mock_user.id = "user-123"

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

    # Mock Billing Service
    mock_billing_service_class = mocker.patch(
        "spacebridge.api.endpoints.issue_dependencies.BillingService"
    )
    mock_billing_instance = MagicMock()
    mock_billing_service_class.return_value = mock_billing_instance

    # Mock OpenAI client
    mock_openai_client = mocker.patch(
        "spacebridge.api.endpoints.issue_dependencies.openai.OpenAI"
    )
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"dependencies": []})))
    ]
    mock_openai_client.return_value.chat.completions.create = AsyncMock(
        return_value=mock_completion
    )

    # Act
    result = await detect_issue_dependencies(
        request=request, db=MagicMock(), current_user=mock_user
    )

    # Assert
    assert isinstance(result, DependencyResponse)
    assert result.dependencies == []

    # Verify mocks were called
    assert mock_crud_issue.get.call_count == len(issue_ids)
    mock_crud_ai_model.get_default_active_model.assert_called_once_with(
        mocker.ANY, account_id=mock_user.id
    )
    mock_openai_client.return_value.chat.completions.create.assert_awaited_once()
    mock_billing_instance.record_usage.assert_called_once_with(
        account_id=mock_user.id, metric="ai_calls", quantity=1
    )
