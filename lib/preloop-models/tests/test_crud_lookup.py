"""Tests for the CRUD lookup functions in organization, project, and issue modules."""

import uuid
from sqlalchemy.orm import Session

from spacemodels.crud import crud_organization, crud_project, crud_issue
from spacemodels.models import Account, Organization, Project, Issue, Tracker


def test_organization_get_by_name(db_session: Session):
    """Test the get_by_name function for Organization."""
    # Create test account
    account = Account(
        username="test_user",
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    # Create two trackers
    tracker1 = Tracker(
        name="GitHub Tracker",
        tracker_type="github",
        api_key="test_api_key_1",
        account_id=account.id,
    )
    tracker2 = Tracker(
        name="GitLab Tracker",
        tracker_type="gitlab",
        api_key="test_api_key_2",
        account_id=account.id,
    )
    db_session.add(tracker1)
    db_session.add(tracker2)
    db_session.commit()

    # Create organizations with same name in different trackers
    org1 = Organization(
        name="Test Organization",
        identifier="test-org-1",
        tracker_id=tracker1.id,
    )
    org2 = Organization(
        name="Test Organization",
        identifier="test-org-2",
        tracker_id=tracker2.id,
    )
    db_session.add(org1)
    db_session.add(org2)
    db_session.commit()

    # Test get_by_name without tracker filter
    # Should return the first match found
    org = crud_organization.get_by_name(db_session, name="Test Organization")
    assert org is not None
    assert org.name == "Test Organization"

    # Test get_by_name with tracker1 filter
    org = crud_organization.get_by_name(
        db_session, name="Test Organization", tracker_id=tracker1.id
    )
    assert org is not None
    assert org.name == "Test Organization"
    assert org.tracker_id == tracker1.id
    assert org.identifier == "test-org-1"

    # Test get_by_name with tracker2 filter
    org = crud_organization.get_by_name(
        db_session, name="Test Organization", tracker_id=tracker2.id
    )
    assert org is not None
    assert org.name == "Test Organization"
    assert org.tracker_id == tracker2.id
    assert org.identifier == "test-org-2"

    # Test get_by_name with non-existent name
    org = crud_organization.get_by_name(db_session, name="Non-existent Organization")
    assert org is None

    # Test get_by_name with non-existent tracker
    org = crud_organization.get_by_name(
        db_session, name="Test Organization", tracker_id=str(uuid.uuid4())
    )
    assert org is None


def test_project_get_by_name(db_session: Session):
    """Test the get_by_name function for Project."""
    # Create test account
    account = Account(
        username="test_user_2",
        email="test2@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    # Create a tracker
    tracker = Tracker(
        name="Test Tracker",
        tracker_type="github",
        api_key="test_api_key",
        account_id=account.id,
    )
    db_session.add(tracker)
    db_session.commit()

    # Create two organizations
    org1 = Organization(
        name="Org One",
        identifier="org-one",
        tracker_id=tracker.id,
    )
    org2 = Organization(
        name="Org Two",
        identifier="org-two",
        tracker_id=tracker.id,
    )
    db_session.add(org1)
    db_session.add(org2)
    db_session.commit()

    # Create projects with same name in different organizations
    project1 = Project(
        name="Test Project",
        identifier="test-project-1",
        organization_id=org1.id,
    )
    project2 = Project(
        name="Test Project",
        identifier="test-project-2",
        organization_id=org2.id,
    )
    db_session.add(project1)
    db_session.add(project2)
    db_session.commit()

    # Test get_by_name without filters
    # Should return the first match found
    project = crud_project.get_by_name(db_session, name="Test Project")
    assert project is not None
    assert project.name == "Test Project"

    # Test get_by_name with organization filter
    project = crud_project.get_by_name(
        db_session, name="Test Project", organization_id=org1.id
    )
    assert project is not None
    assert project.name == "Test Project"
    assert project.organization_id == org1.id
    assert project.identifier == "test-project-1"

    # Test get_by_name with tracker filter - should still work through organization's tracker
    project = crud_project.get_by_name(
        db_session, name="Test Project", tracker_id=tracker.id
    )
    assert project is not None
    assert project.name == "Test Project"

    # Test get_by_name with both organization and tracker filters
    project = crud_project.get_by_name(
        db_session, name="Test Project", organization_id=org2.id, tracker_id=tracker.id
    )
    assert project is not None
    assert project.name == "Test Project"
    assert project.organization_id == org2.id
    assert project.identifier == "test-project-2"

    # Test get_by_name with non-existent name
    project = crud_project.get_by_name(db_session, name="Non-existent Project")
    assert project is None

    # Test get_by_name with non-existent organization
    project = crud_project.get_by_name(
        db_session, name="Test Project", organization_id=str(uuid.uuid4())
    )
    assert project is None


def test_issue_get_by_title(db_session: Session):
    """Test the get_by_title function for Issue."""
    # Create test account
    account = Account(
        username="test_user_3",
        email="test3@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    # Create a tracker
    tracker = Tracker(
        name="Test Tracker for Issues",
        tracker_type="github",
        api_key="test_api_key_issues",
        account_id=account.id,
    )
    db_session.add(tracker)
    db_session.commit()

    # Create an organization
    org = Organization(
        name="Issue Org",
        identifier="issue-org",
        tracker_id=tracker.id,
    )
    db_session.add(org)
    db_session.commit()

    # Create two projects
    project1 = Project(
        name="Issue Project 1",
        identifier="issue-project-1",
        organization_id=org.id,
    )
    project2 = Project(
        name="Issue Project 2",
        identifier="issue-project-2",
        organization_id=org.id,
    )
    db_session.add(project1)
    db_session.add(project2)
    db_session.commit()

    # Create issues with same title in different projects
    issue1 = Issue(
        title="Test Issue",
        description="Description for test issue 1",
        status="open",
        issue_type="bug",
        external_id="ext-1",
        project_id=project1.id,
        tracker_id=tracker.id,
    )
    issue2 = Issue(
        title="Test Issue",
        description="Description for test issue 2",
        status="open",
        issue_type="feature",
        external_id="ext-2",
        project_id=project2.id,
        tracker_id=tracker.id,
    )
    db_session.add(issue1)
    db_session.add(issue2)
    db_session.commit()

    # Test get_by_title without filters
    # Should return the first match found
    issue = crud_issue.get_by_title(db_session, title="Test Issue")
    assert issue is not None
    assert issue.title == "Test Issue"

    # Test get_by_title with project filter
    issue = crud_issue.get_by_title(
        db_session, title="Test Issue", project_id=project1.id
    )
    assert issue is not None
    assert issue.title == "Test Issue"
    assert issue.project_id == project1.id
    assert issue.external_id == "ext-1"

    # Test get_by_title with organization filter
    issue = crud_issue.get_by_title(
        db_session, title="Test Issue", organization_id=org.id
    )
    assert issue is not None
    assert issue.title == "Test Issue"
    # Issues don't have organization_id directly - verify through project relationship
    project = db_session.query(Project).filter(Project.id == issue.project_id).first()
    assert project.organization_id == org.id

    # Test get_by_title with tracker filter
    issue = crud_issue.get_by_title(
        db_session, title="Test Issue", tracker_id=tracker.id
    )
    assert issue is not None
    assert issue.title == "Test Issue"
    assert issue.tracker_id == tracker.id

    # Test get_by_title with project, organization, and tracker filters
    issue = crud_issue.get_by_title(
        db_session,
        title="Test Issue",
        project_id=project2.id,
        organization_id=org.id,
        tracker_id=tracker.id,
    )
    assert issue is not None
    assert issue.title == "Test Issue"
    assert issue.project_id == project2.id
    # Issues don't have organization_id directly - verify through project relationship
    project = db_session.query(Project).filter(Project.id == issue.project_id).first()
    assert project.organization_id == org.id
    assert issue.tracker_id == tracker.id
    assert issue.external_id == "ext-2"

    # Test get_by_title with non-existent title
    issue = crud_issue.get_by_title(db_session, title="Non-existent Issue")
    assert issue is None

    # Test get_by_title with non-existent project
    issue = crud_issue.get_by_title(
        db_session, title="Test Issue", project_id=str(uuid.uuid4())
    )
    assert issue is None
