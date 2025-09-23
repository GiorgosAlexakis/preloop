"""
Tests for the MCP API endpoints.
"""

import uuid
from unittest.mock import patch
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from spacebridge.api.endpoints.search import SearchResponse
from spacebridge.schemas.issue import IssueResponse
from spacebridge.schemas.issue_compliance import ComplianceSuggestionResponse
from spacemodels.models import Account, Organization, Project, Issue, Tracker


def test_mcp_get_issue_success(
    client: TestClient, db_session: Session, test_user: Account
):
    """
    Tests successful retrieval of an issue via the MCP get_issue tool.
    """
    # 1. Create test data
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.id,
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

    # 2. Make the API call
    response = client.post(
        "/api/v1/mcp/get_issue",
        json={"issue": f"test-org/test-proj#{issue.key}"},
    )

    # 3. Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(issue.id)
    assert data["key"] == "TP-1"
    assert data["title"] == "Test Issue"
    assert data["project"] == "test-proj"
    assert data["organization"] == "test-org"
    assert "compliance_results" in data


def test_mcp_create_issue_success(
    client: TestClient, db_session: Session, test_user: Account
):
    """
    Tests successful creation of an issue via the MCP create_issue tool.
    """
    # 1. Create test data
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.id,
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

    # 2. Make the API call
    with patch(
        "spacebridge.api.endpoints.mcp.api_create_issue",
        new_callable=AsyncMock,
    ) as mock_create:
        # The actual API returns an IssueResponse, so we mock that
        mock_create.return_value = IssueResponse(
            id=str(uuid.uuid4()),
            external_id="999",
            key="TP-99",
            title="New Issue",
            description="A new test issue.",
            organization="test-org",
            project="test-proj",
            project_id=str(project.id),
            url="http://example.com/issue/1",
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-01T00:00:00",
        )
        response = client.post(
            "/api/v1/mcp/create_issue",
            json={
                "project": "test-proj",
                "title": "New Issue",
                "description": "A new test issue.",
            },
        )

    # 3. Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "created"
    assert data["message"] == "Successfully created new issue."


def test_mcp_update_issue_success(
    client: TestClient, db_session: Session, test_user: Account
):
    """
    Tests successful update of an issue via the MCP update_issue tool.
    """
    # 1. Create test data
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.id,
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
    )
    db_session.add(issue)
    db_session.commit()

    # 2. Make the API call
    with patch(
        "spacebridge.api.endpoints.mcp.api_update_issue", new_callable=AsyncMock
    ) as mock_update:
        mock_update.return_value = IssueResponse(
            id=str(issue.id),
            external_id=issue.external_id,
            key=issue.key,
            title="Updated Title",
            description=issue.description,
            organization="test-org",
            project="test-proj",
            project_id=str(project.id),
            url="http://example.com/issue/2",
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-01T00:00:00",
        )
        response = client.post(
            "/api/v1/mcp/update_issue",
            json={"issue": str(issue.id), "title": "Updated Title"},
        )

    # 3. Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"
    assert data["issue_id"] == str(issue.id)


def test_mcp_search_success(client: TestClient):
    """
    Tests the MCP search tool.
    """
    with patch(
        "spacebridge.api.endpoints.mcp.api_search_all",
        return_value=SearchResponse(results=[]),
    ) as mock_search:
        response = client.post(
            "/api/v1/mcp/search",
            json={"query": "test query", "project": "test-proj"},
        )
        assert response.status_code == 200
        mock_search.assert_called_once()


def test_mcp_estimate_compliance_success(
    client: TestClient, db_session: Session, test_user: Account
):
    """
    Tests the MCP estimate_compliance tool.
    """
    # This test is simplified and assumes the underlying compliance logic is tested elsewhere.
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.id,
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

    with patch(
        "spacebridge.api.endpoints.mcp.api_get_issue_compliance"
    ) as mock_get_compliance:
        mock_get_compliance.return_value = {
            "id": str(uuid.uuid4()),
            "prompt_id": "default",
            "name": "Default Compliance",
            "short_name": "Default",
            "compliance_factor": 0.8,
            "reason": "Looks good.",
            "suggestion": "No suggestion.",
            "issue_id": str(issue.id),
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }
        response = client.post(
            "/api/v1/mcp/estimate_compliance",
            json={"issues": [str(issue.id)]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["compliance_factor"] == 0.8


def test_mcp_improve_compliance_success(
    client: TestClient, db_session: Session, test_user: Account
):
    """
    Tests the MCP improve_compliance tool.
    """
    tracker = Tracker(
        name="test-tracker",
        account_id=test_user.id,
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

    with patch(
        "spacebridge.api.endpoints.mcp.api_get_compliance_suggestion"
    ) as mock_get_suggestion:
        # Mock should return the Pydantic model, not a dict
        mock_get_suggestion.return_value = ComplianceSuggestionResponse(
            title="Improved Title",
            description="Improved description.",
            changes="- Fixed the title\n- Expanded the description",
        )
        response = client.post(
            "/api/v1/mcp/improve_compliance",
            json={"issues": [str(issue.id)]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["suggested_updates"]) == 1
        assert data["suggested_updates"][0]["arguments"]["title"] == "Improved Title"
