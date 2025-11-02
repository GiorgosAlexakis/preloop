"""Tests for API usage model edge cases."""

from spacemodels.crud import crud_api_usage


def test_log_request_nonexistent_user(db_session):
    """Test logging an API request with non-existent user."""
    # Log a request with non-existent user
    usage = crud_api_usage.log_request(
        db_session,
        username="nonexistent_user",
        endpoint="/api/v1/issues",
        method="GET",
        status_code=200,
        duration=0.123,
        action_type="list_issues",
        create_user_if_missing=False,
    )

    # Should log the request with user_id=None
    assert usage is not None
    assert usage.user_id is None


def test_log_request_anonymous(db_session):
    """Test logging an API request with no user."""
    # Log a request with no user
    usage = crud_api_usage.log_request(
        db_session,
        username=None,
        endpoint="/api/v1/issues",
        method="GET",
        status_code=200,
        duration=0.123,
        action_type="list_issues",
    )

    # Verify usage attributes
    assert usage.user_id is None
    assert usage.endpoint == "/api/v1/issues"
    assert usage.method == "GET"
    assert usage.status_code == 200
    assert usage.duration == 0.123
    assert usage.action_type == "list_issues"
    assert usage.timestamp is not None


def test_create_user_if_missing(db_session):
    """Test creating a user if missing."""
    # Note: create_user_if_missing is not supported in the new architecture
    # This test now verifies that the request is logged with user_id=None
    # when the user doesn't exist
    usage = crud_api_usage.log_request(
        db_session,
        username="new_test_user",
        endpoint="/api/v1/issues",
        method="GET",
        status_code=200,
        duration=0.123,
        action_type="list_issues",
        create_user_if_missing=True,
    )

    # Should log the request with user_id=None (user creation is not supported)
    assert usage is not None
    assert usage.user_id is None
    assert usage.endpoint == "/api/v1/issues"
