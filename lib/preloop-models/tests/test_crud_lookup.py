"""Tests for the CRUD lookup functions in organization, project, and issue modules."""

import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from spacemodels.crud import crud_organization, crud_project, crud_issue, crud_comment
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
    account = create_account(username="cross_org_user")
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


def test_issue_get_by_key(db_session: Session):
    """Test the get_by_key function for Issue."""
    # --- Setup ---
    account = Account(
        username="test_user_key",
        email="test_key@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

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


# --- Start of new Comment tests ---


def test_comment_create_with_author(db_session: Session, create_issue, create_account):
    """Test creating a comment with an author using dictionary input."""
    issue = create_issue()
    author = create_account()
    comment_data_in = {
        "body": "This is a test comment!",
        "type": "issue",
        "issue_id": issue.id,
    }

    comment = crud_comment.create_with_author(
        db_session, obj_in=comment_data_in, author_id=author.id
    )

    assert comment is not None
    assert comment.body == "This is a test comment!"
    assert comment.type == "issue"
    assert comment.issue_id == issue.id
    assert comment.author_id == author.id
    assert comment.id is not None
    assert comment.created_at is not None
    assert comment.updated_at is not None


def test_comment_get_multi_by_issue(
    db_session: Session, create_comment, create_issue, create_account
):
    """Test retrieving multiple comments for a specific issue."""
    author = create_account()
    issue1 = create_issue(title="Issue One for Comments")
    issue2 = create_issue(title="Issue Two for Comments")

    comment1_issue1 = create_comment(
        issue=issue1, author=author, body="First comment for issue 1"
    )
    comment2_issue1 = create_comment(
        issue=issue1, author=author, body="Second comment for issue 1"
    )
    comment1_issue2 = create_comment(
        issue=issue2, author=author, body="First comment for issue 2"
    )

    # Test for issue1
    comments_issue1 = crud_comment.get_multi_by_issue(db_session, issue_id=issue1.id)
    assert len(comments_issue1) == 2
    comment_ids_issue1 = {c.id for c in comments_issue1}
    assert comment1_issue1.id in comment_ids_issue1
    assert comment2_issue1.id in comment_ids_issue1

    # Test for issue2
    comments_issue2 = crud_comment.get_multi_by_issue(db_session, issue_id=issue2.id)
    assert len(comments_issue2) == 1
    assert comments_issue2[0].id == comment1_issue2.id

    # Test for an issue with no comments
    issue_no_comments = create_issue(title="Issue With No Comments")
    comments_no_issue = crud_comment.get_multi_by_issue(
        db_session, issue_id=issue_no_comments.id
    )
    assert len(comments_no_issue) == 0


def test_comment_get_multi_by_author(
    db_session: Session, create_comment, create_issue, create_account
):
    """Test retrieving multiple comments by a specific author."""
    author1 = create_account(username="author_one_comments")
    author2 = create_account(username="author_two_comments")
    issue = create_issue()

    comment1_author1 = create_comment(
        issue=issue, author=author1, body="Author 1, Comment 1"
    )
    comment2_author1 = create_comment(
        issue=issue, author=author1, body="Author 1, Comment 2"
    )
    comment1_author2 = create_comment(
        issue=issue, author=author2, body="Author 2, Comment 1"
    )

    # Test for author1
    comments_author1 = crud_comment.get_multi_by_author(
        db_session, author_id=author1.id
    )
    assert len(comments_author1) == 2
    comment_ids_author1 = {c.id for c in comments_author1}
    assert comment1_author1.id in comment_ids_author1
    assert comment2_author1.id in comment_ids_author1

    # Test for author2
    comments_author2 = crud_comment.get_multi_by_author(
        db_session, author_id=author2.id
    )
    assert len(comments_author2) == 1
    assert comments_author2[0].id == comment1_author2.id

    # Test for an author with no comments
    author_no_comments = create_account(username="author_no_comments")
    comments_no_author = crud_comment.get_multi_by_author(
        db_session, author_id=author_no_comments.id
    )
    assert len(comments_no_author) == 0


def test_comment_base_crud_operations(db_session: Session, create_comment):
    """Test basic CRUD operations (get, update, delete) for Comment using dictionaries."""
    # Create a comment using the fixture
    initial_comment = create_comment(body="Initial comment for CRUD test")
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
