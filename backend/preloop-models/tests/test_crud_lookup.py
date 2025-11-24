"""Tests for the CRUD lookup functions in organization, project, and issue modules."""

import uuid

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from preloop_models.crud import (
    crud_organization,
    crud_project,
    crud_issue,
    crud_comment,
)
from preloop_models.models import Organization, Project, Issue, Tracker


def test_organization_get_by_name(db_session: Session, create_account):
    """Test the get_by_name function for Organization."""
    # Create test account
    account = create_account()

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


def test_project_get_by_name(db_session: Session, create_account):
    """Test the get_by_name function for Project."""
    # Create test account
    account = create_account()

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
    db_session.refresh(project1)
    db_session.refresh(project2)

    # Ensure distinct updated_at timestamps for testing latest match logic
    project1.updated_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    project2.updated_at = datetime.now(timezone.utc)
    db_session.add(project1)
    db_session.add(project2)
    db_session.commit()

    # Test get_by_name without filters
    # Should return the most recently updated match
    project = crud_project.get_by_name(db_session, name="Test Project")
    assert project is not None
    assert project.id == project2.id  # project2 was updated more recently

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


def test_issue_get_by_title(db_session: Session, create_account):
    """Test the get_by_title function for Issue."""
    # Create test account
    account = create_account()

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
        key="TEST-KEY-CRUD-1",
        project_id=project1.id,
        tracker_id=tracker.id,
    )
    issue2 = Issue(
        title="Test Issue",
        description="Description for test issue 2",
        status="open",
        issue_type="feature",
        external_id="ext-2",
        key="TEST-KEY-CRUD-2",
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


def test_project_get_by_slug_or_identifier(
    db_session: Session, create_project, create_organization
):
    """Test the get_by_slug_or_identifier function for Project."""
    org1 = create_organization(identifier="org-slug-test-1")
    org2 = create_organization(identifier="org-slug-test-2")

    # Project with only identifier
    project_id_only = create_project(
        name="ID Only Project", identifier="proj-id-only", organization=org1
    )

    # Project with only slug
    project_slug_only = create_project(
        name="Slug Only Project",
        identifier="proj-slug-only-id",
        slug="proj-slug-only",
        organization=org1,
    )

    # Project with both slug and identifier (different)
    project_both = create_project(
        name="Both Project",
        identifier="proj-both-id",
        slug="proj-both-slug",
        organization=org2,
    )

    # --- Test Lookup by Identifier ---
    # Test finding project with only identifier
    found_proj = crud_project.get_by_slug_or_identifier(
        db_session, slug_or_identifier="proj-id-only", organization_id=org1.id
    )
    assert found_proj is not None
    assert found_proj.id == project_id_only.id
    assert found_proj.identifier == "proj-id-only"
    assert found_proj.slug is None

    # Test finding project with both, using identifier (fallback)
    found_proj = crud_project.get_by_slug_or_identifier(
        db_session, slug_or_identifier="proj-both-id", organization_id=org2.id
    )
    assert found_proj is not None
    assert found_proj.id == project_both.id
    assert found_proj.identifier == "proj-both-id"
    assert found_proj.slug == "proj-both-slug"  # Slug should still be present

    # --- Test Lookup by Slug ---
    # Test finding project with only slug
    found_proj = crud_project.get_by_slug_or_identifier(
        db_session, slug_or_identifier="proj-slug-only", organization_id=org1.id
    )
    assert found_proj is not None
    assert found_proj.id == project_slug_only.id
    assert found_proj.slug == "proj-slug-only"

    # Test finding project with both, using slug (precedence)
    found_proj = crud_project.get_by_slug_or_identifier(
        db_session, slug_or_identifier="proj-both-slug", organization_id=org2.id
    )
    assert found_proj is not None
    assert found_proj.id == project_both.id
    assert found_proj.slug == "proj-both-slug"
    assert found_proj.identifier == "proj-both-id"  # Identifier should still be present

    # --- Test Lookup Failures ---
    # Test non-existent identifier/slug
    found_proj = crud_project.get_by_slug_or_identifier(
        db_session, slug_or_identifier="non-existent", organization_id=org1.id
    )
    assert found_proj is None

    # Test correct identifier/slug but wrong organization
    found_proj = crud_project.get_by_slug_or_identifier(
        db_session, slug_or_identifier="proj-id-only", organization_id=org2.id
    )
    assert found_proj is None
    found_proj = crud_project.get_by_slug_or_identifier(
        db_session, slug_or_identifier="proj-both-slug", organization_id=org1.id
    )
    assert found_proj is None

    # Test lookup without organization_id (should fail if ambiguous, or find first if unique)
    # Create another project with the same slug in a different org to test ambiguity
    create_project(
        name="Ambiguous Slug Project",
        identifier="ambiguous-id",
        slug="proj-slug-only",
        organization=org2,
    )
    # Test lookup without org_id for a unique identifier/slug
    found_proj = crud_project.get_by_slug_or_identifier(
        db_session, slug_or_identifier="proj-id-only"
    )
    assert found_proj is not None
    assert found_proj.id == project_id_only.id

    found_proj = crud_project.get_by_slug_or_identifier(
        db_session, slug_or_identifier="proj-both-slug"
    )
    assert found_proj is not None
    assert found_proj.id == project_both.id


def test_project_get_by_identifier_or_name_across_orgs(
    db_session: Session,
    create_account,
    create_tracker,
    create_organization,
    create_project,
):
    """Test get_by_identifier_or_name_across_orgs returns the most recent project."""
    account = create_account()
    tracker = create_tracker(account=account)
    org1 = create_organization(identifier="cross-org-1", tracker=tracker)
    org2 = create_organization(identifier="cross-org-2", tracker=tracker)

    # --- Setup Projects with potential conflicts and different timestamps ---

    # Project with shared name, older timestamp
    proj_shared_name_org1 = create_project(
        name="Shared Project Name", identifier="spn-id-1", organization=org1
    )
    db_session.commit()
    db_session.refresh(proj_shared_name_org1)
    proj_shared_name_org1.updated_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.add(proj_shared_name_org1)

    # Project with shared name, newer timestamp
    proj_shared_name_org2 = create_project(
        name="Shared Project Name", identifier="spn-id-2", organization=org2
    )
    db_session.commit()
    db_session.refresh(proj_shared_name_org2)
    proj_shared_name_org2.updated_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.add(proj_shared_name_org2)

    # Project with shared identifier, older timestamp
    proj_shared_id_org1 = create_project(
        name="Project SID 1", identifier="shared-project-id", organization=org1
    )
    db_session.commit()
    db_session.refresh(proj_shared_id_org1)
    proj_shared_id_org1.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db_session.add(proj_shared_id_org1)

    # Project with shared identifier, newer timestamp
    proj_shared_id_org2 = create_project(
        name="Project SID 2", identifier="shared-project-id", organization=org2
    )
    db_session.commit()
    db_session.refresh(proj_shared_id_org2)
    proj_shared_id_org2.updated_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    db_session.add(proj_shared_id_org2)

    # Unique project
    proj_unique = create_project(
        name="Unique Proj", identifier="unique-id", organization=org1
    )

    db_session.commit()

    # --- Test Lookups ---

    # Test lookup by shared name - should return the newer one (org2)
    found = crud_project.get_by_identifier_or_name_across_orgs(
        db_session, identifier_or_name="Shared Project Name"
    )
    assert found is not None
    assert found.id == proj_shared_name_org2.id

    # Test lookup by shared identifier - should return the newer one (org2)
    found = crud_project.get_by_identifier_or_name_across_orgs(
        db_session, identifier_or_name="shared-project-id"
    )
    assert found is not None
    assert found.id == proj_shared_id_org2.id

    # Test lookup by unique name
    found = crud_project.get_by_identifier_or_name_across_orgs(
        db_session, identifier_or_name="Unique Proj"
    )
    assert found is not None
    assert found.id == proj_unique.id

    # Test lookup by unique identifier
    found = crud_project.get_by_identifier_or_name_across_orgs(
        db_session, identifier_or_name="unique-id"
    )
    assert found is not None
    assert found.id == proj_unique.id

    # Test lookup for non-existent name/identifier
    found = crud_project.get_by_identifier_or_name_across_orgs(
        db_session, identifier_or_name="non-existent"
    )
    assert found is None


def test_issue_get_by_key(db_session: Session, create_account):
    """Test the get_by_key function for Issue."""
    # --- Setup ---
    account = create_account()

    tracker = Tracker(
        name="Test Tracker for Issue Keys",
        tracker_type="github",
        api_key="test_api_key_issue_keys",
        account_id=account.id,
    )
    db_session.add(tracker)
    db_session.commit()

    org = Organization(
        name="Issue Key Org",
        identifier="issue-key-org",
        tracker_id=tracker.id,
    )
    db_session.add(org)
    db_session.commit()

    project1 = Project(
        name="Issue Key Project 1",
        identifier="issue-key-project-1",
        organization_id=org.id,
    )
    project2 = Project(
        name="Issue Key Project 2",
        identifier="issue-key-project-2",
        organization_id=org.id,
    )
    db_session.add_all([project1, project2])
    db_session.commit()

    # --- Create Test Issue ---
    issue_key = "PROJ-42"
    issue1 = Issue(
        title="Issue with Key",
        description="Description for issue with key",
        status="open",
        issue_type="task",
        external_id="ext-key-1",
        project_id=project1.id,
        tracker_id=tracker.id,
        key=issue_key,  # Assign the key
    )
    # Create another issue with the same key in a different project
    issue2 = Issue(
        title="Another Issue with Same Key",
        description="Description for second issue with same key",
        status="closed",
        issue_type="bug",
        external_id="ext-key-2",
        project_id=project2.id,
        tracker_id=tracker.id,
        key=issue_key,  # Assign the same key
    )
    db_session.add_all([issue1, issue2])
    db_session.commit()
    db_session.refresh(issue1)
    db_session.refresh(issue2)

    # --- Test Cases ---

    # 1. Get by key with correct project_id
    found_issue = crud_issue.get_by_key(
        db_session, key=issue_key, project_id=project1.id
    )
    assert found_issue is not None
    assert found_issue.id == issue1.id
    assert found_issue.key == issue_key
    assert found_issue.project_id == project1.id

    # 2. Get by key without project_id (should return one, likely the first/most recent)
    #    Note: Behavior might depend on the exact implementation of get_by_key.
    #    Assuming it might return the most recently updated if ambiguous without project_id.
    #    Let's update issue2 to be more recent for predictability.
    issue2.updated_at = datetime.now(timezone.utc)
    db_session.add(issue2)
    db_session.commit()
    db_session.refresh(issue2)

    found_issue_no_proj = crud_issue.get_by_key(db_session, key=issue_key)
    assert found_issue_no_proj is not None
    # Check if it's one of the issues with that key. If ambiguous, it might return the latest.
    assert found_issue_no_proj.key == issue_key
    assert found_issue_no_proj.id in [issue1.id, issue2.id]
    # If implementation guarantees latest on ambiguity:
    # assert found_issue_no_proj.id == issue2.id

    # 3. Get by key with non-existent key
    not_found_issue = crud_issue.get_by_key(
        db_session, key="NON-EXISTENT-KEY", project_id=project1.id
    )
    assert not_found_issue is None

    # 4. Get by key with correct key but wrong project_id
    wrong_proj_issue = crud_issue.get_by_key(
        db_session,
        key=issue_key,
        project_id=str(uuid.uuid4()),  # Use a random non-existent project ID
    )
    assert wrong_proj_issue is None

    # 5. Get by key with correct key, but specifying the *other* project's ID
    found_issue_proj2 = crud_issue.get_by_key(
        db_session, key=issue_key, project_id=project2.id
    )
    assert found_issue_proj2 is not None
    assert found_issue_proj2.id == issue2.id
    assert found_issue_proj2.key == issue_key
    assert found_issue_proj2.project_id == project2.id


def test_get_comment_by_external_id_simple(
    db_session: Session, create_comment, create_issue, create_user
) -> None:
    """Test retrieving a comment by external_id with a simpler setup."""
    # Setup: Create an author, an issue, and a comment
    author = create_user()
    issue1 = create_issue()
    # Create a second, distinct issue to test the issue_id filter
    issue2 = create_issue()

    comment_external_id = "ext_comment_simple_001"
    comment_body = "This is a simple test comment."
    created_comment = create_comment(
        issue_id=str(issue1.id),
        author=author,
        external_id=comment_external_id,
        body=comment_body,
    )

    # 1. Retrieve by external_id only
    retrieved_by_external_id = crud_comment.get_by_external_id(
        db_session, external_id=comment_external_id
    )
    assert retrieved_by_external_id is not None
    assert retrieved_by_external_id.id == created_comment.id
    assert retrieved_by_external_id.body == comment_body

    # 2. Retrieve by external_id and correct issue_id
    retrieved_by_external_id_and_issue_id = crud_comment.get_by_external_id(
        db_session, external_id=comment_external_id, issue_id=str(issue1.id)
    )
    assert retrieved_by_external_id_and_issue_id is not None
    assert retrieved_by_external_id_and_issue_id.id == created_comment.id

    # 3. Attempt to retrieve with correct external_id but wrong issue_id
    retrieved_with_wrong_issue_id = crud_comment.get_by_external_id(
        db_session,
        external_id=comment_external_id,
        issue_id=str(issue2.id),  # Using issue2.id
    )
    assert retrieved_with_wrong_issue_id is None

    # 4. Attempt to retrieve with a non-existent external_id
    retrieved_non_existent = crud_comment.get_by_external_id(
        db_session, external_id="non_existent_ext_id"
    )
    assert retrieved_non_existent is None


def test_comment_create_with_author(
    db_session: Session, create_issue, create_user, create_comment
):
    """Test creating a comment with a specific author."""
    author = create_user(username="test_author_for_comment")
    issue = create_issue(title="Issue for author comment test")

    comment = create_comment(
        body="This is a test comment!",
        external_id="901",
        issue=issue,
        author=author,
    )

    assert comment is not None
    assert comment.body == "This is a test comment!"
    assert comment.author == author.username
    assert comment.issue_id == issue.id


def test_comment_get_multi_by_issue(db_session: Session, create_issue, create_comment):
    """Test retrieving multiple comments for a specific issue."""
    issue1 = create_issue(title="Issue with multiple comments 1")
    issue2 = create_issue(title="Issue with multiple comments 2")

    # Create comments for issue1
    create_comment(issue_id=str(issue1.id), body="First comment for issue 1")
    create_comment(issue_id=str(issue1.id), body="Second comment for issue 1")

    # Create a comment for issue2
    create_comment(issue_id=str(issue2.id), body="Comment for issue 2")

    # Retrieve comments for issue1
    comments = crud_comment.get_multi_by_issue(db_session, issue_id=str(issue1.id))
    assert len(comments) == 2
    assert {c.body for c in comments} == {
        "First comment for issue 1",
        "Second comment for issue 1",
    }

    # Retrieve comments for issue2
    comments = crud_comment.get_multi_by_issue(db_session, issue_id=str(issue2.id))
    assert len(comments) == 1
    assert comments[0].body == "Comment for issue 2"


def test_comment_get_multi_by_author(
    db_session: Session, create_issue, create_user, create_comment
):
    """Test retrieving multiple comments by a specific author."""
    author1 = create_user(username="author_one_comments")
    author2 = create_user(username="author_two_comments")
    issue = create_issue(title="Issue for author-specific comments")

    # Create comments by author1
    create_comment(issue_id=str(issue.id), author=author1, body="Author 1, Comment 1")
    create_comment(issue_id=str(issue.id), author=author1, body="Author 1, Comment 2")

    # Create a comment by author2
    create_comment(issue_id=str(issue.id), author=author2, body="Author 2, Comment 1")

    # Retrieve comments by author1
    comments = crud_comment.get_multi_by_author(db_session, author=author1.username)
    assert len(comments) == 2
    assert {c.body for c in comments} == {"Author 1, Comment 1", "Author 1, Comment 2"}

    # Retrieve comments by author2
    comments = crud_comment.get_multi_by_author(db_session, author=author2.username)
    assert len(comments) == 1
    assert comments[0].body == "Author 2, Comment 1"


def test_comment_base_crud_operations(db_session: Session, create_comment):
    """Test basic CRUD operations (get, update, delete) for Comment using dictionaries."""
    # Create a comment using the fixture
    initial_comment = create_comment(
        external_id="901", body="Initial comment for CRUD test"
    )
    comment_id = initial_comment.id

    # Test get
    retrieved_comment = crud_comment.get(db_session, id=comment_id)
    assert retrieved_comment is not None
    assert retrieved_comment.id == comment_id
    assert retrieved_comment.body == "Initial comment for CRUD test"

    # Test update
    update_data_dict = {"body": "Updated comment body!"}
    # The CRUDBase.update method expects db_obj (the SQLAlchemy model instance) and obj_in (a dict)
    updated_comment = crud_comment.update(
        db_session, db_obj=retrieved_comment, obj_in=update_data_dict
    )
    assert updated_comment.body == "Updated comment body!"
    assert updated_comment.id == comment_id
    # Verify it's updated in the DB
    re_retrieved_comment = crud_comment.get(db_session, id=comment_id)
    assert re_retrieved_comment.body == "Updated comment body!"

    # Test delete
    deleted_comment = crud_comment.delete(db_session, id=comment_id)
    assert deleted_comment.id == comment_id
    # Verify it's deleted from the DB
    not_found_comment = crud_comment.get(db_session, id=comment_id)
    assert not_found_comment is None


# --- End of new Comment tests ---


# Existing tests after this point, e.g.:
# def test_project_get_by_slug_or_identifier(
# ...
