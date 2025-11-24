import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Tuple
from uuid import uuid4
from fastapi import HTTPException
from pytest_mock import MockerFixture
from unittest.mock import patch

from preloop_ai.api.endpoints import issue_duplicates

from preloop_ai.api.endpoints.issue_duplicates import (
    execute_issue_duplicate_resolution,
)
from preloop_ai.schemas import (
    IssueDuplicateResolutionRequest,
    IssueUpdate,
)
from preloop_models.models.issue import Issue


@pytest.fixture
def mock_issues(mocker: MockerFixture) -> Tuple[MagicMock, MagicMock]:
    """Provides mock Issue objects for testing."""
    issue_a = MagicMock(spec=Issue)
    issue_a.id = uuid4()  # Changed from "db_id_a" to proper UUID
    issue_a.key = "PROJ-1"
    issue_a.title = "Original Title A"
    issue_a.description = "Original Description A"

    issue_b = MagicMock(spec=Issue)
    issue_b.id = uuid4()  # Changed from "db_id_b" to proper UUID
    issue_b.key = "PROJ-2"
    issue_b.title = "Original Title B"
    issue_b.description = "Original Description B"
    return issue_a, issue_b


@pytest.mark.asyncio
async def test_execute_resolution_close_a(mock_issues, mocker: MockerFixture):
    """Tests that a 'close_a' resolution correctly closes issue A."""
    # Arrange
    issue_a, issue_b = mock_issues
    resolution_request = IssueDuplicateResolutionRequest(
        issue1_id=issue_a.id, issue2_id=issue_b.id, resolution="close_a"
    )

    mock_crud_issue = mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.crud_issue",
        new_callable=MagicMock,
    )
    mock_update_issue = mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.update_issue",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.crud_issue_duplicate",
        new_callable=MagicMock,
    )

    mock_crud_issue.get.side_effect = [issue_a, issue_b]

    # Act
    await execute_issue_duplicate_resolution(
        resolution=resolution_request, db=MagicMock(), current_user=MagicMock()
    )

    # Assert
    assert mock_update_issue.call_count == 2
    mock_update_issue.assert_has_calls(
        [
            mocker.call(
                issue_id=issue_a.id,
                issue_update=IssueUpdate(
                    status="closed",
                    comment=f"Closed as duplicate of issue {issue_b.key}.",
                ),
                db=mocker.ANY,
                current_user=mocker.ANY,
            ),
            mocker.call(
                issue_id=issue_b.id,
                issue_update=IssueUpdate(
                    comment=f"Issue {issue_a.key} was closed as a duplicate of this issue."
                ),
                db=mocker.ANY,
                current_user=mocker.ANY,
            ),
        ],
        any_order=False,
    )


@pytest.mark.asyncio
async def test_execute_resolution_merge_b_to_a(mock_issues, mocker: MockerFixture):
    """Tests that a 'merge_b_to_a' resolution correctly merges B into A."""
    # Arrange
    issue_a, issue_b = mock_issues
    resolution_request = IssueDuplicateResolutionRequest(
        issue1_id=issue_a.id,
        issue2_id=issue_b.id,
        resolution="merge_b_to_a",
        resulting_issue_1_title="New Merged Title",
        resulting_issue_1_description="New Merged Description",
    )

    mock_crud_issue = mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.crud_issue",
        new_callable=MagicMock,
    )
    mock_update_issue = mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.update_issue",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.crud_issue_duplicate",
        new_callable=MagicMock,
    )

    mock_crud_issue.get.side_effect = [issue_a, issue_b]

    # Act
    await execute_issue_duplicate_resolution(
        resolution=resolution_request, db=MagicMock(), current_user=MagicMock()
    )

    # Assert
    assert mock_update_issue.call_count == 2
    mock_update_issue.assert_any_call(
        issue_id=issue_a.id,
        issue_update=IssueUpdate(
            title="New Merged Title",
            description="New Merged Description",
            comment=f"Merged content from issue {issue_b.key}.",
        ),
        db=mocker.ANY,
        current_user=mocker.ANY,
    )
    mock_update_issue.assert_any_call(
        issue_id=issue_b.id,
        issue_update=IssueUpdate(
            status="closed",
            comment=f"Merged into and closed as duplicate of issue {issue_a.key}.",
        ),
        db=mocker.ANY,
        current_user=mocker.ANY,
    )


@pytest.mark.asyncio
async def test_execute_resolution_deconflict(mock_issues, mocker: MockerFixture):
    """Tests that a 'deconflict' resolution correctly updates both issues."""
    # Arrange
    issue_a, issue_b = mock_issues
    resolution_request = IssueDuplicateResolutionRequest(
        issue1_id=issue_a.id,
        issue2_id=issue_b.id,
        resolution="deconflict",
        resulting_issue_1_title="Deconflicted Title A",
        resulting_issue_1_description="Deconflicted Desc A",
        resulting_issue_2_title="Deconflicted Title B",
        resulting_issue_2_description="Deconflicted Desc B",
    )

    mock_crud_issue = mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.crud_issue",
        new_callable=MagicMock,
    )
    mock_update_issue = mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.update_issue",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.crud_issue_duplicate",
        new_callable=MagicMock,
    )

    mock_crud_issue.get.side_effect = [issue_a, issue_b]

    # Act
    await execute_issue_duplicate_resolution(
        resolution=resolution_request, db=MagicMock(), current_user=MagicMock()
    )

    # Assert
    assert mock_update_issue.call_count == 2
    mock_update_issue.assert_any_call(
        issue_id=issue_a.id,
        issue_update=IssueUpdate(
            title="Deconflicted Title A", description="Deconflicted Desc A"
        ),
        db=mocker.ANY,
        current_user=mocker.ANY,
    )
    mock_update_issue.assert_any_call(
        issue_id=issue_b.id,
        issue_update=IssueUpdate(
            title="Deconflicted Title B", description="Deconflicted Desc B"
        ),
        db=mocker.ANY,
        current_user=mocker.ANY,
    )


@pytest.mark.asyncio
async def test_execute_resolution_issue_not_found(mocker: MockerFixture):
    """Tests that a 404 HTTPException is raised if an issue is not found."""
    # Arrange
    issue1_uuid = uuid4()
    issue2_uuid = uuid4()
    resolution_request = IssueDuplicateResolutionRequest(
        issue1_id=issue1_uuid, issue2_id=issue2_uuid, resolution="close_a"
    )
    mock_crud_issue = mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.crud_issue",
        new_callable=MagicMock,
    )
    # Configure the mock to be awaitable
    mock_crud_issue.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as excinfo:
        await execute_issue_duplicate_resolution(
            resolution=resolution_request, db=MagicMock(), current_user=MagicMock()
        )
    assert excinfo.value.status_code == 404
    assert "not found" in excinfo.value.detail


@pytest.mark.asyncio
async def test_execute_resolution_invalid_type(mock_issues, mocker: MockerFixture):
    """Tests that a 400 HTTPException is raised for an invalid resolution type."""
    # Arrange
    issue_a, issue_b = mock_issues
    resolution_request = IssueDuplicateResolutionRequest(
        issue1_id=issue_a.id, issue2_id=issue_b.id, resolution="invalid_type"
    )
    mock_crud_issue = mocker.patch(
        "preloop_ai.api.endpoints.issue_duplicates.crud_issue",
        new_callable=MagicMock,
    )
    # Configure the mock to be awaitable
    mock_crud_issue.get.side_effect = [issue_a, issue_b]

    # Act & Assert
    with pytest.raises(HTTPException) as excinfo:
        await execute_issue_duplicate_resolution(
            resolution=resolution_request, db=MagicMock(), current_user=MagicMock()
        )
    assert excinfo.value.status_code == 400
    assert "Invalid resolution type" in excinfo.value.detail


@patch("preloop_ai.api.endpoints.issue_duplicates.crud_issue_duplicate.get_multi")
def test_get_duplicate_issues_success(mock_get_multi):
    """
    Tests the get_duplicate_issues function for a successful request.
    """
    mock_get_multi.return_value = []
    db_session = MagicMock()
    current_user = MagicMock()

    result = issue_duplicates.get_duplicate_issues(
        db=db_session, current_user=current_user
    )
    assert result == []


@patch(
    "preloop_ai.api.endpoints.issue_duplicates.crud_issue_duplicate.get_by_issue_ids"
)
def test_check_or_create_issue_duplicate_existing(mock_get_by_issue_ids):
    """
    Tests the check_or_create_issue_duplicate function when a duplicate already exists.
    """
    issue1_uuid = uuid4()
    issue2_uuid = uuid4()
    ai_model_uuid = uuid4()

    mock_get_by_issue_ids.return_value = MagicMock(
        issue1_id=issue1_uuid,
        issue2_id=issue2_uuid,
        decision="duplicate",
        reason="test",
        suggestion="test",
        resolution="test",
        resolution_reason="test",
        resulting_issue1_id=issue1_uuid,
        resulting_issue2_id=issue2_uuid,
        ai_model_id=ai_model_uuid,
        ai_model_name="test",
    )
    db_session = MagicMock()
    current_user = MagicMock()
    settings = MagicMock()

    result = issue_duplicates.check_or_create_issue_duplicate(
        db=db_session,
        issue1_id=str(issue1_uuid),
        issue2_id=str(issue2_uuid),
        current_user=current_user,
        settings=settings,
    )
    assert result is not None
