import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Tuple
from fastapi import HTTPException
from pytest_mock import MockerFixture

from spacebridge.api.endpoints.issue_duplicates import (
    execute_issue_duplicate_resolution,
)
from spacebridge.schemas import (
    IssueDuplicateResolutionRequest,
    IssueUpdate,
)
from spacemodels.models.issue import Issue


@pytest.fixture
def mock_issues(mocker: MockerFixture) -> Tuple[MagicMock, MagicMock]:
    """Provides mock Issue objects for testing."""
    issue_a = MagicMock(spec=Issue)
    issue_a.id = "db_id_a"
    issue_a.key = "PROJ-1"
    issue_a.title = "Original Title A"
    issue_a.description = "Original Description A"

    issue_b = MagicMock(spec=Issue)
    issue_b.id = "db_id_b"
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
        "spacebridge.api.endpoints.issue_duplicates.crud_issue",
        new_callable=MagicMock,
    )
    mock_update_issue = mocker.patch(
        "spacebridge.api.endpoints.issue_duplicates.update_issue",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "spacebridge.api.endpoints.issue_duplicates.crud_issue_duplicate",
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
        "spacebridge.api.endpoints.issue_duplicates.crud_issue",
        new_callable=MagicMock,
    )
    mock_update_issue = mocker.patch(
        "spacebridge.api.endpoints.issue_duplicates.update_issue",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "spacebridge.api.endpoints.issue_duplicates.crud_issue_duplicate",
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
        "spacebridge.api.endpoints.issue_duplicates.crud_issue",
        new_callable=MagicMock,
    )
    mock_update_issue = mocker.patch(
        "spacebridge.api.endpoints.issue_duplicates.update_issue",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "spacebridge.api.endpoints.issue_duplicates.crud_issue_duplicate",
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
    resolution_request = IssueDuplicateResolutionRequest(
        issue1_id="a", issue2_id="b", resolution="close_a"
    )
    mock_crud_issue = mocker.patch(
        "spacebridge.api.endpoints.issue_duplicates.crud_issue",
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
        "spacebridge.api.endpoints.issue_duplicates.crud_issue",
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
