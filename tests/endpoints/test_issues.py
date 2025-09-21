from datetime import datetime, timezone
import uuid
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from spacebridge.api.app import create_app
from spacemodels.db.session import get_db_session
from spacemodels.models import (
    Account,
    Issue,
    Organization,
    Project,
    Tracker,
    TrackerScopeRule,
)
from spacebridge.api.auth import get_current_active_user


@pytest.fixture(scope="module")
def test_app():
    """Create a FastAPI app instance for the module, with NATS mocked out."""
    with (
        patch("spacebridge.api.app.connect_nats", new_callable=AsyncMock),
        patch("spacebridge.api.app.close_nats", new_callable=AsyncMock),
    ):
        app = create_app()
        yield app


@pytest.fixture
def client(test_app: "FastAPI", db_session: Session, test_user: Account):
    """Create a test client with authenticated user and DB session overrides."""

    def override_get_db():
        yield db_session

    def override_get_current_user():
        return test_user

    test_app.dependency_overrides[get_db_session] = override_get_db
    test_app.dependency_overrides[get_current_active_user] = override_get_current_user

    with TestClient(test_app) as c:
        yield c

    test_app.dependency_overrides.clear()


@patch("spacebridge.api.endpoints.issues.get_tracker_client", new_callable=AsyncMock)
def test_search_issues_simple(
    mock_get_tracker_client: AsyncMock,
    client: TestClient,
    db_session: Session,
    test_user: Account,
):
    """Test basic issue search."""
    tracker = Tracker(
        id=str(uuid.uuid4()),
        name="Test Tracker",
        tracker_type="github",
        url="http://test.com",
        api_key="test_key",
        account_id=test_user.id,
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

    response = client.get("/api/v1/issues/search?query=Test")

    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["title"] == "Test Issue"


@patch("spacebridge.api.endpoints.issues.get_tracker_client", new_callable=AsyncMock)
def test_search_issues_with_project_filter(
    mock_get_tracker_client: AsyncMock,
    client: TestClient,
    db_session: Session,
    test_user: Account,
):
    """Test issue search with a project filter."""
    tracker = Tracker(
        id=str(uuid.uuid4()),
        name="Test Tracker 2",
        tracker_type="github",
        url="http://test2.com",
        api_key="test_key_2",
        account_id=test_user.id,
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

    response = client.get(
        f"/api/v1/issues/search?query=Project&organization={org.name}&project={project.name}"
    )

    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["title"] == "Project Issue 2"
