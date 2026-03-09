"""Endpoint tests for gateway usage summaries."""

from preloop.models.crud import (
    crud_api_usage,
    crud_flow,
    crud_flow_execution,
    crud_runtime_session,
)
from preloop.models.schemas.flow import FlowCreate
from preloop.models.schemas.flow_execution import FlowExecutionCreate
from preloop.services.gateway_usage_search import GatewayUsageSearchService


def test_account_gateway_usage_summary_endpoint(client, db_session, test_user):
    """Account usage summary endpoint should return aggregated session-aware usage."""
    flow = crud_flow.create(
        db=db_session,
        flow_in=FlowCreate(
            name="Gateway Session Flow",
            prompt_template="Test",
            trigger_event_source="github",
            trigger_event_types=["test"],
            agent_type="codex",
            agent_config={},
            allowed_mcp_servers=[],
            allowed_mcp_tools=[],
            account_id=test_user.account_id,
        ),
        account_id=test_user.account_id,
    )
    execution = crud_flow_execution.create(
        db_session,
        FlowExecutionCreate(
            flow_id=flow.id,
            status="SUCCEEDED",
            agent_session_reference="session-123",
        ),
    )
    runtime_session = crud_runtime_session.upsert_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="flow_execution",
        session_source_id=str(execution.id),
        session_reference="session-123",
        runtime_principal_type="flow_execution",
        runtime_principal_id=str(execution.id),
        runtime_principal_name=flow.name,
        started_at=execution.start_time,
        last_activity_at=execution.start_time,
    )
    db_session.commit()
    crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        flow_id=str(flow.id),
        flow_execution_id=str(execution.id),
        runtime_session_id=str(runtime_session.id),
        model_alias="openai/gpt-5",
        provider_name="openai",
        prompt_tokens=12,
        completion_tokens=8,
        total_tokens=20,
        estimated_cost=0.05,
    )

    response = client.get("/api/v1/account/gateway-usage/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 1
    assert body["token_usage"]["total_tokens"] == 20
    assert body["estimated_cost"] == 0.05
    assert body["usage_by_model"][0]["model_alias"] == "openai/gpt-5"
    assert body["usage_by_session"][0]["runtime_session_id"] == str(runtime_session.id)
    assert body["usage_by_session"][0]["session_source_type"] == "flow_execution"
    assert body["usage_by_session"][0]["flow_execution_id"] == str(execution.id)
    assert body["usage_by_session"][0]["flow_name"] == "Gateway Session Flow"
    assert body["usage_by_session"][0]["session_reference"] == "session-123"


def test_flow_gateway_usage_summary_endpoint(client, db_session, test_user):
    """Flow usage summary endpoint should scope to one flow."""
    flow = crud_flow.create(
        db=db_session,
        flow_in=FlowCreate(
            name="Gateway Summary Flow",
            prompt_template="Test",
            trigger_event_source="github",
            trigger_event_types=["test"],
            agent_type="codex",
            agent_config={},
            allowed_mcp_servers=[],
            allowed_mcp_tools=[],
            account_id=test_user.account_id,
        ),
        account_id=test_user.account_id,
    )
    execution = crud_flow_execution.create(
        db_session,
        FlowExecutionCreate(flow_id=flow.id, status="SUCCEEDED"),
    )
    crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/chat/completions",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        flow_id=str(flow.id),
        flow_execution_id=str(execution.id),
        model_alias="openai/gpt-5",
        provider_name="openai",
        prompt_tokens=40,
        completion_tokens=10,
        total_tokens=50,
        estimated_cost=0.2,
    )

    response = client.get(f"/api/v1/flows/{flow.id}/gateway-usage/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["flow_id"] == str(flow.id)
    assert body["total_requests"] == 1
    assert body["token_usage"]["total_tokens"] == 50
    assert body["usage_by_execution"][0]["flow_execution_id"] == str(execution.id)


def test_account_gateway_usage_search_endpoint(client, db_session, test_user):
    """Account gateway search should return indexed interaction hits."""
    flow = crud_flow.create(
        db=db_session,
        flow_in=FlowCreate(
            name="Gateway Search Flow",
            prompt_template="Test",
            trigger_event_source="github",
            trigger_event_types=["test"],
            agent_type="codex",
            agent_config={},
            allowed_mcp_servers=[],
            allowed_mcp_tools=[],
            account_id=test_user.account_id,
        ),
        account_id=test_user.account_id,
    )
    execution = crud_flow_execution.create(
        db_session,
        FlowExecutionCreate(
            flow_id=flow.id,
            status="RUNNING",
            agent_session_reference="session-search-123",
        ),
    )
    runtime_session = crud_runtime_session.upsert_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="flow_execution",
        session_source_id=str(execution.id),
        session_reference="session-search-123",
        runtime_principal_type="flow_execution",
        runtime_principal_id=str(execution.id),
        runtime_principal_name=flow.name,
        started_at=execution.start_time,
        last_activity_at=execution.start_time,
    )
    db_session.commit()
    usage = crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        flow_id=str(flow.id),
        flow_execution_id=str(execution.id),
        runtime_session_id=str(runtime_session.id),
        model_alias="openai/gpt-5",
        provider_name="openai",
        prompt_tokens=21,
        completion_tokens=13,
        total_tokens=34,
        estimated_cost=0.11,
        runtime_principal_type="flow_execution",
        runtime_principal_id=str(execution.id),
        runtime_principal_name=flow.name,
    )
    GatewayUsageSearchService(db_session).index_interaction(
        usage=usage,
        request_payload={
            "input": "Please review the production rollback checklist",
            "metadata": {"environment": "production"},
        },
        response_payload={
            "output_text": "Rollback checklist reviewed successfully",
        },
    )

    response = client.get(
        "/api/v1/account/gateway-usage/search",
        params={"query": "rollback checklist"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["api_usage_id"] == str(usage.id)
    assert body["items"][0]["flow_name"] == "Gateway Search Flow"
    assert body["items"][0]["runtime_session_id"] == str(runtime_session.id)
    assert body["items"][0]["session_reference"] == "session-search-123"
    assert body["items"][0]["token_usage"]["total_tokens"] == 34
    assert "rollback checklist" in body["items"][0]["excerpt"].lower()


def test_account_gateway_usage_search_lists_recent_documents_without_query(
    client, db_session, test_user
):
    """Account gateway search should list recent indexed interactions without a query."""
    first_usage = crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/anthropic/v1/messages",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        model_alias="anthropic/claude-sonnet-4",
        provider_name="anthropic",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        estimated_cost=0.02,
    )
    second_usage = crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/chat/completions",
        method="POST",
        status_code=500,
        duration=0.2,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        model_alias="openai/gpt-5",
        provider_name="openai",
        prompt_tokens=18,
        completion_tokens=0,
        total_tokens=18,
        estimated_cost=0.03,
    )
    search_service = GatewayUsageSearchService(db_session)
    search_service.index_interaction(
        usage=first_usage,
        request_payload={"input": "Summarize onboarding status"},
        response_payload={"output_text": "Onboarding status summary"},
    )
    search_service.index_interaction(
        usage=second_usage,
        request_payload={"input": "Diagnose failed deployment"},
        response_payload={"error": "provider timeout"},
    )

    response = client.get(
        "/api/v1/account/gateway-usage/search",
        params={"limit": 1, "provider_name": "openai"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["api_usage_id"] == str(second_usage.id)
    assert body["items"][0]["provider_name"] == "openai"
    assert body["items"][0]["outcome"] == "error"


def test_account_runtime_sessions_endpoints(client, db_session, test_user):
    """Runtime session explorer endpoints should list and drill into sessions."""
    runtime_session = crud_runtime_session.upsert_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="claude_code",
        session_source_id="workspace-42",
        session_reference="claude-session-42",
        runtime_principal_type="claude_code",
        runtime_principal_id="workspace-42",
        runtime_principal_name="Claude Workspace",
        started_at=test_user.created_at,
        last_activity_at=test_user.created_at,
    )
    db_session.commit()

    usage = crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/anthropic/v1/messages",
        method="POST",
        status_code=200,
        duration=0.2,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        runtime_session_id=str(runtime_session.id),
        model_alias="anthropic/claude-sonnet-4",
        provider_name="anthropic",
        prompt_tokens=55,
        completion_tokens=34,
        total_tokens=89,
        estimated_cost=0.14,
        runtime_principal_type="claude_code",
        runtime_principal_id="workspace-42",
        runtime_principal_name="Claude Workspace",
    )
    GatewayUsageSearchService(db_session).index_interaction(
        usage=usage,
        request_payload={"input": "Summarize the deployment risk review"},
        response_payload={"output_text": "Deployment risk review summarized"},
    )

    list_response = client.get(
        "/api/v1/account/runtime-sessions",
        params={"session_source_type": "claude_code"},
    )

    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["id"] == str(runtime_session.id)
    assert list_body["items"][0]["runtime_principal_name"] == "Claude Workspace"
    assert list_body["items"][0]["token_usage"]["total_tokens"] == 89

    detail_response = client.get(
        f"/api/v1/account/runtime-sessions/{runtime_session.id}",
        params={"interaction_query": "deployment risk"},
    )

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["session"]["id"] == str(runtime_session.id)
    assert detail_body["session"]["session_source_type"] == "claude_code"
    assert (
        detail_body["usage_by_model"][0]["model_alias"] == "anthropic/claude-sonnet-4"
    )
    assert detail_body["interactions"]["total"] == 1
    assert (
        "deployment risk" in detail_body["interactions"]["items"][0]["excerpt"].lower()
    )
