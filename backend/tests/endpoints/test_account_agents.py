"""Endpoint tests for managed-agent registry surfaces."""

from datetime import UTC, datetime

from preloop.models.crud import crud_api_usage, crud_runtime_session
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


def test_account_agents_endpoint_lists_onboarded_agents(client, db_session, test_user):
    """Account agents endpoint should expose registry entries created by onboarding."""
    github_server = _create_active_mcp_server(
        db_session, test_user.account_id, name="github"
    )
    _add_server_tool(db_session, github_server.id, tool_name="search_issues")

    token_response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-123",
            "session_reference": "claude-session-abc",
            "runtime_principal_name": "Claude Code Workspace",
            "allowed_mcp_servers": ["github"],
        },
    )

    assert token_response.status_code == 201
    runtime_session = crud_runtime_session.get_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="claude_code",
        session_source_id="workspace-123",
    )
    assert runtime_session is not None

    crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        runtime_session_id=str(runtime_session.id),
        model_alias="openai/gpt-5",
        provider_name="openai",
        prompt_tokens=120,
        completion_tokens=40,
        total_tokens=160,
        estimated_cost=0.12,
        runtime_principal_type="claude_code",
        runtime_principal_id="workspace-123",
        runtime_principal_name="Claude Code Workspace",
    )

    response = client.get("/api/v1/account/agents")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["display_name"] == "Claude Code Workspace"
    assert item["session_source_type"] == "claude_code"
    assert item["session_source_id"] == "workspace-123"
    assert item["session_reference"] == "claude-session-abc"
    assert item["runtime_session_id"] == str(runtime_session.id)
    assert item["managed_mcp_servers"] == ["github"]
    assert item["total_requests"] == 1
    assert item["estimated_cost"] == 0.12
    assert item["latest_model_alias"] == "openai/gpt-5"
    assert item["latest_provider_name"] == "openai"


def test_account_agent_detail_endpoint_returns_one_agent(client, db_session, test_user):
    """Managed agent detail endpoint should return the scoped registry summary."""
    github_server = _create_active_mcp_server(
        db_session, test_user.account_id, name="github"
    )
    _add_server_tool(db_session, github_server.id, tool_name="search_issues")

    token_response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-456",
            "session_reference": "claude-session-def",
            "runtime_principal_name": "Claude Code Workspace 2",
            "allowed_mcp_servers": ["github"],
        },
    )

    assert token_response.status_code == 201

    list_response = client.get("/api/v1/account/agents")
    assert list_response.status_code == 200
    agent_id = list_response.json()["items"][0]["id"]

    detail_response = client.get(f"/api/v1/account/agents/{agent_id}")

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["agent"]["id"] == agent_id
    assert body["agent"]["display_name"] == "Claude Code Workspace 2"
    assert body["agent"]["session_source_type"] == "claude_code"
    assert body["agent"]["session_source_id"] == "workspace-456"
    assert body["agent"]["managed_mcp_servers"] == ["github"]
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["session_source_id"] == "workspace-456"


def test_account_agent_detail_endpoint_includes_session_history(
    client, db_session, test_user
):
    """Managed agent detail should include multiple runtime sessions for one durable agent."""
    principal_id = "claude-code-agent-1"

    first_response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-1",
            "runtime_principal_id": principal_id,
            "runtime_principal_name": "Claude Code Workspace",
        },
    )
    second_response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-2",
            "runtime_principal_id": principal_id,
            "runtime_principal_name": "Claude Code Workspace",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    list_response = client.get("/api/v1/account/agents")
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1

    agent_id = body["items"][0]["id"]
    detail_response = client.get(f"/api/v1/account/agents/{agent_id}")

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["agent"]["session_source_id"] == principal_id
    assert len(detail_body["sessions"]) == 2
    assert [session["session_source_id"] for session in detail_body["sessions"]] == [
        "workspace-2",
        "workspace-1",
    ]
