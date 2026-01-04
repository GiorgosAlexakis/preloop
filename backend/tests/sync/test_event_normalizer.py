"""
Tests for event normalization and filter field extraction.

Tests use real webhook payload structures from GitLab, GitHub, and Jira.
"""

import pytest
from preloop.sync.event_normalizer import (
    normalize_event_type,
    extract_filter_fields,
)
from preloop.sync.webhook_payloads import (
    GITLAB_ISSUE_OPENED,
    GITLAB_ISSUE_CLOSED,
    GITHUB_ISSUE_OPENED,
    GITHUB_ISSUE_CLOSED,
    JIRA_ISSUE_CREATED,
)


class TestEventNormalization:
    """Test event type normalization for different trackers."""

    def test_gitlab_issue_opened_normalization(self):
        """Test GitLab 'Issue Hook' with action='open' normalizes to 'issue_opened'."""
        normalized = normalize_event_type("gitlab", "Issue Hook", GITLAB_ISSUE_OPENED)
        assert normalized == "issue_opened"

    def test_gitlab_issue_closed_normalization(self):
        """Test GitLab 'Issue Hook' with action='close' normalizes to 'issue_closed'."""
        normalized = normalize_event_type("gitlab", "Issue Hook", GITLAB_ISSUE_CLOSED)
        assert normalized == "issue_closed"

    def test_gitlab_merge_request_normalization(self):
        """Test GitLab 'Merge Request Hook' normalizes to 'merge_request_opened'."""
        normalized = normalize_event_type("gitlab", "Merge Request Hook", {})
        assert normalized == "merge_request_opened"

    def test_github_issue_opened_normalization(self):
        """Test GitHub 'issues' with action='opened' normalizes to 'issue_opened'."""
        normalized = normalize_event_type("github", "issues", GITHUB_ISSUE_OPENED)
        assert normalized == "issue_opened"

    def test_github_issue_closed_normalization(self):
        """Test GitHub 'issues' with action='closed' normalizes to 'issue_closed'."""
        normalized = normalize_event_type("github", "issues", GITHUB_ISSUE_CLOSED)
        assert normalized == "issue_closed"

    def test_github_pull_request_normalization(self):
        """Test GitHub 'pull_request' normalizes to 'pull_request_opened'."""
        normalized = normalize_event_type(
            "github", "pull_request", {"action": "opened"}
        )
        assert normalized == "pull_request_opened"

    def test_jira_issue_created_normalization(self):
        """Test Jira 'jira:issue_created' normalizes to 'issue_opened'."""
        normalized = normalize_event_type(
            "jira", "jira:issue_created", JIRA_ISSUE_CREATED
        )
        assert normalized == "issue_opened"

    def test_unknown_tracker_type(self):
        """Test unknown tracker type returns original event type."""
        normalized = normalize_event_type("unknown", "some_event", {})
        assert normalized == "some_event"


class TestFilterFieldExtraction:
    """Test extraction of filter fields from webhook payloads."""

    def test_gitlab_issue_opened_filters(self):
        """Test GitLab issue opened event extracts correct filter fields."""
        fields = extract_filter_fields("gitlab", "Issue Hook", GITLAB_ISSUE_OPENED)

        assert fields["author"] == "root"
        assert fields["assignee"] == ["user1"]
        assert set(fields["labels"]) == {"API", "Feature"}
        assert fields["state"] == "opened"
        assert fields["action"] == "open"

    def test_gitlab_issue_closed_filters(self):
        """Test GitLab issue closed event extracts correct filter fields."""
        fields = extract_filter_fields("gitlab", "Issue Hook", GITLAB_ISSUE_CLOSED)

        assert fields["author"] == "root"
        assert fields["state"] == "closed"
        assert fields["action"] == "close"

    def test_github_issue_opened_filters(self):
        """Test GitHub issue opened event extracts correct filter fields."""
        fields = extract_filter_fields("github", "issues", GITHUB_ISSUE_OPENED)

        assert fields["author"] == "octocat"
        assert fields["assignee"] == ["octocat"]
        assert fields["labels"] == ["bug"]
        assert fields["state"] == "open"
        assert fields["action"] == "opened"
        assert fields["sender"] == "octocat"

    def test_github_issue_closed_filters(self):
        """Test GitHub issue closed event extracts correct filter fields."""
        fields = extract_filter_fields("github", "issues", GITHUB_ISSUE_CLOSED)

        assert fields["state"] == "closed"
        assert fields["action"] == "closed"

    def test_jira_issue_created_filters(self):
        """Test Jira issue created event extracts correct filter fields."""
        fields = extract_filter_fields("jira", "jira:issue_created", JIRA_ISSUE_CREATED)

        assert (
            "Creator Name" in fields["author"]
            or fields["author"] == "5b10a2844c20165700ede21g"
        )
        assert (
            "Assignee Name" in fields["assignee"]
            or fields["assignee"] == "5b10a2844c20165700ede21g"
        )
        assert set(fields["labels"]) == {"backend", "api"}
        assert fields["priority"] == "Medium"
        assert fields["state"] == "To Do"
        assert fields["issue_type"] == "Task"

    def test_filter_fields_missing_data(self):
        """Test that missing data doesn't cause errors."""
        # Empty GitHub payload
        fields = extract_filter_fields("github", "issues", {"issue": {}})

        # Should have action but other fields may be None/empty
        assert "action" in fields

    def test_filter_fields_single_assignee(self):
        """Test single assignee (not a list) is handled correctly."""
        payload = {
            "object_attributes": {"assignee_id": 51, "state": "opened"},
            "user": {"username": "testuser"},
            "assignee": {"username": "single_assignee"},
        }

        fields = extract_filter_fields("gitlab", "Issue Hook", payload)

        # Should be a single string, not a list
        assert fields["assignee"] == "single_assignee"


class TestFilterMatching:
    """Test that filter matching works as expected with FlowTriggerService logic."""

    def test_label_filter_matching(self):
        """Test that label filters would match correctly."""
        # Extract fields from GitHub issue with "bug" label
        fields = extract_filter_fields("github", "issues", GITHUB_ISSUE_OPENED)

        # Simulate trigger_config: {"labels": ["bug"]}
        trigger_config_labels = ["bug"]
        actual_labels = fields.get("labels", [])

        # Check if any trigger label is in actual labels
        matches = any(label in actual_labels for label in trigger_config_labels)
        assert matches is True

    def test_label_filter_no_match(self):
        """Test that label filters correctly don't match when label is absent."""
        fields = extract_filter_fields("github", "issues", GITHUB_ISSUE_OPENED)

        # Simulate trigger_config: {"labels": ["feature"]}
        trigger_config_labels = ["feature"]
        actual_labels = fields.get("labels", [])

        matches = any(label in actual_labels for label in trigger_config_labels)
        assert matches is False

    def test_author_filter_matching(self):
        """Test that author filters would match correctly."""
        fields = extract_filter_fields("github", "issues", GITHUB_ISSUE_OPENED)

        # Simulate trigger_config: {"author": "octocat"}
        trigger_author = "octocat"
        actual_author = fields.get("author")

        assert actual_author == trigger_author

    def test_assignee_filter_matching_list(self):
        """Test that assignee filters work with list of assignees."""
        fields = extract_filter_fields("github", "issues", GITHUB_ISSUE_OPENED)

        # Simulate trigger_config: {"assignee": "octocat"}
        trigger_assignee = "octocat"
        actual_assignees = fields.get("assignee", [])

        # Check if trigger assignee is in the list
        matches = trigger_assignee in actual_assignees
        assert matches is True


@pytest.mark.parametrize(
    "tracker_type,event_type,payload,expected_normalized,expected_fields",
    [
        # GitLab test cases
        (
            "gitlab",
            "Issue Hook",
            GITLAB_ISSUE_OPENED,
            "issue_opened",
            {"author": "root", "state": "opened", "action": "open"},
        ),
        (
            "gitlab",
            "Merge Request Hook",
            {},
            "merge_request_opened",
            {},
        ),
        # GitHub test cases
        (
            "github",
            "issues",
            GITHUB_ISSUE_OPENED,
            "issue_opened",
            {"author": "octocat", "state": "open", "action": "opened"},
        ),
        (
            "github",
            "pull_request",
            {"action": "opened"},
            "pull_request_opened",
            {"action": "opened"},
        ),
        # Jira test cases
        (
            "jira",
            "jira:issue_created",
            JIRA_ISSUE_CREATED,
            "issue_opened",
            {"priority": "Medium", "state": "To Do", "issue_type": "Task"},
        ),
    ],
)
def test_end_to_end_normalization_and_extraction(
    tracker_type, event_type, payload, expected_normalized, expected_fields
):
    """Test complete normalization and extraction flow for various trackers."""
    # Test normalization
    normalized = normalize_event_type(tracker_type, event_type, payload)
    assert normalized == expected_normalized

    # Test extraction
    fields = extract_filter_fields(tracker_type, event_type, payload)

    # Check expected fields are present and match
    for key, value in expected_fields.items():
        assert key in fields
        assert fields[key] == value


class TestUUIDSerialization:
    """Test UUID serialization for JSON storage."""

    def test_serialize_uuids_in_dict(self):
        """Test that UUIDs in dictionaries are converted to strings."""
        from uuid import UUID
        from preloop.sync.tasks import serialize_uuids

        test_uuid = UUID("9607c913-df61-4a24-9179-b6e83893c501")
        data = {"tracker_id": test_uuid, "name": "test"}

        serialized = serialize_uuids(data)

        assert serialized["tracker_id"] == "9607c913-df61-4a24-9179-b6e83893c501"
        assert serialized["name"] == "test"
        assert isinstance(serialized["tracker_id"], str)

    def test_serialize_uuids_in_nested_dict(self):
        """Test that UUIDs in nested structures are converted to strings."""
        from uuid import UUID
        from preloop.sync.tasks import serialize_uuids

        test_uuid1 = UUID("9607c913-df61-4a24-9179-b6e83893c501")
        test_uuid2 = UUID("f3dd00c0-7316-411d-aea7-2fee793b5c08")

        data = {
            "tracker_id": test_uuid1,
            "organization_id": test_uuid2,
            "nested": {"another_uuid": test_uuid1, "value": 42},
            "list": [test_uuid2, "string", 123],
        }

        serialized = serialize_uuids(data)

        assert serialized["tracker_id"] == "9607c913-df61-4a24-9179-b6e83893c501"
        assert serialized["organization_id"] == "f3dd00c0-7316-411d-aea7-2fee793b5c08"
        assert (
            serialized["nested"]["another_uuid"]
            == "9607c913-df61-4a24-9179-b6e83893c501"
        )
        assert serialized["nested"]["value"] == 42
        assert serialized["list"][0] == "f3dd00c0-7316-411d-aea7-2fee793b5c08"
        assert serialized["list"][1] == "string"
        assert serialized["list"][2] == 123

    def test_serialize_uuids_preserves_non_uuid_data(self):
        """Test that non-UUID data is preserved unchanged."""
        from preloop.sync.tasks import serialize_uuids

        data = {
            "string": "test",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"key": "value"},
        }

        serialized = serialize_uuids(data)

        assert serialized == data
