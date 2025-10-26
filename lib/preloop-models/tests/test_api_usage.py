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
    # Create an account with a unique identifier
    account = create_account()

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
            username=account.username,
            endpoint=test_endpoints[0],  # First unique endpoint
            method="GET",
            status_code=200,
            duration=0.1 + i * 0.1,
        )

    for i in range(2):
        crud_api_usage.log_request(
            db_session,
            username=account.username,
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


def test_get_user_stats(db_session, create_account):  # Added create_account fixture
    """Test getting user statistics."""
    # Create the accounts first to satisfy foreign key constraint
    account1 = create_account(
        username="user1_test_api_usage"
    )  # Make usernames more unique
    account2 = create_account(
        username="user2_test_api_usage"
    )  # Make usernames more unique

    test_usernames = {account1.username, account2.username}

    # Log API usage for the created accounts
    crud_api_usage.create(
        db_session,
        obj_in={
            "username": account1.username,  # Use username from created account
            "endpoint": "/api/v1/test",
            "method": "GET",
            "status_code": 200,
            "duration": 0.1,
        },
    )

    crud_api_usage.create(
        db_session,
        obj_in={
            "username": account2.username,  # Use username from created account
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
                "username": account1.username,  # Use username from created account
                "endpoint": "/api/v1/test",
                "method": "GET",
                "status_code": 200,
                "duration": 0.3,
            },
        )

    # Get user stats
    all_stats = crud_api_usage.get_user_stats(db_session, days=1, limit=10)

    # Filter stats to only include those relevant to this test
    stats = [s for s in all_stats if s["username"] in test_usernames]

    # Should have stats for 2 users relevant to this test
    assert len(stats) == 2

    # Sort stats by username to ensure consistent order for assertions
    stats.sort(key=lambda x: x["username"])

    # First user should be user1 (alphabetically, or by request count if sorted differently)
    # Assuming user1_test_api_usage comes before user2_test_api_usage alphabetically
    assert stats[0]["username"] == account1.username
    assert stats[0]["request_count"] == 3

    # Second user should be user2
    assert stats[1]["username"] == account2.username
    assert stats[1]["request_count"] == 1
