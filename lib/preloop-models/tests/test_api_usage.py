"""Tests for API usage model and CRUD operations."""

from spacemodels.crud import crud_api_usage


def test_log_request(db_session, create_account):
    """Test logging an API request."""
    # Create an account
    account = create_account()

    # Log a request
    usage = crud_api_usage.log_request(
        db_session,
        username=account.username,
        endpoint="/api/v1/issues",
        method="GET",
        status_code=200,
        duration=0.123,
        action_type="list_issues",
    )

    # Verify usage attributes
    assert usage.username == account.username
    assert usage.endpoint == "/api/v1/issues"
    assert usage.method == "GET"
    assert usage.status_code == 200
    assert usage.duration == 0.123
    assert usage.action_type == "list_issues"
    assert usage.timestamp is not None


def test_get_user_usage(db_session, create_account):
    """Test getting API usage for a user."""
    # Create an account
    account = create_account()

    # Log a few requests
    crud_api_usage.log_request(
        db_session,
        username=account.username,
        endpoint="/api/v1/issues",
        method="GET",
        status_code=200,
        duration=0.123,
    )

    crud_api_usage.log_request(
        db_session,
        username=account.username,
        endpoint="/api/v1/issues",
        method="POST",
        status_code=201,
        duration=0.456,
    )

    # Get user usage
    usage_records = crud_api_usage.get_user_usage(
        db_session, username=account.username, days=1
    )

    # Should have 2 records
    assert len(usage_records) == 2
    assert usage_records[0].method == "POST"  # Most recent first
    assert usage_records[1].method == "GET"


def test_get_endpoint_stats(db_session, create_account):
    """Test getting endpoint statistics."""
    # Create an account
    account = create_account()

    # Log requests to different endpoints
    for i in range(3):
        crud_api_usage.log_request(
            db_session,
            username=account.username,
            endpoint="/api/v1/issues",
            method="GET",
            status_code=200,
            duration=0.1 + i * 0.1,
        )

    for i in range(2):
        crud_api_usage.log_request(
            db_session,
            username=account.username,
            endpoint="/api/v1/projects",
            method="GET",
            status_code=200,
            duration=0.2 + i * 0.1,
        )

    # Get endpoint stats
    stats = crud_api_usage.get_endpoint_stats(db_session, days=1)

    # Should have stats for 2 endpoints
    assert len(stats) == 2

    # First endpoint should be /issues (most requests)
    assert stats[0]["endpoint"] == "/api/v1/issues"
    assert stats[0]["request_count"] == 3
    assert 0.1 <= stats[0]["min_duration"] <= 0.3
    assert 0.2 <= stats[0]["avg_duration"] <= 0.3
    assert 0.3 <= stats[0]["max_duration"] <= 0.4

    # Second endpoint should be /projects
    assert stats[1]["endpoint"] == "/api/v1/projects"
    assert stats[1]["request_count"] == 2


def test_get_user_stats(db_session):
    """Test getting user statistics."""
    # Create two accounts with API usage
    crud_api_usage.create(
        db_session,
        obj_in={
            "username": "user1",
            "endpoint": "/api/v1/test",
            "method": "GET",
            "status_code": 200,
            "duration": 0.1,
        },
    )

    crud_api_usage.create(
        db_session,
        obj_in={
            "username": "user2",
            "endpoint": "/api/v1/test",
            "method": "GET",
            "status_code": 200,
            "duration": 0.2,
        },
    )

    # User 1 has more requests
    for _i in range(2):
        crud_api_usage.create(
            db_session,
            obj_in={
                "username": "user1",
                "endpoint": "/api/v1/test",
                "method": "GET",
                "status_code": 200,
                "duration": 0.3,
            },
        )

    # Get user stats
    stats = crud_api_usage.get_user_stats(db_session, days=1, limit=10)

    # Should have stats for 2 users
    assert len(stats) == 2

    # First user should be user1 (most requests)
    assert stats[0]["username"] == "user1"
    assert stats[0]["request_count"] == 3

    # Second user should be user2
    assert stats[1]["username"] == "user2"
    assert stats[1]["request_count"] == 1
