from datetime import datetime, timedelta, timezone

from preloop.models.crud import (
    crud_ai_model,
    crud_api_usage,
    crud_flow,
    crud_flow_execution,
    crud_gateway_usage_search_document,
    crud_runtime_session,
)
from preloop.models.schemas.flow import FlowCreate
from preloop.models.schemas.flow_execution import FlowExecutionCreate


def test_search_account_documents_isolates_runtime_session_with_legacy_fallback(
    db_session, test_user
):
    ai_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5.4",
            "api_key": "provider-secret",
        },
        account_id=test_user.account_id,
    )
    flow = crud_flow.create(
        db=db_session,
        flow_in=FlowCreate(
            name="Gateway Search Flow",
            prompt_template="Test",
            trigger_event_source="github",
            trigger_event_types=["test"],
            ai_model_id=ai_model.id,
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
        FlowExecutionCreate(flow_id=flow.id, status="RUNNING"),
    )
    selected_session = crud_runtime_session.upsert_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="flow_execution",
        session_source_id=str(execution.id),
        session_reference="selected-session",
        runtime_principal_type="flow_execution",
        runtime_principal_id=str(execution.id),
        runtime_principal_name="Gateway Search Flow",
        started_at=execution.start_time,
        last_activity_at=execution.start_time,
    )
    sibling_session = crud_runtime_session.upsert_by_source(
        db_session,
        account_id=test_user.account_id,
        session_source_type="custom",
        session_source_id="sibling-session",
        session_reference="sibling-session",
        runtime_principal_type="flow_execution",
        runtime_principal_id=str(execution.id),
        runtime_principal_name="Gateway Search Flow",
        started_at=execution.start_time,
        last_activity_at=execution.start_time,
    )

    selected_usage = crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        ai_model_id=str(ai_model.id),
        flow_id=str(flow.id),
        flow_execution_id=str(execution.id),
        runtime_session_id=str(selected_session.id),
        model_alias="openai/gpt-5.4",
        provider_name="openai",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        estimated_cost=0.1,
    )
    sibling_usage = crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        ai_model_id=str(ai_model.id),
        flow_id=str(flow.id),
        flow_execution_id=str(execution.id),
        runtime_session_id=str(sibling_session.id),
        model_alias="openai/gpt-5.4",
        provider_name="openai",
        prompt_tokens=20,
        completion_tokens=10,
        total_tokens=30,
        estimated_cost=0.2,
    )
    legacy_usage = crud_api_usage.log_gateway_request(
        db_session,
        endpoint="/openai/v1/responses",
        method="POST",
        status_code=200,
        duration=0.1,
        user_id=str(test_user.id),
        account_id=str(test_user.account_id),
        ai_model_id=str(ai_model.id),
        flow_id=str(flow.id),
        flow_execution_id=str(execution.id),
        model_alias="openai/gpt-5.4",
        provider_name="openai",
        prompt_tokens=30,
        completion_tokens=15,
        total_tokens=45,
        estimated_cost=0.3,
    )

    crud_gateway_usage_search_document.upsert_for_api_usage(
        db_session,
        api_usage=selected_usage,
        searchable_text="selected runtime session interaction",
    )
    crud_gateway_usage_search_document.upsert_for_api_usage(
        db_session,
        api_usage=sibling_usage,
        searchable_text="sibling runtime session interaction",
    )
    crud_gateway_usage_search_document.upsert_for_api_usage(
        db_session,
        api_usage=legacy_usage,
        searchable_text="legacy unbound interaction",
    )

    start_date = datetime.now(timezone.utc) - timedelta(days=1)
    end_date = datetime.now(timezone.utc) + timedelta(days=1)

    result = crud_gateway_usage_search_document.search_account_documents(
        db_session,
        account_id=str(test_user.account_id),
        start_date=start_date,
        end_date=end_date,
        runtime_session_id=str(selected_session.id),
        flow_execution_id=str(execution.id),
        limit=20,
        offset=0,
    )

    returned_usage_ids = {item["api_usage_id"] for item in result["items"]}

    assert result["total"] == 2
    assert str(selected_usage.id) in returned_usage_ids
    assert str(legacy_usage.id) in returned_usage_ids
    assert str(sibling_usage.id) not in returned_usage_ids

    sibling_result = crud_gateway_usage_search_document.search_account_documents(
        db_session,
        account_id=str(test_user.account_id),
        start_date=start_date,
        end_date=end_date,
        runtime_session_id=str(sibling_session.id),
        flow_execution_id=str(execution.id),
        limit=20,
        offset=0,
    )

    sibling_usage_ids = {item["api_usage_id"] for item in sibling_result["items"]}

    assert sibling_result["total"] == 1
    assert str(sibling_usage.id) in sibling_usage_ids
    assert str(selected_usage.id) not in sibling_usage_ids
    assert str(legacy_usage.id) not in sibling_usage_ids
