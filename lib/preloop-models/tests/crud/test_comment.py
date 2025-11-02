"""Tests for Comment CRUD operations."""

from sqlalchemy.orm import Session

from spacemodels.crud.comment import crud_comment


class TestCommentCRUD:
    """Test CRUD operations for Comment."""

    def test_create_with_author(
        self, db_session: Session, create_issue, create_tracker
    ):
        """Test creating a comment with author."""
        tracker = create_tracker()
        issue = create_issue(tracker=tracker)

        comment_data = {
            "issue_id": issue.id,
            "tracker_id": tracker.id,
            "body": "Test comment",
            "external_id": "comment-1",
        }

        comment = crud_comment.create_with_author(
            db_session, obj_in=comment_data, author="test_author"
        )

        assert comment.id is not None
        assert comment.author == "test_author"
        assert comment.body == "Test comment"
        assert comment.issue_id == issue.id

    def test_get_by_external_id(
        self, db_session: Session, create_comment, create_issue, create_tracker
    ):
        """Test getting comment by external ID."""
        tracker = create_tracker()
        issue = create_issue(tracker=tracker)
        comment = create_comment(issue_id=issue.id, external_id="ext-123")

        # Get without filters
        found = crud_comment.get_by_external_id(db_session, external_id="ext-123")
        assert found.id == comment.id

        # Get with issue_id filter
        found = crud_comment.get_by_external_id(
            db_session, external_id="ext-123", issue_id=issue.id
        )
        assert found.id == comment.id

        # Get with wrong issue_id
        found = crud_comment.get_by_external_id(
            db_session, external_id="ext-123", issue_id="wrong-id"
        )
        assert found is None

        # Get with account_id filter
        found = crud_comment.get_by_external_id(
            db_session, external_id="ext-123", account_id=tracker.account_id
        )
        assert found.id == comment.id

        # Get with wrong account_id
        found = crud_comment.get_by_external_id(
            db_session, external_id="ext-123", account_id="wrong-account"
        )
        assert found is None

    def test_get_multi_by_issue(
        self, db_session: Session, create_comment, create_issue, create_tracker
    ):
        """Test getting multiple comments for an issue."""
        tracker = create_tracker()
        issue = create_issue(tracker=tracker)

        # Create multiple comments
        comment1 = create_comment(issue_id=issue.id, body="Comment 1")
        comment2 = create_comment(issue_id=issue.id, body="Comment 2")
        comment3 = create_comment(issue_id=issue.id, body="Comment 3")

        print(comment1)
        print(comment2)
        print(comment3)

        # Get all comments for the issue
        comments = crud_comment.get_multi_by_issue(db_session, issue_id=issue.id)
        assert len(comments) == 3

        # Test pagination
        comments = crud_comment.get_multi_by_issue(
            db_session, issue_id=issue.id, skip=1, limit=1
        )
        assert len(comments) == 1

        # Test with account filter
        comments = crud_comment.get_multi_by_issue(
            db_session, issue_id=issue.id, account_id=tracker.account_id
        )
        assert len(comments) == 3

        # Test with wrong account
        comments = crud_comment.get_multi_by_issue(
            db_session, issue_id=issue.id, account_id="wrong-account"
        )
        assert len(comments) == 0

    def test_get_multi_by_author(
        self,
        db_session: Session,
        create_comment,
        create_issue,
        create_tracker,
        create_user,
    ):
        """Test getting multiple comments by author."""
        # Create users for alice and bob
        alice = create_user(username="alice")
        bob = create_user(username="bob")
        print(alice)
        print(bob)

        tracker = create_tracker()
        issue = create_issue(tracker=tracker)

        # Create comments by different authors
        comment1 = create_comment(issue_id=issue.id, author=alice)
        comment2 = create_comment(issue_id=issue.id, author=alice)
        comment3 = create_comment(issue_id=issue.id, author=bob)

        print(comment1)
        print(comment2)
        print(comment3)

        # Get comments by alice
        comments = crud_comment.get_multi_by_author(db_session, author="alice")
        assert len(comments) == 2

        # Get comments by bob
        comments = crud_comment.get_multi_by_author(db_session, author="bob")
        assert len(comments) == 1

        # Test pagination
        comments = crud_comment.get_multi_by_author(
            db_session, author="alice", skip=1, limit=1
        )
        assert len(comments) == 1

        # Test with account filter
        comments = crud_comment.get_multi_by_author(
            db_session, author="alice", account_id=tracker.account_id
        )
        assert len(comments) == 2

        # Test with wrong account
        comments = crud_comment.get_multi_by_author(
            db_session, author="alice", account_id="wrong-account"
        )
        assert len(comments) == 0
