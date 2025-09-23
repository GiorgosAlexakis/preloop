import pytest
from unittest.mock import Mock
from datetime import datetime

from spacesync.trackers.base import BaseTracker


class ConcreteTracker(BaseTracker):
    def get_organizations(self):
        return []

    def get_projects(self, organization_id):
        return []

    def get_issues(self, organization_id, project_id, since=None):
        return []

    def register_webhook(self, **kwargs):
        return True

    def unregister_webhook(self, **kwargs):
        return True

    def is_webhook_registered(self, webhook):
        return True

    def get_webhooks(self):
        return []

    def delete_webhook(self, webhook):
        return True

    def unregister_all_webhooks(self, webhook_url_pattern=None):
        return {"unregistered": 0, "failed": 0, "not_found": 0}

    def is_webhook_registered_for_project(self, project, webhook_url):
        return True

    def is_webhook_registered_for_organization(self, organization, webhook_url):
        return True


@pytest.fixture
def tracker():
    return ConcreteTracker("tracker-1", "api-key", {})


def test_transform_organization(tracker):
    org_data = {"id": "org-1", "name": "Test Org"}
    transformed = tracker.transform_organization(org_data)
    assert transformed["identifier"] == "org-1"
    assert transformed["name"] == "Test Org"
    assert transformed["tracker_id"] == "tracker-1"


def test_transform_project(tracker):
    proj_data = {"id": "proj-1", "name": "Test Proj", "description": "A test project"}
    transformed = tracker.transform_project(proj_data, "org-db-id")
    assert transformed["identifier"] == "proj-1"
    assert transformed["name"] == "Test Proj"
    assert transformed["organization_id"] == "org-db-id"


def test_transform_issue(tracker):
    issue_data = {
        "id": "issue-1",
        "title": "Test Issue",
        "description": "A test issue",
        "state": "open",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    mock_project = Mock()
    mock_project.id = "project-db-id"
    transformed = tracker.transform_issue(issue_data, mock_project)
    assert transformed["external_id"] == "issue-1"
    assert transformed["title"] == "Test Issue"
    assert transformed["project_id"] == "project-db-id"


def test_transform_comment(tracker):
    comment_data = {"id": "comment-1", "body": "A test comment"}
    transformed = tracker.transform_comment(comment_data, "issue-db-id")
    assert transformed["external_id"] == "comment-1"
    assert transformed["body"] == "A test comment"
    assert transformed["issue_id"] == "issue-db-id"
