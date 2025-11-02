"""Tests for API usage model and CRUD operations."""

from spacemodels.crud import crud_api_usage


def test_log_request(db_session, create_account, create_user):
    """Test logging an API request."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Log a request
    usage = crud_api_usage.log_request(
        db_session,
        username=user.username,
        endpoint="/api/v1/issues",
        method="GET",
        status_code=200,
        duration=0.123,
        action_type="list_issues",
    )

    # Verify usage attributes
    assert usage.user_id == user.id
    assert usage.endpoint == "/api/v1/issues"
    assert usage.method == "GET"
    assert usage.status_code == 200
    assert usage.duration == 0.123
    assert usage.action_type == "list_issues"
    assert usage.timestamp is not None


def test_get_user_usage(db_session, create_account, create_user):
    """Test getting API usage for a user."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Log a few requests
    crud_api_usage.log_request(
        db_session,
        username=user.username,
        endpoint="/api/v1/issues",
        method="GET",
        status_code=200,
        duration=0.123,
    )

    crud_api_usage.log_request(
        db_session,
        username=user.username,
        endpoint="/api/v1/issues",
        method="POST",
        status_code=201,
        duration=0.456,
    )

    # Get user usage
    usage_records = crud_api_usage.get_user_usage(
        db_session, username=user.username, days=1
    )

    # Should have 2 records
    assert len(usage_records) == 2
    assert usage_records[0].method == "POST"  # Most recent first
    assert usage_records[1].method == "GET"


def test_get_endpoint_stats(db_session, create_account, create_user):
    """Test getting endpoint statistics."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Use unique endpoints for this test to avoid conflicts with other test runs
    import uuid

    unique_suffix = str(uuid.uuid4())[:8]
    test_endpoints = [
        f"/api/v1/test_endpoint_stats_issues_{unique_suffix}",
        f"/api/v1/test_endpoint_stats_projects_{unique_suffix}",
    ]

    # Log requests to different endpoints
    for i in range(3):
        crud_api_usage.log_request(
            db_session,
            username=user.username,
            endpoint=test_endpoints[0],  # First unique endpoint
            method="GET",
            status_code=200,
            duration=0.1 + i * 0.1,
        )

    for i in range(2):
        crud_api_usage.log_request(
            db_session,
            username=user.username,
            endpoint=test_endpoints[1],  # Second unique endpoint
            method="GET",
            status_code=200,
            duration=0.2 + i * 0.1,
        )

    # Get endpoint stats
    all_stats = crud_api_usage.get_endpoint_stats(db_session, days=1)

    # Filter stats to only include those relevant to this test
    stats = [s for s in all_stats if s["endpoint"] in test_endpoints]

    # Should have stats for 2 endpoints relevant to this test
    assert len(stats) == 2

    # Sort stats by endpoint name to ensure consistent order for assertions
    stats.sort(key=lambda x: x["endpoint"])

    # First endpoint (alphabetically)
    assert stats[0]["endpoint"] == test_endpoints[0]
    assert stats[0]["request_count"] == 3
    assert 0.1 <= stats[0]["min_duration"] <= 0.3
    # Adjust avg_duration check due to potential floating point inaccuracies
    assert 0.19 <= stats[0]["avg_duration"] <= 0.21  # (0.1+0.2+0.3)/3 = 0.2
    assert 0.3 <= stats[0]["max_duration"] <= 0.4

    # Second endpoint (alphabetically)
    assert stats[1]["endpoint"] == test_endpoints[1]
    assert stats[1]["request_count"] == 2
    # (0.2+0.3)/2 = 0.25
    assert 0.24 <= stats[1]["avg_duration"] <= 0.26


def test_get_user_stats(
    db_session, create_account, create_user
):  # Added create_user fixture
    """Test getting user statistics."""
    # Create the accounts and users first to satisfy foreign key constraint
    account1 = create_account()
    user1 = create_user(account=account1)
    account2 = create_account()
    user2 = create_user(account=account2)

    test_usernames = {user1.username, user2.username}

    # Log API usage for the created users
    crud_api_usage.log_request(
        db_session,
        username=user1.username,
        endpoint="/api/v1/test",
        method="GET",
        status_code=200,
        duration=0.1,
    )

    crud_api_usage.log_request(
        db_session,
        username=user2.username,
        endpoint="/api/v1/test",
        method="GET",
        status_code=200,
        duration=0.2,
    )

    # User 1 has more requests
    for _i in range(2):
        crud_api_usage.log_request(
            db_session,
            username=user1.username,
            endpoint="/api/v1/test",
            method="GET",
            status_code=200,
            duration=0.3,
        )

    # Get user stats
    all_stats = crud_api_usage.get_user_stats(db_session, days=1, limit=10)

    # Filter stats to only include those relevant to this test
    stats = [s for s in all_stats if s["username"] in test_usernames]

    # Should have stats for 2 users relevant to this test
    assert len(stats) == 2

    # Create a mapping of username to stats
    stats_by_username = {s["username"]: s for s in stats}

    # Verify user1 has 3 requests
    assert user1.username in stats_by_username
    assert stats_by_username[user1.username]["request_count"] == 3

    # Verify user2 has 1 request
    assert user2.username in stats_by_username
    assert stats_by_username[user2.username]["request_count"] == 1


def test_api_usage_repr(db_session, create_account, create_user):
    """Test the __repr__ method of ApiUsage model."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Log a request
    usage = crud_api_usage.log_request(
        db_session,
        username=user.username,
        endpoint="/api/v1/test",
        method="POST",
        status_code=201,
        duration=0.5,
    )

    # Test repr
    repr_str = repr(usage)
    assert "ApiUsage" in repr_str
    assert "POST" in repr_str
    assert "/api/v1/test" in repr_str
    assert str(user.id) in repr_str


def test_get_user_usage_with_account_id(db_session, create_account, create_user):
    """Test getting API usage for a user with account filter."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Log a request
    crud_api_usage.log_request(
        db_session,
        username=user.username,
        endpoint="/api/v1/test",
        method="GET",
        status_code=200,
        duration=0.1,
    )

    # Get usage with account_id filter
    usage_records = crud_api_usage.get_user_usage(
        db_session, username=user.username, days=1, account_id=account.id
    )

    # Should have 1 record
    assert len(usage_records) == 1


def test_get_endpoint_stats_with_account_id(db_session, create_account, create_user):
    """Test getting endpoint statistics with account filter."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Log requests
    for i in range(2):
        crud_api_usage.log_request(
            db_session,
            username=user.username,
            endpoint="/api/v1/test_with_account",
            method="GET",
            status_code=200,
            duration=0.1 + i * 0.1,
        )

    # Get stats with account_id filter
    stats = crud_api_usage.get_endpoint_stats(db_session, days=1, account_id=account.id)

    # Should have stats (may include other endpoints from other tests)
    assert len(stats) >= 1


def test_get_user_stats_with_account_id(db_session, create_account, create_user):
    """Test getting user statistics with account filter."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Log requests
    for _i in range(2):
        crud_api_usage.log_request(
            db_session,
            username=user.username,
            endpoint="/api/v1/test",
            method="GET",
            status_code=200,
            duration=0.1,
        )

    # Get user stats with account_id filter
    stats = crud_api_usage.get_user_stats(db_session, days=1, account_id=account.id)

    # Should have stats for our user
    matching_stats = [s for s in stats if s["username"] == user.username]
    assert len(matching_stats) >= 1
    assert matching_stats[0]["request_count"] >= 2
