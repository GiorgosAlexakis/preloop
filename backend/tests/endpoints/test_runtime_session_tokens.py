"""Tests for external runtime-session token onboarding."""

from datetime import datetime, UTC

from preloop.models.crud import crud_account, crud_api_key, crud_runtime_session
from preloop.models.models.mcp_server import MCPServer
from preloop.models.models.mcp_tool import MCPTool


def _create_active_mcp_server(db_session, account_id, *, name: str) -> MCPServer:
    server = MCPServer(
        account_id=account_id,
        name=name,
        url=f"https://{name}.example.com/mcp",
        transport="http-streaming",
        auth_type="none",
        status="active",
    )
    db_session.add(server)
    db_session.flush()
    return server


def _add_server_tool(db_session, server_id, *, tool_name: str) -> None:
    db_session.add(
        MCPTool(
            mcp_server_id=server_id,
            name=tool_name,
            description=f"{tool_name} description",
            input_schema={"type": "object"},
            discovered_at=datetime.now(UTC).isoformat(),
        )
    )
    db_session.flush()


def test_create_runtime_session_token(client, db_session, test_user):
    """Runtime session token endpoint should mint a token and upsert the session."""
    github_server = _create_active_mcp_server(
        db_session, test_user.account_id, name="github"
    )
    _add_server_tool(db_session, github_server.id, tool_name="search_issues")

    response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-123",
            "session_reference": "claude-session-abc",
            "runtime_principal_name": "Claude Code Workspace",
            "expires_in_minutes": 30,
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
        account_id=test_user.account_id,
        session_source_type="claude_code",
        session_source_id="workspace-123",
    )
    assert runtime_session is not None
    assert runtime_session.session_reference == "claude-session-abc"
    assert runtime_session.runtime_principal_name == "Claude Code Workspace"

    api_key = crud_api_key.get_by_key(db_session, key=body["token"])
    assert api_key is not None
    assert api_key.user_id == test_user.id
    assert api_key.scopes == ["mcp:read", "mcp:write"]
    assert api_key.context_data["runtime_session_id"] == str(runtime_session.id)
    assert api_key.context_data["runtime_principal"]["type"] == "claude_code"
    assert api_key.context_data["runtime_principal"]["id"] == "workspace-123"
    assert api_key.context_data["allowed_mcp_servers"] == ["github"]
    assert api_key.context_data["allowed_mcp_tools"] == [{"tool_name": "search_issues"}]


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


def test_create_runtime_session_token_rejects_scope_escalation(client):
    """Runtime session tokens should reject scopes outside the runtime-safe set."""
    response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-123",
            "scopes": ["mcp:read", "admin:all"],
        },
    )

    assert response.status_code == 400
    assert "only support these scopes" in response.json()["detail"]


def test_create_runtime_session_token_rejects_unknown_allowed_servers(client):
    """Runtime session tokens should only accept active account MCP servers."""
    response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-123",
            "allowed_mcp_servers": ["github"],
        },
    )

    assert response.status_code == 400
    assert "allowed_mcp_servers" in response.json()["detail"]


def test_runtime_session_identity_is_account_scoped(db_session):
    """Runtime session source identity should be isolated per account."""
    first_account = crud_account.create(
        db_session,
        obj_in={"organization_name": "Account One", "is_active": True},
    )
    second_account = crud_account.create(
        db_session,
        obj_in={"organization_name": "Account Two", "is_active": True},
    )
    now = datetime.now(UTC)

    first_session = crud_runtime_session.upsert_by_source(
        db_session,
        account_id=first_account.id,
        session_source_type="claude_code",
        session_source_id="workspace-123",
        runtime_principal_name="Account One Agent",
        last_activity_at=now,
    )
    second_session = crud_runtime_session.upsert_by_source(
        db_session,
        account_id=second_account.id,
        session_source_type="claude_code",
        session_source_id="workspace-123",
        runtime_principal_name="Account Two Agent",
        last_activity_at=now,
    )
    db_session.commit()

    assert first_session.id != second_session.id
    assert (
        crud_runtime_session.get_by_source(
            db_session,
            account_id=first_account.id,
            session_source_type="claude_code",
            session_source_id="workspace-123",
        ).id
        == first_session.id
    )
    assert (
        crud_runtime_session.get_by_source(
            db_session,
            account_id=second_account.id,
            session_source_type="claude_code",
            session_source_id="workspace-123",
        ).id
        == second_session.id
    )
