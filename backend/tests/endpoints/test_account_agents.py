"""Endpoint tests for managed-agent registry surfaces."""

from datetime import UTC, datetime

from preloop.models.crud import (
    crud_api_usage,
    crud_runtime_session,
    crud_runtime_session_activity,
)
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

    response = client.get("/api/v1/agents")

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

    list_response = client.get("/api/v1/agents")
    assert list_response.status_code == 200
    agent_id = list_response.json()["items"][0]["id"]

    detail_response = client.get(f"/api/v1/agents/{agent_id}")

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

    first_session = crud_runtime_session.get_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="claude_code",
        session_source_id="workspace-1",
    )
    second_session = crud_runtime_session.get_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="claude_code",
        session_source_id="workspace-2",
    )
    assert first_session is not None
    assert second_session is not None

    crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        runtime_session_id=str(first_session.id),
        model_alias="openai/gpt-5",
        provider_name="openai",
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
        estimated_cost=0.25,
        runtime_principal_type="claude_code",
        runtime_principal_id=principal_id,
        runtime_principal_name="Claude Code Workspace",
    )
    crud_runtime_session_activity.log_tool_call(
        db_session,
        account_id=test_user.account_id,
        runtime_session_id=first_session.id,
        server_name="github",
        tool_name="search_issues",
        status="success",
        commit=False,
    )
    crud_runtime_session_activity.log_tool_call(
        db_session,
        account_id=test_user.account_id,
        runtime_session_id=second_session.id,
        server_name="github",
        tool_name="search_issues",
        status="failed",
        summary="rate limited",
        commit=False,
    )
    crud_runtime_session_activity.log_tool_call(
        db_session,
        account_id=test_user.account_id,
        runtime_session_id=second_session.id,
        server_name="jira",
        tool_name="get_issue",
        status="success",
    )
    crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=429,
        duration=0.2,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        runtime_session_id=str(second_session.id),
        model_alias="openai/gpt-5-mini",
        provider_name="openai",
        prompt_tokens=50,
        completion_tokens=10,
        total_tokens=60,
        estimated_cost=0.05,
        runtime_principal_type="claude_code",
        runtime_principal_id=principal_id,
        runtime_principal_name="Claude Code Workspace",
    )

    list_response = client.get("/api/v1/agents")
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1

    agent_id = body["items"][0]["id"]
    detail_response = client.get(f"/api/v1/agents/{agent_id}")

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["agent"]["session_source_id"] == principal_id
    assert detail_body["aggregate"]["session_count"] == 2
    assert detail_body["aggregate"]["total_requests"] == 2
    assert detail_body["aggregate"]["successful_requests"] == 1
    assert detail_body["aggregate"]["failed_requests"] == 1
    assert detail_body["aggregate"]["token_usage"]["prompt_tokens"] == 150
    assert detail_body["aggregate"]["token_usage"]["completion_tokens"] == 30
    assert detail_body["aggregate"]["token_usage"]["total_tokens"] == 180
    assert detail_body["aggregate"]["estimated_cost"] == 0.3
    assert len(detail_body["usage_by_model"]) == 2
    assert detail_body["usage_by_model"][0]["model_alias"] == "openai/gpt-5"
    assert detail_body["usage_by_model"][0]["provider_name"] == "openai"
    assert detail_body["usage_by_model"][0]["request_count"] == 1
    assert detail_body["usage_by_model"][0]["token_usage"]["total_tokens"] == 120
    assert detail_body["usage_by_model"][1]["model_alias"] == "openai/gpt-5-mini"
    assert detail_body["usage_by_model"][1]["request_count"] == 1
    assert len(detail_body["activity_by_server"]) == 2
    assert detail_body["activity_by_server"][0]["server_name"] == "github"
    assert detail_body["activity_by_server"][0]["call_count"] == 2
    assert detail_body["activity_by_server"][0]["successful_calls"] == 1
    assert detail_body["activity_by_server"][0]["failed_calls"] == 1
    assert detail_body["activity_by_tool"][0]["tool_name"] == "search_issues"
    assert detail_body["activity_by_tool"][0]["server_name"] == "github"
    assert detail_body["activity_by_tool"][0]["call_count"] == 2
    assert detail_body["activity_by_tool"][1]["tool_name"] == "get_issue"
    assert len(detail_body["sessions"]) == 2
    assert [session["session_source_id"] for session in detail_body["sessions"]] == [
        "workspace-2",
        "workspace-1",
    ]


def test_account_agent_update_endpoint_controls_lifecycle_and_owner(
    client, db_session, test_user
):
    """Managed agent update endpoint should support ownership and lifecycle controls."""
    token_response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-lifecycle",
            "runtime_principal_name": "Lifecycle Agent",
        },
    )
    assert token_response.status_code == 201

    list_response = client.get("/api/v1/agents")
    assert list_response.status_code == 200
    agent_id = list_response.json()["items"][0]["id"]

    update_response = client.patch(
        f"/api/v1/agents/{agent_id}",
        json={
            "owner_user_id": str(test_user.id),
            "lifecycle_action": "suspend",
            "reason": "maintenance window",
        },
    )

    assert update_response.status_code == 200
    body = update_response.json()
    assert body["owner_user_id"] == str(test_user.id)
    assert body["owner_username"] == test_user.username
    assert body["lifecycle_state"] == "suspended"
    assert body["lifecycle_reason"] == "maintenance window"
    assert body["activity_status"] == "suspended"

    reenroll_response = client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"lifecycle_action": "reenroll"},
    )
    assert reenroll_response.status_code == 200
    assert reenroll_response.json()["lifecycle_state"] == "active"


def test_account_agent_detail_includes_credentials_and_enrollments(
    client, db_session, test_user
):
    """Managed agent detail should expose durable credentials and enrollment state."""
    token_response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "openclaw",
            "session_source_id": "openclaw-workspace",
            "session_reference": "/Users/test/.openclaw/openclaw.json",
            "runtime_principal_name": "OpenClaw Workspace",
        },
    )
    assert token_response.status_code == 201

    list_response = client.get("/api/v1/agents")
    assert list_response.status_code == 200
    agent_id = list_response.json()["items"][0]["id"]

    credential_response = client.post(
        f"/api/v1/agents/{agent_id}/credentials",
        json={
            "name": "OpenClaw Durable Credential",
            "description": "Primary managed credential",
            "scopes": ["mcp:read", "mcp:write"],
        },
    )
    assert credential_response.status_code == 201
    credential_body = credential_response.json()
    assert credential_body["token"].startswith("agt_")
    assert credential_body["credential"]["name"] == "OpenClaw Durable Credential"

    enrollment_response = client.post(
        f"/api/v1/agents/{agent_id}/enrollments",
        json={
            "enrollment_type": "cli_managed_config",
            "adapter_key": "openclaw",
            "status": "pending",
            "target_config_path": "/Users/test/.openclaw/openclaw.json",
            "discovered_config": {
                "mcpServers": {"github": {"url": "https://example.com"}}
            },
            "managed_config": {
                "mcpServers": {"preloop": {"url": "https://preloop.test/mcp"}}
            },
            "backup_metadata": {"path": "/tmp/openclaw.backup.json"},
            "validation_result": {"dry_run": True},
            "restore_available": True,
        },
    )
    assert enrollment_response.status_code == 201

    detail_response = client.get(f"/api/v1/agents/{agent_id}")
    assert detail_response.status_code == 200
    body = detail_response.json()
    assert len(body["credentials"]) == 1
    assert body["credentials"][0]["name"] == "OpenClaw Durable Credential"
    assert body["credentials"][0]["status"] == "active"
    assert len(body["enrollments"]) == 2
    enrollment_types = {item["enrollment_type"] for item in body["enrollments"]}
    assert enrollment_types == {"cli_managed_config", "runtime_session_bootstrap"}
    cli_enrollment = next(
        item
        for item in body["enrollments"]
        if item["enrollment_type"] == "cli_managed_config"
    )
    bootstrap_enrollment = next(
        item
        for item in body["enrollments"]
        if item["enrollment_type"] == "runtime_session_bootstrap"
    )
    assert cli_enrollment["adapter_key"] == "openclaw"
    assert (
        bootstrap_enrollment["managed_config"]["runtime_session_id"]
        == (token_response.json()["runtime_session_id"])
    )

    revoke_response = client.delete(
        f"/api/v1/agents/{agent_id}/credentials/{credential_body['credential']['id']}"
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"

    credentials_response = client.get(f"/api/v1/agents/{agent_id}/credentials")
    assert credentials_response.status_code == 200
    assert credentials_response.json()[0]["status"] == "revoked"


def test_account_agent_enrollment_validate_and_restore(client, db_session, test_user):
    """Managed agent enrollments should support validation and restore actions."""
    token_response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "workspace-validate-restore",
            "session_reference": "/Users/test/.claude/mcp-servers.json",
            "runtime_principal_name": "Claude Code Workspace",
        },
    )
    assert token_response.status_code == 201

    list_response = client.get("/api/v1/agents")
    assert list_response.status_code == 200
    agent_id = list_response.json()["items"][0]["id"]

    enrollment_response = client.post(
        f"/api/v1/agents/{agent_id}/enrollments",
        json={
            "enrollment_type": "cli_managed_config",
            "adapter_key": "claude_code",
            "status": "applied",
            "target_config_path": "/Users/test/.claude/mcp-servers.json",
            "discovered_config": {
                "servers": {"github": {"url": "https://example.com"}}
            },
            "managed_config": {
                "servers": {"preloop": {"url": "https://preloop.test/mcp/v1"}}
            },
            "backup_metadata": {"backup_path": "/tmp/claude.backup.json"},
            "restore_available": True,
        },
    )
    assert enrollment_response.status_code == 201
    enrollment_id = enrollment_response.json()["id"]

    validate_response = client.post(
        f"/api/v1/agents/{agent_id}/enrollments/{enrollment_id}/validate",
        json={
            "status": "validated",
            "validation_result": {
                "ok": True,
                "checked": ["config_parse", "preloop_server_present"],
            },
        },
    )
    assert validate_response.status_code == 200
    validate_body = validate_response.json()
    assert validate_body["status"] == "validated"
    assert validate_body["validation_result"]["ok"] is True
    assert validate_body["last_validated_at"] is not None
    assert validate_body["restore_available"] is True

    restore_response = client.post(
        f"/api/v1/agents/{agent_id}/enrollments/{enrollment_id}/restore",
        json={
            "backup_metadata": {
                "backup_path": "/tmp/claude.backup.json",
                "restored_by": "test",
            },
            "validation_result": {"restored": True},
        },
    )
    assert restore_response.status_code == 200
    restore_body = restore_response.json()
    assert restore_body["status"] == "restored"
    assert restore_body["restore_available"] is False
    assert restore_body["backup_metadata"]["restored_by"] == "test"
    assert restore_body["validation_result"]["restored"] is True
    assert restore_body["last_restored_at"] is not None
