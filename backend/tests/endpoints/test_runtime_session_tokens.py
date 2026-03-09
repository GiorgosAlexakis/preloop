"""Tests for external runtime-session token onboarding."""

from preloop.models.crud import crud_api_key, crud_runtime_session


def test_create_runtime_session_token(client, db_session, test_user):
    """Runtime session token endpoint should mint a token and upsert the session."""
    response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-123",
            "session_reference": "claude-session-abc",
            "runtime_principal_name": "Claude Code Workspace",
            "expires_in_minutes": 30,
            "allowed_mcp_tools": [{"tool_name": "search_issues"}],
            "allowed_mcp_servers": ["github"],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["session_source_type"] == "claude_code"
    assert body["session_source_id"] == "workspace-123"
    assert body["session_reference"] == "claude-session-abc"
    assert body["token"]

    runtime_session = crud_runtime_session.get_by_source(
        db_session,
        session_source_type="claude_code",
        session_source_id="workspace-123",
    )
    assert runtime_session is not None
    assert runtime_session.session_reference == "claude-session-abc"
    assert runtime_session.runtime_principal_name == "Claude Code Workspace"

    api_key = crud_api_key.get_by_key(db_session, key=body["token"])
    assert api_key is not None
    assert api_key.user_id == test_user.id
    assert api_key.context_data["runtime_session_id"] == str(runtime_session.id)
    assert api_key.context_data["runtime_principal"]["type"] == "claude_code"
    assert api_key.context_data["runtime_principal"]["id"] == "workspace-123"
    assert api_key.context_data["allowed_mcp_servers"] == ["github"]


def test_create_runtime_session_token_rejects_unknown_source_type(client):
    """Runtime session token endpoint should validate supported source types."""
    response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "totally_unknown_agent",
            "session_source_id": "workspace-123",
        },
    )

    assert response.status_code == 400
    assert "Unsupported session_source_type" in response.json()["detail"]
