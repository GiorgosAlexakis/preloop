"""Endpoint tests for gateway usage summaries."""

from preloop.models.crud import (
    crud_api_usage,
    crud_flow,
    crud_flow_execution,
    crud_runtime_session,
)
from preloop.models.schemas.flow import FlowCreate
from preloop.models.schemas.flow_execution import FlowExecutionCreate


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
