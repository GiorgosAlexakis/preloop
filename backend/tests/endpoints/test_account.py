"""Tests for account API endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from preloop.models.crud import crud_api_usage, crud_runtime_session


class TestAccountDetails:
    """Test GET and PATCH /api/v1/account/details endpoints."""

    def test_get_account_details_success(self, client: TestClient):
        """Test GET /account/details returns current account info."""
        response = client.get("/api/v1/account/details")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "organization_name" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert isinstance(data["id"], str)
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

    def test_patch_account_details_success(self, client: TestClient):
        """Test PATCH /account/details updates organization name."""
        response = client.patch(
            "/api/v1/account/details",
            json={"organization_name": "Updated Org Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["organization_name"] == "Updated Org Name"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_patch_account_details_partial(self, client: TestClient):
        """Test PATCH /account/details with empty org name (clear)."""
        response = client.patch(
            "/api/v1/account/details",
            json={"organization_name": None},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["organization_name"] is None


def test_get_dashboard_telemetry_aggregates_recent_usage(
    client: TestClient, db_session, test_user
):
    """Dashboard telemetry should aggregate active sessions and recent usage."""
    now = datetime.now(timezone.utc)
    recent_session = crud_runtime_session.upsert_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="managed_agent",
        session_source_id="agent-1",
        session_reference="session-1",
        runtime_principal_type="managed_agent",
        runtime_principal_id="agent-1",
        runtime_principal_name="Agent One",
        started_at=now - timedelta(hours=2),
        last_activity_at=now,
    )
    crud_runtime_session.upsert_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="managed_agent",
        session_source_id="agent-2",
        session_reference="session-2",
        runtime_principal_type="managed_agent",
        runtime_principal_id="agent-2",
        runtime_principal_name="Agent Two",
        started_at=now - timedelta(days=2),
        last_activity_at=now - timedelta(days=1),
        ended_at=now - timedelta(hours=12),
    )
    crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        runtime_session_id=str(recent_session.id),
        runtime_principal_type="managed_agent",
        runtime_principal_id="agent-1",
        runtime_principal_name="Agent One",
        model_alias="openai/gpt-5",
        provider_name="openai",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        estimated_cost=1.25,
    )
    old_usage = crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=500,
        duration=0.2,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        runtime_principal_type="managed_agent",
        runtime_principal_id="agent-2",
        runtime_principal_name="Agent Two",
        model_alias="openai/gpt-5.4",
        provider_name="openai",
        prompt_tokens=4,
        completion_tokens=0,
        total_tokens=4,
        estimated_cost=9.0,
    )
    old_usage.timestamp = now - timedelta(days=2)
    db_session.add(old_usage)
    db_session.commit()

    response = client.get("/api/v1/account/telemetry/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "active_agents": 1,
        "total_tool_calls": 1,
        "daily_cost": 1.25,
        "success_rate": 100.0,
    }
