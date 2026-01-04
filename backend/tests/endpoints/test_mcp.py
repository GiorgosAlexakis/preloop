"""
Tests for the MCP API endpoints.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import Session

from preloop.api.endpoints import mcp
from preloop.api.endpoints.search import SearchResponse as ApiSearchResponse
from preloop.schemas.issue import IssueResponse
from preloop.schemas.mcp import (
    SuggestedUpdate,
    UpdateIssueRequest,
    GetIssueResponse,
)
from preloop.models.models import (
    Organization,
    Project,
    Issue,
    Tracker,
    EmbeddingModel,
)
from preloop.models.models.user import User


@pytest.mark.asyncio
async def test_mcp_get_issue_success(db_session: Session, test_user: User):
    """
    Tests successful retrieval of an issue via the MCP get_issue tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="github",
        api_key="test_key",
        url="https://github.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org", identifier="test-org", tracker_id=tracker.id
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="test-proj",
        identifier="test-proj",
        slug="test-proj",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    issue = Issue(
        title="Test Issue",
        description="A test issue.",
        project_id=project.id,
        tracker_id=tracker.id,
        external_id="123",
        key="TP-1",
    )
    db_session.add(issue)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request") as mock_get_request,
        patch(
            "preloop.api.endpoints.mcp.get_user_from_token_if_valid",
            new_callable=AsyncMock,
        ) as mock_get_user,
        patch("preloop.api.endpoints.mcp.get_db") as mock_get_db,
    ):
        mock_get_request.return_value.headers = {"authorization": "Bearer testtoken"}
        mock_get_user.return_value = test_user
        mock_get_db.return_value = iter([db_session])

        response = await mcp.get_issue(issue=str(issue.id))

    # response.id is a UUID object, need to compare with issue.id directly
    assert response.id == issue.id
    assert response.key == "TP-1"
    assert response.title == "Test Issue"
    assert response.project == "test-proj"
    assert response.organization == "test-org"


@pytest.mark.asyncio
async def test_mcp_create_issue_success(db_session: Session, test_user: User):
    """
    Tests successful creation of an issue via the MCP create_issue tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="github",
        api_key="test_key",
        url="https://github.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org", identifier="test-org", tracker_id=tracker.id
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="test-proj",
        identifier="test-proj",
        slug="test-proj",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request") as mock_get_request,
        patch(
            "preloop.api.endpoints.mcp.get_user_from_token_if_valid",
            new_callable=AsyncMock,
        ) as mock_get_user,
        patch(
            "preloop.api.endpoints.mcp.api_create_issue", new_callable=AsyncMock
        ) as mock_api_create,
        patch("preloop.api.endpoints.mcp.get_db") as mock_get_db,
    ):
        mock_get_request.return_value.headers = {"authorization": "Bearer testtoken"}
        mock_get_user.return_value = test_user
        mock_get_db.return_value = iter([db_session])
        mock_api_create.return_value = IssueResponse(
            id=str(uuid.uuid4()),
            external_id="ext-123",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            url="http://example.com/issue/1",
            key="TP-1",
            title="New Issue",
            project="test-proj",
            project_id=str(project.id),
            organization="test-org",
        )

        response = await mcp.create_issue(
            project="test-proj",
            title="New Issue",
            description="A new test issue.",
            prevent_duplicates=False,
        )

    assert response.status == "created"
    assert response.message == "Successfully created new issue."
    mock_api_create.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_update_issue_success(db_session: Session, test_user: User):
    """
    Tests successful update of an issue via the MCP update_issue tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="github",
        api_key="test_key",
        url="https://github.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org", identifier="test-org", tracker_id=tracker.id
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="test-proj",
        identifier="test-proj",
        slug="test-proj",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    issue = Issue(
        title="Original Title",
        description="Original description.",
        project_id=project.id,
        tracker_id=tracker.id,
        external_id="456",
        key="TP-2",
        status="open",
    )
    db_session.add(issue)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request") as mock_get_request,
        patch(
            "preloop.api.endpoints.mcp.get_user_from_token_if_valid",
            new_callable=AsyncMock,
        ) as mock_get_user,
        patch(
            "preloop.api.endpoints.mcp.get_tracker_client", new_callable=AsyncMock
        ) as mock_get_tracker,
        patch("preloop.api.endpoints.mcp.get_db") as mock_get_db,
    ):
        mock_get_request.return_value.headers = {"authorization": "Bearer testtoken"}
        mock_get_user.return_value = test_user
        mock_get_db.return_value = iter([db_session])
        mock_tracker_client = AsyncMock()
        mock_get_tracker.return_value = mock_tracker_client

        response = await mcp.update_issue(issue=str(issue.id), title="Updated Title")

    assert isinstance(response, GetIssueResponse)
    assert response.title == "Updated Title"
    mock_tracker_client.update_issue.assert_called_once()
    db_session.refresh(issue)
    assert issue.title == "Updated Title"


@pytest.mark.asyncio
async def test_mcp_search_success(db_session: Session, test_user: User):
    """
    Tests the MCP search tool.
    """
    embedding_model = EmbeddingModel(
        name="test-embedding-model",
        provider="openai",
        version="text-embedding-ada-002",
        dimensions=1536,
        is_active=True,
    )
    db_session.add(embedding_model)
    db_session.commit()
    with (
        patch("preloop.api.endpoints.mcp.get_http_request") as mock_get_request,
        patch(
            "preloop.api.endpoints.mcp.get_user_from_token_if_valid",
            new_callable=AsyncMock,
        ) as mock_get_user,
        patch(
            "preloop.api.endpoints.mcp.perform_search", new_callable=AsyncMock
        ) as mock_perform_search,
        patch("preloop.api.endpoints.mcp.get_db") as mock_get_db,
    ):
        mock_get_request.return_value.headers = {"authorization": "Bearer testtoken"}
        mock_get_user.return_value = test_user
        mock_perform_search.return_value = ApiSearchResponse(results=[])
        mock_get_db.return_value = iter([db_session])

        response = await mcp.search(query="test query", project="test-proj")

    assert isinstance(response, ApiSearchResponse)


@pytest.mark.asyncio
async def test_mcp_estimate_compliance_success(db_session: Session, test_user: User):
    """
    Tests the MCP estimate_compliance tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="github",
        api_key="test_key",
        url="https://github.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org", identifier="test-org", tracker_id=tracker.id
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="test-proj",
        identifier="test-proj",
        slug="test-proj",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    issue = Issue(
        title="Test Issue",
        project_id=project.id,
        tracker_id=tracker.id,
        external_id="789",
        key="TP-3",
    )
    db_session.add(issue)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request"),
        patch(
            "preloop.api.endpoints.mcp._get_authenticated_user",
            new_callable=AsyncMock,
        ) as mock_auth,
        patch(
            "preloop.api.endpoints.mcp._process_single_issue_estimate",
            new_callable=AsyncMock,
        ) as mock_process,
    ):
        mock_auth.return_value = (db_session, test_user)
        mock_process.return_value = MagicMock(
            success=True,
            data={
                "id": str(uuid.uuid4()),
                "compliance_factor": 0.8,
                "reason": "Looks good.",
                "issue_id": str(issue.id),
                "prompt_id": "test",
                "name": "Test Compliance",
                "suggestion": "No suggestion",
                "short_name": "test",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )

        response = await mcp.estimate_compliance(issues=[str(issue.id)])

    assert len(response.results) == 1
    assert response.results[0].compliance_factor == 0.8


@pytest.mark.asyncio
async def test_mcp_improve_compliance_success(db_session: Session, test_user: User):
    """
    Tests the MCP improve_compliance tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="github",
        api_key="test_key",
        url="https://github.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org", identifier="test-org", tracker_id=tracker.id
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="test-proj",
        identifier="test-proj",
        slug="test-proj",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    issue = Issue(
        title="Test Issue",
        project_id=project.id,
        tracker_id=tracker.id,
        external_id="101",
        key="TP-4",
    )
    db_session.add(issue)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request"),
        patch(
            "preloop.api.endpoints.mcp._get_authenticated_user",
            new_callable=AsyncMock,
        ) as mock_auth,
        patch(
            "preloop.api.endpoints.mcp._process_single_issue_compliance",
            new_callable=AsyncMock,
        ) as mock_process,
    ):
        mock_auth.return_value = (db_session, test_user)
        mock_process.return_value = MagicMock(
            success=True,
            data=SuggestedUpdate(
                issue_identifier=str(issue.id),
                arguments=UpdateIssueRequest(
                    issue=str(issue.id), title="Improved Title"
                ),
            ),
        )

        response = await mcp.improve_compliance(issues=[str(issue.id)])

    assert len(response.suggested_updates) == 1
    assert response.suggested_updates[0].arguments.title == "Improved Title"


@pytest.mark.asyncio
async def test_mcp_add_comment_success(db_session: Session, test_user: User):
    """
    Tests successful addition of a comment via the MCP add_comment tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="github",
        api_key="test_key",
        url="https://github.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org", identifier="test-org", tracker_id=tracker.id
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="test-proj",
        identifier="test-proj",
        slug="test-proj",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    issue = Issue(
        title="Test Issue",
        description="A test issue.",
        project_id=project.id,
        tracker_id=tracker.id,
        external_id="123",
        key="TP-1",
    )
    db_session.add(issue)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request") as mock_get_request,
        patch(
            "preloop.api.endpoints.mcp.get_user_from_token_if_valid",
            new_callable=AsyncMock,
        ) as mock_get_user,
        patch("preloop.api.endpoints.mcp.get_db") as mock_get_db,
        patch(
            "preloop.api.endpoints.mcp.get_tracker_client",
            new_callable=AsyncMock,
        ) as mock_get_tracker,
    ):
        mock_get_request.return_value.headers = {"authorization": "Bearer testtoken"}
        mock_get_user.return_value = test_user
        mock_get_db.return_value = iter([db_session])

        mock_tracker = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = "comment-123"
        mock_comment.meta_data = {
            "url": "https://github.com/owner/repo/issues/1#comment-123"
        }
        mock_tracker.add_comment = AsyncMock(return_value=mock_comment)
        mock_get_tracker.return_value = mock_tracker

        response = await mcp.add_comment(target=str(issue.id), comment="Test comment")

    assert response.status == "created"
    assert "successfully added comment" in response.message.lower()


@pytest.mark.asyncio
async def test_mcp_get_pull_request_success(db_session: Session, test_user: User):
    """
    Tests successful retrieval of a GitHub pull request via the MCP get_pull_request tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="github",
        api_key="test_key",
        url="https://github.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org",
        identifier="test-org",
        tracker_id=tracker.id,
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="owner/repo",
        identifier="owner/repo",
        slug="owner/repo",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request") as mock_get_request,
        patch("preloop.api.endpoints.mcp.get_db") as mock_get_db,
        patch(
            "preloop.api.endpoints.mcp._get_authenticated_user",
            new_callable=AsyncMock,
        ) as mock_auth,
        patch(
            "preloop.api.endpoints.mcp.get_tracker_client",
            new_callable=AsyncMock,
        ) as mock_get_tracker,
    ):
        mock_get_request.return_value.headers = {"authorization": "Bearer testtoken"}
        mock_get_db.return_value = iter([db_session])
        mock_auth.return_value = (db_session, test_user)

        mock_tracker = MagicMock()
        mock_tracker.tracker_type = "github"
        mock_tracker.client = MagicMock()
        mock_tracker.client.get_pull_request = AsyncMock(
            return_value={
                "id": "pr-123",
                "number": 123,
                "title": "Test PR",
                "description": "Test PR description",
                "state": "open",
                "author": "testuser",
                "url": "https://github.com/owner/repo/pull/123",
            }
        )
        mock_tracker.get_pull_request = mock_tracker.client.get_pull_request
        mock_get_tracker.return_value = mock_tracker

        response = await mcp.get_pull_request(pull_request="owner/repo#123")

    assert response.number == 123
    assert response.title == "Test PR"
    assert response.state == "open"


@pytest.mark.asyncio
async def test_mcp_get_merge_request_success(db_session: Session, test_user: User):
    """
    Tests successful retrieval of a GitLab merge request via the MCP get_merge_request tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="gitlab",
        api_key="test_key",
        url="https://gitlab.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org",
        identifier="test-org",
        tracker_id=tracker.id,
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="group/project",
        identifier="group/project",
        slug="group/project",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request") as mock_get_request,
        patch("preloop.api.endpoints.mcp.get_db") as mock_get_db,
        patch(
            "preloop.api.endpoints.mcp._get_authenticated_user",
            new_callable=AsyncMock,
        ) as mock_auth,
        patch(
            "preloop.api.endpoints.mcp.get_tracker_client",
            new_callable=AsyncMock,
        ) as mock_get_tracker,
    ):
        mock_get_request.return_value.headers = {"authorization": "Bearer testtoken"}
        mock_get_db.return_value = iter([db_session])
        mock_auth.return_value = (db_session, test_user)

        mock_tracker = MagicMock()
        mock_tracker.tracker_type = "gitlab"
        mock_tracker.client = MagicMock()
        mock_tracker.client.get_merge_request = AsyncMock(
            return_value={
                "id": "mr-456",
                "iid": 456,
                "title": "Test MR",
                "description": "Test MR description",
                "state": "opened",
                "author": "testuser",
                "url": "https://gitlab.com/group/project/-/merge_requests/456",
            }
        )
        mock_tracker.get_merge_request = mock_tracker.client.get_merge_request
        mock_get_tracker.return_value = mock_tracker

        response = await mcp.get_merge_request(merge_request="group/project#456")

    assert response.iid == 456
    assert response.title == "Test MR"
    assert response.state == "opened"


@pytest.mark.asyncio
async def test_mcp_update_pull_request_success(db_session: Session, test_user: User):
    """
    Tests successful update of a GitHub pull request via the MCP update_pull_request tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="github",
        api_key="test_key",
        url="https://github.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org",
        identifier="test-org",
        tracker_id=tracker.id,
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="owner/repo",
        identifier="owner/repo",
        slug="owner/repo",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request") as mock_get_request,
        patch("preloop.api.endpoints.mcp.get_db") as mock_get_db,
        patch(
            "preloop.api.endpoints.mcp._get_authenticated_user",
            new_callable=AsyncMock,
        ) as mock_auth,
        patch(
            "preloop.api.endpoints.mcp.get_tracker_client",
            new_callable=AsyncMock,
        ) as mock_get_tracker,
    ):
        mock_get_request.return_value.headers = {"authorization": "Bearer testtoken"}
        mock_get_db.return_value = iter([db_session])
        mock_auth.return_value = (db_session, test_user)

        mock_tracker = MagicMock()
        mock_tracker.tracker_type = "github"
        mock_tracker.client = MagicMock()
        mock_tracker.client.update_pull_request = AsyncMock(
            return_value={
                "id": "pr-123",
                "number": 123,
                "title": "Updated PR Title",
                "description": "Updated PR description",
                "state": "open",
                "url": "https://github.com/owner/repo/pull/123",
            }
        )
        mock_tracker.update_pull_request = mock_tracker.client.update_pull_request
        mock_get_tracker.return_value = mock_tracker

        response = await mcp.update_pull_request(
            pull_request="owner/repo#123", title="Updated PR Title"
        )

    assert response.status == "updated"
    assert response.pull_request_id == "pr-123"
    assert "Successfully updated pull request" in response.message


@pytest.mark.asyncio
async def test_mcp_update_merge_request_success(db_session: Session, test_user: User):
    """
    Tests successful update of a GitLab merge request via the MCP update_merge_request tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.account_id,
        tracker_type="gitlab",
        api_key="test_key",
        url="https://gitlab.com",
    )
    db_session.add(tracker)
    db_session.commit()

    organization = Organization(
        name="test-org",
        identifier="test-org",
        tracker_id=tracker.id,
    )
    db_session.add(organization)
    db_session.commit()

    project = Project(
        name="group/project",
        identifier="group/project",
        slug="group/project",
        organization_id=organization.id,
    )
    db_session.add(project)
    db_session.commit()

    with (
        patch("preloop.api.endpoints.mcp.get_http_request") as mock_get_request,
        patch("preloop.api.endpoints.mcp.get_db") as mock_get_db,
        patch(
            "preloop.api.endpoints.mcp._get_authenticated_user",
            new_callable=AsyncMock,
        ) as mock_auth,
        patch(
            "preloop.api.endpoints.mcp.get_tracker_client",
            new_callable=AsyncMock,
        ) as mock_get_tracker,
    ):
        mock_get_request.return_value.headers = {"authorization": "Bearer testtoken"}
        mock_get_db.return_value = iter([db_session])
        mock_auth.return_value = (db_session, test_user)

        mock_tracker = MagicMock()
        mock_tracker.tracker_type = "gitlab"
        mock_tracker.client = MagicMock()
        mock_tracker.client.update_merge_request = AsyncMock(
            return_value={
                "id": "mr-456",
                "iid": 456,
                "title": "Updated MR Title",
                "description": "Updated MR description",
                "state": "opened",
                "url": "https://gitlab.com/group/project/-/merge_requests/456",
            }
        )
        mock_tracker.update_merge_request = mock_tracker.client.update_merge_request
        mock_get_tracker.return_value = mock_tracker

        response = await mcp.update_merge_request(
            merge_request="group/project#456", title="Updated MR Title"
        )

    assert response.status == "updated"
    assert response.merge_request_id == "mr-456"
    assert "Successfully updated merge request" in response.message
