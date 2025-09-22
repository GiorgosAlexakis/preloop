import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from spacebridge.api.endpoints import comments
from spacebridge.schemas.comment import CommentCreate


@pytest.mark.asyncio
@patch("spacebridge.api.endpoints.comments.get_tracker_client")
async def test_list_issue_comments_success(mock_get_tracker_client):
    """
    Tests the list_issue_comments function for a successful request.
    """
    tracker_client = AsyncMock()
    tracker_client.get_issue.return_value = MagicMock()
    tracker_client.get_comments.return_value = []
    mock_get_tracker_client.return_value = tracker_client

    db_session = MagicMock()
    current_user = MagicMock()

    result = await comments.list_issue_comments(
        "123",
        "org",
        "proj",
        limit=10,
        offset=0,
        db=db_session,
        current_user=current_user,
    )
    assert result.total == 0


@pytest.mark.asyncio
@patch("spacebridge.api.endpoints.comments.get_tracker_client")
async def test_add_issue_comment_success(mock_get_tracker_client):
    """
    Tests the add_issue_comment function for a successful request.
    """
    tracker_client = AsyncMock()
    tracker_client.get_issue.return_value = MagicMock()
    tracker_client.add_comment.return_value = MagicMock(
        id="456",
        author="test",
        body="Test comment",
        created_at="2025-09-22T00:19:39.601Z",
        updated_at="2025-09-22T00:19:39.601Z",
        meta_data={},
    )
    mock_get_tracker_client.return_value = tracker_client

    db_session = MagicMock()
    current_user = MagicMock()
    comment_create = CommentCreate(body="Test comment")

    result = await comments.add_issue_comment(
        "123", comment_create, "org", "proj", db=db_session, current_user=current_user
    )
    assert result.id == "456"


@pytest.mark.asyncio
@pytest.mark.asyncio
@patch("spacebridge.api.endpoints.comments.crud_comment.get_multi_by_issue")
async def test_search_comments_by_issue_id(mock_get_multi_by_issue):
    """
    Tests the search_comments function when searching by issue_id.
    """
    mock_get_multi_by_issue.return_value = []
    db_session = MagicMock()
    current_user = MagicMock()

    with patch(
        "spacebridge.api.endpoints.comments.crud_tracker.get_for_account",
        return_value=[MagicMock()],
    ):
        result = await comments.search_comments(
            db=db_session,
            current_user=current_user,
            issue_id="123",
            search_type="full_text",
            query="",
            author=None,
        )
        assert result.total == 0
        mock_get_multi_by_issue.assert_called_once()


@pytest.mark.asyncio
@patch("spacebridge.api.endpoints.comments.crud_comment.get_multi_by_author")
async def test_search_comments_by_author(mock_get_multi_by_author):
    """
    Tests the search_comments function when searching by author.
    """
    mock_get_multi_by_author.return_value = []
    db_session = MagicMock()
    current_user = MagicMock()

    with patch(
        "spacebridge.api.endpoints.comments.crud_tracker.get_for_account",
        return_value=[MagicMock()],
    ):
        result = await comments.search_comments(
            db=db_session,
            current_user=current_user,
            author="test",
            search_type="full_text",
            query="",
            issue_id=None,
        )
        assert result.total == 0
        mock_get_multi_by_author.assert_called_once()
