from datetime import datetime, timezone
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from spacemodels.models import (
    Account,
    Issue,
    Organization,
    Project,
    Tracker,
    TrackerScopeRule,
)


def test_search_issues_simple(
    client: TestClient,
    db_session: Session,
    test_user: Account,
):
    """Test basic issue search."""
    # Create and commit test data
    tracker = Tracker(
        id=str(uuid.uuid4()),
        name="Test Tracker",
        tracker_type="github",
        url="http://test.com",
        api_key="test_key",
        account_id=test_user.id,  # Use the authenticated user's ID
    )
    org = Organization(
        id=str(uuid.uuid4()),
        name="Test Org",
        identifier="test-org",
        tracker_id=tracker.id,
    )
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Project",
        identifier="test-proj",
        organization_id=org.id,
    )
    issue = Issue(
        id=str(uuid.uuid4()),
        title="Test Issue",
        project_id=project.id,
        tracker_id=tracker.id,
        external_id="123",
        key="TEST-1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    scope_rule = TrackerScopeRule(
        id=str(uuid.uuid4()),
        tracker_id=tracker.id,
        scope_type="ORGANIZATION",
        rule_type="INCLUDE",
        identifier=org.identifier,
    )
    db_session.add_all([tracker, org, project, issue, scope_rule])
    db_session.commit()

    # Make the API call
    response = client.get("/api/v1/issues/search?query=Test")

    # Assert the response
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["title"] == "Test Issue"


def test_search_issues_with_project_filter(
    client: TestClient,
    db_session: Session,
    test_user: Account,
):
    """Test issue search with a project filter."""
    # Create and commit test data
    tracker = Tracker(
        id=str(uuid.uuid4()),
        name="Test Tracker 2",
        tracker_type="github",
        url="http://test2.com",
        api_key="test_key_2",
        account_id=test_user.id,  # Use the authenticated user's ID
    )
    org = Organization(
        id=str(uuid.uuid4()),
        name="org2",
        identifier="org2",
        tracker_id=tracker.id,
    )
    project = Project(
        id=str(uuid.uuid4()),
        name="proj2",
        identifier="proj2",
        organization_id=org.id,
    )
    issue = Issue(
        id=str(uuid.uuid4()),
        title="Project Issue 2",
        project_id=project.id,
        tracker_id=tracker.id,
        external_id="457",
        key="PROJ-2",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    scope_rule = TrackerScopeRule(
        id=str(uuid.uuid4()),
        tracker_id=tracker.id,
        scope_type="ORGANIZATION",
        rule_type="INCLUDE",
        identifier=org.identifier,
    )
    db_session.add_all([tracker, org, project, issue, scope_rule])
    db_session.commit()

    # Make the API call
    response = client.get(
        f"/api/v1/issues/search?query=Project&organization={org.name}&project={project.name}"
    )

    # Assert the response
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["title"] == "Project Issue 2"
