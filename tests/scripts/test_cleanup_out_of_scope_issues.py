"""
Tests for the cleanup_out_of_scope_issues maintenance script.
"""

import pytest
from unittest.mock import MagicMock

from spacebridge.scripts.cleanup_out_of_scope_issues import (
    get_out_of_scope_issues,
    delete_out_of_scope_issues,
)
from spacemodels.models.issue import Issue
from spacemodels.models.project import Project
from spacemodels.models.organization import Organization
from spacemodels.models.tracker import Tracker
from spacemodels.models.tracker_scope_rule import TrackerScopeRule


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def sample_tracker():
    """Create a sample tracker."""
    tracker = Tracker(
        id="tracker-1",
        name="Test Tracker",
        account_id="account-1",
        is_active=True,
        is_deleted=False,
    )
    return tracker


@pytest.fixture
def sample_organization(sample_tracker):
    """Create a sample organization."""
    org = Organization(
        id="org-1",
        identifier="test-org",
        name="Test Organization",
        tracker_id=sample_tracker.id,
        tracker=sample_tracker,
    )
    return org


@pytest.fixture
def sample_project(sample_organization):
    """Create a sample project."""
    project = Project(
        id="project-1",
        identifier="test-project",
        name="Test Project",
        organization_id=sample_organization.id,
        organization=sample_organization,
    )
    return project


@pytest.fixture
def sample_issue(sample_project):
    """Create a sample issue."""
    issue = Issue(
        id="issue-1",
        key="TEST-1",
        title="Test Issue",
        project_id=sample_project.id,
        project=sample_project,
    )
    return issue


def test_get_out_of_scope_issues_no_rules(
    mock_db_session, sample_issue, sample_organization
):
    """Test that issues with no scope rules are considered out of scope."""
    # Mock the query chain
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.side_effect = [
        [sample_issue],  # First call returns issues
        [],  # Second call returns no scope rules
    ]

    result = get_out_of_scope_issues(mock_db_session)

    # Issue should be out of scope (no org inclusions)
    assert len(result) == 1
    assert result[0] == sample_issue


def test_get_out_of_scope_issues_excluded_project(
    mock_db_session, sample_issue, sample_project
):
    """Test that excluded projects are identified as out of scope."""
    # Create scope rules
    rules = [
        TrackerScopeRule(
            scope_type="ORGANIZATION",
            rule_type="INCLUDE",
            identifier=sample_project.organization.identifier,
        ),
        TrackerScopeRule(
            scope_type="PROJECT",
            rule_type="EXCLUDE",
            identifier=sample_project.identifier,
        ),
    ]

    # Mock the query chain
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.side_effect = [
        [sample_issue],  # First call returns issues
        rules,  # Second call returns scope rules
    ]

    result = get_out_of_scope_issues(mock_db_session)

    # Issue should be out of scope (project excluded)
    assert len(result) == 1
    assert result[0] == sample_issue


def test_get_out_of_scope_issues_in_scope(
    mock_db_session, sample_issue, sample_project
):
    """Test that in-scope issues are not returned."""
    # Create scope rules that include the project
    rules = [
        TrackerScopeRule(
            scope_type="ORGANIZATION",
            rule_type="INCLUDE",
            identifier=sample_project.organization.identifier,
        ),
    ]

    # Mock the query chain
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.side_effect = [
        [sample_issue],  # First call returns issues
        rules,  # Second call returns scope rules
    ]

    result = get_out_of_scope_issues(mock_db_session)

    # Issue should be in scope
    assert len(result) == 0


def test_delete_out_of_scope_issues(mock_db_session):
    """Test deletion of out-of-scope issues."""
    issues = [
        Issue(id="issue-1", key="TEST-1", title="Test Issue 1"),
        Issue(id="issue-2", key="TEST-2", title="Test Issue 2"),
    ]

    # Mock the query chain for counting
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.side_effect = [5, 10]  # 5 comments, 10 embeddings
    mock_query.delete.return_value = None

    result = delete_out_of_scope_issues(mock_db_session, issues)

    # Verify counts
    assert result["issues"] == 2
    assert result["comments"] == 5
    assert result["embeddings"] == 10

    # Verify delete was called
    assert mock_query.delete.call_count == 3  # comments, embeddings, issues

    # Verify commit was called
    mock_db_session.commit.assert_called_once()


def test_delete_out_of_scope_issues_empty_list(mock_db_session):
    """Test deletion with empty issue list."""
    issues = []

    # Mock the query chain
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 0

    result = delete_out_of_scope_issues(mock_db_session, issues)

    # Verify counts are all zero
    assert result["issues"] == 0
    assert result["comments"] == 0
    assert result["embeddings"] == 0
