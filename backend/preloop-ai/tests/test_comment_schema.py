"""Tests for comment Pydantic schemas."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from preloop_ai.schemas.comment import (
    CommentBase,
    CommentCreate,
    CommentList,
    CommentResponse,
    CommentSearchResults,
)


class TestCommentBase:
    """Test CommentBase schema."""

    def test_create_with_required_fields(self):
        """Test creating CommentBase with required fields only."""
        comment = CommentBase(body="This is a test comment")

        assert comment.body == "This is a test comment"
        assert comment.meta_data is None

    def test_create_with_all_fields(self):
        """Test creating CommentBase with all fields."""
        metadata = {"author_id": "user123", "is_internal": True}
        comment = CommentBase(body="Test comment with metadata", meta_data=metadata)

        assert comment.body == "Test comment with metadata"
        assert comment.meta_data == metadata

    def test_body_required(self):
        """Test that body field is required."""
        with pytest.raises(ValidationError) as exc_info:
            CommentBase()

        errors = exc_info.value.errors()
        assert any(error["loc"][0] == "body" for error in errors)


class TestCommentCreate:
    """Test CommentCreate schema."""

    def test_inherits_from_base(self):
        """Test that CommentCreate inherits from CommentBase."""
        comment = CommentCreate(body="Creating a new comment")

        assert isinstance(comment, CommentBase)
        assert comment.body == "Creating a new comment"

    def test_create_with_metadata(self):
        """Test creating with metadata."""
        metadata = {"priority": "high", "tags": ["bug", "urgent"]}
        comment = CommentCreate(body="Bug report comment", meta_data=metadata)

        assert comment.body == "Bug report comment"
        assert comment.meta_data == metadata


class TestCommentResponse:
    """Test CommentResponse schema."""

    def test_create_with_required_fields(self):
        """Test creating CommentResponse with required fields."""
        comment = CommentResponse(
            id="comment-123",
            issue_id="issue-456",
            body="Response comment",
            created_at="2025-01-15T10:00:00Z",
        )

        assert comment.id == "comment-123"
        assert comment.issue_id == "issue-456"
        assert comment.body == "Response comment"
        assert comment.created_at == "2025-01-15T10:00:00Z"
        assert comment.author is None
        assert comment.updated_at is None
        assert comment.score is None

    def test_create_with_all_fields(self):
        """Test creating CommentResponse with all fields."""
        metadata = {"source": "webhook"}
        comment = CommentResponse(
            id="comment-789",
            issue_id="issue-101",
            body="Full comment response",
            author="john_doe",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T11:00:00Z",
            meta_data=metadata,
            score=0.95,
        )

        assert comment.id == "comment-789"
        assert comment.issue_id == "issue-101"
        assert comment.body == "Full comment response"
        assert comment.author == "john_doe"
        assert comment.created_at == "2025-01-15T10:00:00Z"
        assert comment.updated_at == "2025-01-15T11:00:00Z"
        assert comment.meta_data == metadata
        assert comment.score == 0.95

    def test_datetime_field_validator_with_datetime_object(self):
        """Test datetime validator converts datetime to ISO string."""
        now = datetime.now()
        comment = CommentResponse(
            id="comment-123",
            issue_id="issue-456",
            body="Test",
            created_at=now,
            updated_at=now,
        )

        assert comment.created_at == now.isoformat()
        assert comment.updated_at == now.isoformat()

    def test_datetime_field_validator_with_string(self):
        """Test datetime validator accepts string."""
        iso_string = "2025-01-15T10:00:00Z"
        comment = CommentResponse(
            id="comment-123",
            issue_id="issue-456",
            body="Test",
            created_at=iso_string,
            updated_at=iso_string,
        )

        assert comment.created_at == iso_string
        assert comment.updated_at == iso_string

    def test_datetime_field_validator_with_none(self):
        """Test datetime validator handles None for optional fields."""
        comment = CommentResponse(
            id="comment-123",
            issue_id="issue-456",
            body="Test",
            created_at="2025-01-15T10:00:00Z",
            updated_at=None,
        )

        assert comment.updated_at is None

    def test_datetime_field_validator_rejects_invalid_type(self):
        """Test datetime validator rejects invalid types."""
        with pytest.raises((ValidationError, TypeError)) as exc_info:
            CommentResponse(
                id="comment-123",
                issue_id="issue-456",
                body="Test",
                created_at=12345,  # Invalid: integer
            )

        # Validator raises TypeError for invalid types
        if isinstance(exc_info.value, TypeError):
            assert "must be a datetime object or a string" in str(exc_info.value)
        else:
            # Or Pydantic ValidationError
            errors = exc_info.value.errors()
            assert len(errors) > 0

    def test_from_attributes_config(self):
        """Test that from_attributes is enabled."""
        assert CommentResponse.model_config.get("from_attributes") is True


class TestCommentList:
    """Test CommentList schema."""

    def test_create_comment_list(self):
        """Test creating CommentList with pagination."""
        items = [
            CommentResponse(
                id="comment-1",
                issue_id="issue-1",
                body="First comment",
                created_at="2025-01-15T10:00:00Z",
            ),
            CommentResponse(
                id="comment-2",
                issue_id="issue-1",
                body="Second comment",
                created_at="2025-01-15T11:00:00Z",
            ),
        ]

        comment_list = CommentList(items=items, total=10, limit=2, offset=0)

        assert len(comment_list.items) == 2
        assert comment_list.total == 10
        assert comment_list.limit == 2
        assert comment_list.offset == 0

    def test_empty_comment_list(self):
        """Test creating empty CommentList."""
        comment_list = CommentList(items=[], total=0, limit=10, offset=0)

        assert len(comment_list.items) == 0
        assert comment_list.total == 0


class TestCommentSearchResults:
    """Test CommentSearchResults schema."""

    def test_create_search_results(self):
        """Test creating CommentSearchResults."""
        items = [
            CommentResponse(
                id="comment-1",
                issue_id="issue-1",
                body="Bug found in login",
                created_at="2025-01-15T10:00:00Z",
                score=0.95,
            ),
            CommentResponse(
                id="comment-2",
                issue_id="issue-2",
                body="Login bug fixed",
                created_at="2025-01-15T11:00:00Z",
                score=0.87,
            ),
        ]

        results = CommentSearchResults(items=items, total=2, query="login bug")

        assert len(results.items) == 2
        assert results.total == 2
        assert results.query == "login bug"
        assert results.items[0].score == 0.95
        assert results.items[1].score == 0.87

    def test_empty_search_results(self):
        """Test creating empty search results."""
        results = CommentSearchResults(items=[], total=0, query="nonexistent")

        assert len(results.items) == 0
        assert results.total == 0
        assert results.query == "nonexistent"

    def test_required_fields(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            CommentSearchResults()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}

        required_fields = {"items", "total", "query"}
        assert required_fields == error_fields
