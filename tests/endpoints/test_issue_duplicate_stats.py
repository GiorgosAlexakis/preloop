"""Tests for issue duplicate statistics endpoint."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from spacemodels.models import Tracker, Organization, Project


@pytest.fixture(autouse=True)
def mock_event_bus_connect():
    """Auto-mock the event bus connect method to avoid NATS connection attempts."""
    with patch(
        "spacesync.services.event_bus.EventBus.connect", new_callable=AsyncMock
    ) as mock_connect:
        yield mock_connect


def test_get_projects_duplicate_stats_empty(client: TestClient, db_session, test_user):
    """Test getting duplicate stats when no projects exist."""
    response = client.get("/api/v1/project-duplicate-stats")
    assert response.status_code == 200

    response_json = response.json()
    assert "projects" in response_json
    assert response_json["projects"] == {}


def test_get_projects_duplicate_stats_response_structure(client: TestClient):
    """Test that the response structure is correct.

    This test verifies the basic response structure without worrying
    about RBAC and project visibility.
    """
    response = client.get("/api/v1/project-duplicate-stats")
    assert response.status_code == 200

    response_json = response.json()
    assert "projects" in response_json
    assert isinstance(response_json["projects"], dict)


def test_get_projects_duplicate_stats_with_status_filter(
    client: TestClient, db_session, test_user
):
    """Test getting duplicate stats with status filter."""
    # Create tracker, org, and project
    tracker = Tracker(
        name="Test Tracker",
        tracker_type="github",
        url="https://github.com",
        account_id=test_user.account_id,
        api_key="test_key",
    )
    db_session.add(tracker)
    db_session.commit()

    org = Organization(
        name="Test Org",
        identifier="test-org",
        tracker_id=tracker.id,
    )
    db_session.add(org)
    db_session.commit()

    project = Project(
        name="Test Project",
        identifier="TEST",
        slug="test",
        organization_id=org.id,
    )
    db_session.add(project)
    db_session.commit()

    response = client.get("/api/v1/project-duplicate-stats?status=opened")
    assert response.status_code == 200


def test_get_projects_duplicate_stats_with_similarity_threshold(
    client: TestClient, db_session, test_user
):
    """Test getting duplicate stats with similarity threshold."""
    # Create tracker, org, and project
    tracker = Tracker(
        name="Test Tracker",
        tracker_type="github",
        url="https://github.com",
        account_id=test_user.account_id,
        api_key="test_key",
    )
    db_session.add(tracker)
    db_session.commit()

    org = Organization(
        name="Test Org",
        identifier="test-org",
        tracker_id=tracker.id,
    )
    db_session.add(org)
    db_session.commit()

    project = Project(
        name="Test Project",
        identifier="TEST",
        slug="test",
        organization_id=org.id,
    )
    db_session.add(project)
    db_session.commit()

    response = client.get("/api/v1/project-duplicate-stats?similarity_threshold=0.9")
    assert response.status_code == 200


def test_issue_duplicate_project_stats_schema_serialization():
    """Direct unit test for IssueDuplicateProjectStats schema serialization.

    This test verifies that UUID fields are properly serialized to strings.
    """
    from spacebridge.schemas.issue_duplicate import IssueDuplicateProjectStats
    import uuid

    project_id = uuid.uuid4()

    # Create schema instance with UUID
    stats = IssueDuplicateProjectStats(
        project_id=project_id,
        project_name="Test Project",
        total=10,
        duplicates=2,
    )

    # Verify serialization to dict
    stats_dict = stats.model_dump()
    assert isinstance(stats_dict["project_id"], str)
    assert stats_dict["project_id"] == str(project_id)
    assert stats_dict["project_name"] == "Test Project"
    assert stats_dict["total"] == 10
    assert stats_dict["duplicates"] == 2

    # Verify JSON serialization
    json_str = stats.model_dump_json()
    assert str(project_id) in json_str


def test_issue_duplicate_stats_schema_with_string_keys():
    """Test that IssueDuplicateStats requires string keys in the projects dict."""
    from spacebridge.schemas.issue_duplicate import (
        IssueDuplicateStats,
        IssueDuplicateProjectStats,
    )
    import uuid

    project_id1 = uuid.uuid4()
    project_id2 = uuid.uuid4()

    # Create with string keys (correct)
    stats = IssueDuplicateStats(
        projects={
            str(project_id1): IssueDuplicateProjectStats(
                project_id=project_id1,
                project_name="Project 1",
                total=5,
                duplicates=1,
            ),
            str(project_id2): IssueDuplicateProjectStats(
                project_id=project_id2,
                project_name="Project 2",
                total=3,
                duplicates=0,
            ),
        }
    )

    stats_dict = stats.model_dump()
    assert len(stats_dict["projects"]) == 2

    # Verify all keys are strings
    for key in stats_dict["projects"].keys():
        assert isinstance(key, str)


def test_issue_duplicate_stats_json_serialization():
    """Test that IssueDuplicateStats can be fully serialized to JSON."""
    from spacebridge.schemas.issue_duplicate import (
        IssueDuplicateStats,
        IssueDuplicateProjectStats,
    )
    import uuid

    project_id = uuid.uuid4()

    stats = IssueDuplicateStats(
        projects={
            str(project_id): IssueDuplicateProjectStats(
                project_id=project_id,
                project_name="Test Project",
                total=10,
                duplicates=2,
            ),
        }
    )

    # This should not raise any errors
    json_str = stats.model_dump_json()

    # Verify the JSON is valid and contains expected data
    assert str(project_id) in json_str
    assert "Test Project" in json_str

    # Verify we can parse it back
    import json

    parsed = json.loads(json_str)
    assert str(project_id) in parsed["projects"]
    assert parsed["projects"][str(project_id)]["project_name"] == "Test Project"
