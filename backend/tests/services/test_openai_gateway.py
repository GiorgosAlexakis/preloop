"""Tests for the OpenAI-compatible gateway service."""

from unittest.mock import patch

import pytest

from preloop.config import settings
from preloop.models.models.api_usage import ApiUsage
from preloop.models.crud import (
    crud_account,
    crud_ai_model,
    crud_audit_log,
    crud_flow,
    crud_flow_execution,
    crud_gateway_usage_search_document,
    crud_runtime_session,
)
from preloop.models.crud import crud_api_key
from preloop.models.schemas.flow import FlowCreate
from preloop.models.schemas.flow_execution import FlowExecutionCreate
from preloop.services.model_gateway_auth import ModelGatewayAuthContext
from preloop.services.model_gateway_errors import ModelGatewayAPIError
from preloop.services.openai_gateway import OpenAIGatewayService


def test_list_models_returns_gateway_enabled_aliases(db_session, test_user):
    """Only gateway-enabled models should be listed."""
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "test-key",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                }
            },
        },
        account_id=test_user.account_id,
    )
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Non Gateway Model",
            "provider_name": "anthropic",
            "model_identifier": "claude-sonnet-4-5",
            "api_key": "test-key",
        },
        account_id=test_user.account_id,
    )

    service = OpenAIGatewayService(
        db_session, ModelGatewayAuthContext(token="t", user=test_user)
    )
    payload = service.list_models()

    assert payload["object"] == "list"
    assert [item["id"] for item in payload["data"]] == ["openai/gpt-5"]


def test_create_response_requires_gateway_enabled_default_when_model_omitted(
    db_session, test_user
):
    """Omitted model should not fall back to a non-gateway default."""
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Direct Default Model",
            "provider_name": "openai",
            "model_identifier": "gpt-4.1",
            "api_key": "provider-secret",
            "is_default": True,
        },
        account_id=test_user.account_id,
    )
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                }
            },
        },
        account_id=test_user.account_id,
    )

    service = OpenAIGatewayService(
        db_session, ModelGatewayAuthContext(token="t", user=test_user)
    )

    with patch("preloop.services.openai_gateway.litellm.completion") as mock_completion:
        with pytest.raises(
            ModelGatewayAPIError, match="No gateway-enabled default model configured"
        ) as exc:
            service.create_response({"instructions": "Be brief", "input": "Hello"})

    assert exc.value.status_code == 404
    mock_completion.assert_not_called()


def test_create_response_normalizes_and_calls_litellm(db_session, test_user):
    """Responses API should normalize input and return OpenAI-style response output."""
    ai_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                },
                "pricing": {"input_price_per_1k": 0.01, "output_price_per_1k": 0.02},
            },
            "is_default": True,
        },
        account_id=test_user.account_id,
    )
    runtime_api_key, _ = crud_api_key.create_runtime_key(
        db_session,
        name="Gateway Runtime Token",
        account_id=test_user.account_id,
        user_id=test_user.id,
        context_data={
            "runtime_session_id": str(
                crud_runtime_session.upsert_by_source(
                    db_session,
                    account_id=test_user.account_id,
                    session_source_type="custom",
                    session_source_id="gateway-test-session",
                    runtime_principal_type="flow_execution",
                    runtime_principal_id="11111111-1111-1111-1111-111111111111",
                    runtime_principal_name="Test Flow",
                    started_at=ai_model.created_at,
                    last_activity_at=ai_model.created_at,
                ).id
            ),
            "runtime_principal": {
                "type": "flow_execution",
                "id": "11111111-1111-1111-1111-111111111111",
                "name": "Test Flow",
            },
        },
    )

    service = OpenAIGatewayService(
        db_session,
        ModelGatewayAuthContext(token="t", user=test_user, api_key=runtime_api_key),
    )
    litellm_response = {
        "id": "chatcmpl_123",
        "created": 1710000000,
        "choices": [
            {
                "message": {"role": "assistant", "content": "Gateway says hello"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value=litellm_response,
    ) as mock_completion:
        payload = service.create_response(
            {
                "model": "openai/gpt-5",
                "instructions": "Be brief",
                "input": "Hello",
            }
        )

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-5"
    assert kwargs["api_key"] == "provider-secret"
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["role"] == "user"
    assert payload["output_text"] == "Gateway says hello"
    assert payload["usage"]["total_tokens"] == 18

    usage_row = (
        db_session.query(ApiUsage)
        .filter(ApiUsage.endpoint == "/openai/v1/responses")
        .order_by(ApiUsage.timestamp.desc())
        .first()
    )
    assert usage_row is not None
    assert usage_row.user_id == test_user.id
    assert usage_row.account_id == test_user.account_id
    assert usage_row.api_key_id == runtime_api_key.id
    assert usage_row.ai_model_id == ai_model.id
    assert usage_row.model_alias == "openai/gpt-5"
    assert usage_row.provider_name == "openai"
    assert usage_row.prompt_tokens == 11
    assert usage_row.completion_tokens == 7
    assert usage_row.total_tokens == 18
    assert usage_row.estimated_cost == 0.00025
    assert usage_row.runtime_session_id is not None
    assert usage_row.runtime_principal_type == "flow_execution"
    assert usage_row.runtime_principal_name == "Test Flow"


def test_create_response_marks_soft_limit_exceeded_in_usage_metadata(
    db_session, test_user
):
    """Soft-limit exceedance should allow the request but annotate the usage row."""
    account = crud_account.get(db_session, id=test_user.account_id)
    crud_account.update(
        db_session,
        db_obj=account,
        obj_in={
            "meta_data": {
                "model_gateway_budget": {
                    "soft_limit_usd": 0.00001,
                    "monthly_usd_limit": 1.0,
                }
            }
        },
    )

    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                },
                "pricing": {"input_price_per_1k": 0.01, "output_price_per_1k": 0.02},
            },
            "is_default": True,
        },
        account_id=test_user.account_id,
    )

    service = OpenAIGatewayService(
        db_session, ModelGatewayAuthContext(token="t", user=test_user)
    )
    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value={
            "id": "chatcmpl_123",
            "created": 1710000000,
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Gateway says hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        },
    ):
        service.create_response(
            {"model": "openai/gpt-5", "instructions": "Be brief", "input": "Hello"}
        )

    usage_row = (
        db_session.query(ApiUsage)
        .filter(ApiUsage.endpoint == "/openai/v1/responses")
        .order_by(ApiUsage.timestamp.desc())
        .first()
    )
    assert usage_row is not None
    assert usage_row.meta_data["budget"]["soft_limit_exceeded"] is True
    assert usage_row.meta_data["budget"]["hard_limit_exceeded"] is False


def test_create_response_appends_model_gateway_event_for_flow_execution(
    db_session, test_user
):
    """Completed gateway calls should append one flow execution log entry."""
    ai_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                }
            },
            "is_default": True,
        },
        account_id=test_user.account_id,
    )
    flow = crud_flow.create(
        db=db_session,
        flow_in=FlowCreate(
            name="Gateway Event Flow",
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
    runtime_api_key, _ = crud_api_key.create_runtime_key(
        db_session,
        name="Gateway Runtime Token",
        account_id=test_user.account_id,
        user_id=test_user.id,
        context_data={
            "flow_id": str(flow.id),
            "flow_execution_id": str(execution.id),
            "runtime_session_id": str(
                crud_runtime_session.upsert_by_source(
                    db_session,
                    account_id=test_user.account_id,
                    session_source_type="flow_execution",
                    session_source_id=str(execution.id),
                    session_reference="gateway-event-session",
                    runtime_principal_type="flow_execution",
                    runtime_principal_id=str(execution.id),
                    runtime_principal_name="Gateway Event Flow",
                    started_at=execution.start_time,
                    last_activity_at=execution.start_time,
                ).id
            ),
            "runtime_principal": {
                "type": "flow_execution",
                "id": str(execution.id),
                "name": "Gateway Event Flow",
            },
        },
    )

    service = OpenAIGatewayService(
        db_session,
        ModelGatewayAuthContext(token="t", user=test_user, api_key=runtime_api_key),
    )

    with (
        patch(
            "preloop.services.openai_gateway.litellm.completion",
            return_value={
                "id": "chatcmpl_123",
                "created": 1710000000,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Gateway says hello",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                },
            },
        ),
        patch(
            "preloop.services.model_gateway_events.crud_flow_execution.append_log"
        ) as mock_append_log,
    ):
        service.create_response(
            {
                "model": "openai/gpt-5",
                "instructions": "Be brief",
                "input": "Hello",
            }
        )

    mock_append_log.assert_called_once()
    assert mock_append_log.call_args.args[1] == str(execution.id)
    event = mock_append_log.call_args.args[2]
    assert event["type"] == "model_gateway_call"
    assert event["execution_id"] == str(execution.id)
    assert event["runtime_session_id"] is not None
    assert event["flow_id"] == str(flow.id)
    assert event["payload"]["outcome"] == "success"
    assert event["payload"]["endpoint_kind"] == "responses"


def test_create_response_denies_when_flow_budget_exceeded(db_session, test_user):
    """Flow budget hard limits should deny the request before the upstream call."""
    ai_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                },
                "pricing": {"input_price_per_1k": 0.01, "output_price_per_1k": 0.02},
            },
            "is_default": True,
        },
        account_id=test_user.account_id,
    )
    flow = crud_flow.create(
        db=db_session,
        flow_in=FlowCreate(
            name="Budgeted Flow",
            prompt_template="Test",
            trigger_event_source="github",
            trigger_event_types=["test"],
            ai_model_id=ai_model.id,
            agent_type="codex",
            agent_config={"model_gateway_budget": {"monthly_usd_limit": 0.00001}},
            allowed_mcp_servers=[],
            allowed_mcp_tools=[],
            account_id=test_user.account_id,
        ),
        account_id=test_user.account_id,
    )
    runtime_api_key, _ = crud_api_key.create_runtime_key(
        db_session,
        name="Gateway Runtime Token",
        account_id=test_user.account_id,
        user_id=test_user.id,
        context_data={"flow_id": str(flow.id)},
    )

    service = OpenAIGatewayService(
        db_session,
        ModelGatewayAuthContext(token="t", user=test_user, api_key=runtime_api_key),
    )

    with patch("preloop.services.openai_gateway.litellm.completion") as mock_completion:
        with pytest.raises(
            ModelGatewayAPIError, match="flow monthly limit reached"
        ) as exc:
            service.create_response(
                {"model": "openai/gpt-5", "instructions": "Be brief", "input": "Hello"}
            )

    assert exc.value.status_code == 403
    mock_completion.assert_not_called()

    audit_logs = crud_audit_log.get_by_account(
        db_session, account_id=test_user.account_id
    )
    gateway_logs = [log for log in audit_logs if log.action == "model_gateway_request"]
    assert len(gateway_logs) == 1
    assert gateway_logs[0].status == "budget_denied"
    assert gateway_logs[0].details["requested_model"] == "openai/gpt-5"
    assert gateway_logs[0].details["api_key_name"] == "Gateway Runtime Token"
    assert gateway_logs[0].details["error_type"] == "budget_limit_exceeded"


def test_create_response_denies_budgeted_request_when_pricing_metadata_missing(
    db_session, test_user
):
    """Budgeted accounts should fail closed when request cost cannot be estimated."""
    account = crud_account.get(db_session, id=test_user.account_id)
    crud_account.update(
        db_session,
        db_obj=account,
        obj_in={"meta_data": {"model_gateway_budget": {"monthly_usd_limit": 1.0}}},
    )
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                }
            },
            "is_default": True,
        },
        account_id=test_user.account_id,
    )
    service = OpenAIGatewayService(
        db_session, ModelGatewayAuthContext(token="t", user=test_user)
    )

    with patch("preloop.services.openai_gateway.litellm.completion") as mock_completion:
        with pytest.raises(
            ModelGatewayAPIError,
            match="pricing metadata for the selected gateway model",
        ) as exc:
            service.create_response({"model": "openai/gpt-5", "input": "Hello"})

    assert exc.value.status_code == 403
    mock_completion.assert_not_called()

    audit_logs = crud_audit_log.get_by_account(
        db_session, account_id=test_user.account_id
    )
    gateway_logs = [log for log in audit_logs if log.action == "model_gateway_request"]
    assert len(gateway_logs) == 1
    assert gateway_logs[0].status == "budget_denied"
    assert gateway_logs[0].details["error_type"] == "budget_limit_exceeded"


def test_create_response_maps_upstream_status_to_openai_error(db_session, test_user):
    """Upstream status codes should become OpenAI-native gateway errors."""
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                }
            },
            "is_default": True,
        },
        account_id=test_user.account_id,
    )
    service = OpenAIGatewayService(
        db_session, ModelGatewayAuthContext(token="t", user=test_user)
    )

    class FakeLiteLLMRateLimitError(Exception):
        status_code = 429
        message = "Rate limit exceeded"

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        side_effect=FakeLiteLLMRateLimitError(),
    ):
        with pytest.raises(ModelGatewayAPIError) as exc:
            service.create_response(
                {"model": "openai/gpt-5", "instructions": "Be brief", "input": "Hello"}
            )

    assert exc.value.status_code == 429
    assert exc.value.to_payload() == {
        "error": {
            "message": "Rate limit exceeded",
            "type": "rate_limit_error",
            "param": None,
            "code": None,
        }
    }

    audit_logs = crud_audit_log.get_by_account(
        db_session, account_id=test_user.account_id
    )
    gateway_logs = [log for log in audit_logs if log.action == "model_gateway_request"]
    assert len(gateway_logs) == 1
    assert gateway_logs[0].status == "failed"
    assert gateway_logs[0].details["status_code"] == 429
    assert gateway_logs[0].details["error_type"] == "rate_limit_error"
    assert gateway_logs[0].details["error_detail"] == "Rate limit exceeded"


def test_stream_response_records_usage_after_completion(db_session, test_user):
    """Streaming responses should emit SSE events and still persist usage facts."""
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                },
                "pricing": {"input_price_per_1k": 0.01, "output_price_per_1k": 0.02},
            },
            "is_default": True,
        },
        account_id=test_user.account_id,
    )

    service = OpenAIGatewayService(
        db_session, ModelGatewayAuthContext(token="t", user=test_user)
    )
    stream_chunks = iter(
        [
            {
                "id": "chatcmpl_123",
                "created": 1710000000,
                "choices": [{"index": 0, "delta": {"content": "Hello "}}],
            },
            {
                "id": "chatcmpl_123",
                "created": 1710000000,
                "choices": [{"index": 0, "delta": {"content": "world"}}],
            },
            {
                "id": "chatcmpl_123",
                "created": 1710000000,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 4,
                    "total_tokens": 7,
                },
            },
        ]
    )

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value=stream_chunks,
    ):
        events = list(
            service.stream_response(
                {
                    "model": "openai/gpt-5",
                    "input": "Hello",
                    "stream": True,
                }
            )
        )

    assert any("response.created" in event for event in events)
    assert any("response.output_text.delta" in event for event in events)
    assert any("response.completed" in event for event in events)
    assert events[-1] == "data: [DONE]\n\n"

    usage_row = (
        db_session.query(ApiUsage)
        .filter(ApiUsage.endpoint == "/openai/v1/responses")
        .order_by(ApiUsage.timestamp.desc())
        .first()
    )
    assert usage_row is not None
    assert usage_row.total_tokens == 7
    assert usage_row.estimated_cost == 0.00011


def test_create_response_auto_indexes_usage_document_when_enabled(
    db_session, test_user
):
    """Successful gateway requests should auto-index after usage and event recording."""
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                }
            },
            "is_default": True,
        },
        account_id=test_user.account_id,
    )
    service = OpenAIGatewayService(
        db_session, ModelGatewayAuthContext(token="t", user=test_user)
    )

    with (
        patch.object(settings, "model_gateway_auto_index_interactions", True),
        patch.object(settings, "model_gateway_capture_content", False),
        patch(
            "preloop.services.openai_gateway.litellm.completion",
            return_value={
                "id": "chatcmpl_123",
                "created": 1710000000,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Gateway says hello",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                },
            },
        ),
    ):
        service.create_response(
            {
                "model": "openai/gpt-5",
                "instructions": "Be brief",
                "input": "Hello",
            }
        )

    usage_row = (
        db_session.query(ApiUsage)
        .filter(ApiUsage.endpoint == "/openai/v1/responses")
        .order_by(ApiUsage.timestamp.desc())
        .first()
    )
    assert usage_row is not None

    document = crud_gateway_usage_search_document.get_by_api_usage_id(
        db_session, api_usage_id=str(usage_row.id)
    )
    assert document is not None
    assert "provider_name: openai" in document.searchable_text
    assert "request.instructions" not in document.searchable_text
    assert "response.output_text" not in document.searchable_text


def test_failed_gateway_requests_only_auto_index_when_failure_policy_enabled(
    db_session, test_user
):
    """Failure indexing should require a separate explicit opt-in."""
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                }
            },
            "is_default": True,
        },
        account_id=test_user.account_id,
    )
    service = OpenAIGatewayService(
        db_session, ModelGatewayAuthContext(token="t", user=test_user)
    )

    class FakeLiteLLMRateLimitError(Exception):
        status_code = 429
        message = "Rate limit exceeded"

    with (
        patch.object(settings, "model_gateway_auto_index_interactions", True),
        patch.object(settings, "model_gateway_auto_index_failed_interactions", False),
        patch.object(settings, "model_gateway_capture_content", True),
        patch(
            "preloop.services.openai_gateway.litellm.completion",
            side_effect=FakeLiteLLMRateLimitError(),
        ),
    ):
        with pytest.raises(ModelGatewayAPIError):
            service.create_response(
                {"model": "openai/gpt-5", "instructions": "Be brief", "input": "Hello"}
            )

    failed_usage = (
        db_session.query(ApiUsage)
        .filter(
            ApiUsage.endpoint == "/openai/v1/responses", ApiUsage.status_code == 429
        )
        .order_by(ApiUsage.timestamp.asc())
        .first()
    )
    assert failed_usage is not None
    assert (
        crud_gateway_usage_search_document.get_by_api_usage_id(
            db_session, api_usage_id=str(failed_usage.id)
        )
        is None
    )

    with (
        patch.object(settings, "model_gateway_auto_index_interactions", True),
        patch.object(settings, "model_gateway_auto_index_failed_interactions", True),
        patch.object(settings, "model_gateway_capture_content", True),
        patch(
            "preloop.services.openai_gateway.litellm.completion",
            side_effect=FakeLiteLLMRateLimitError(),
        ),
    ):
        with pytest.raises(ModelGatewayAPIError):
            service.create_response(
                {"model": "openai/gpt-5", "instructions": "Be brief", "input": "Hello"}
            )

    indexed_failed_usage = (
        db_session.query(ApiUsage)
        .filter(
            ApiUsage.endpoint == "/openai/v1/responses", ApiUsage.status_code == 429
        )
        .order_by(ApiUsage.timestamp.desc())
        .first()
    )
    assert indexed_failed_usage is not None

    document = crud_gateway_usage_search_document.get_by_api_usage_id(
        db_session, api_usage_id=str(indexed_failed_usage.id)
    )
    assert document is not None
    assert "outcome: error" in document.searchable_text
    assert "error_detail: Rate limit exceeded" in document.searchable_text
    assert "request.instructions: Be brief" in document.searchable_text
