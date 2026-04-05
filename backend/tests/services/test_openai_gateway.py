"""Tests for the OpenAI-compatible gateway service."""

import pytest
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from preloop.models.models.api_usage import ApiUsage
from preloop.models.crud import (
    crud_ai_model,
    crud_runtime_session,
)
from preloop.models.crud import crud_api_key
from preloop.services.model_gateway_auth import ModelGatewayAuthContext
from preloop.services.model_gateway_errors import ModelGatewayAPIError
from preloop.services.openai_gateway import OpenAIGatewayService


def _parse_sse_payload(event: str):
    data_line = next(line for line in event.splitlines() if line.startswith("data: "))
    payload = data_line.removeprefix("data: ")
    if payload == "[DONE]":
        return payload
    return json.loads(payload)


def test_call_litellm_uses_injected_upstream_backend():
    auth_context = ModelGatewayAuthContext(
        token="token",
        user=SimpleNamespace(id="user-1", account_id="account-1"),
    )
    upstream_backend = MagicMock()
    service = OpenAIGatewayService(
        MagicMock(), auth_context, upstream_backend=upstream_backend
    )
    ai_model = SimpleNamespace(
        provider_name="openai", model_identifier="gpt-5", api_endpoint=None
    )

    with patch(
        "preloop.services.openai_gateway.get_secret_service"
    ) as mock_secret_service:
        mock_secret_service.return_value.resolve_ai_model_api_key.return_value = (
            SimpleNamespace(value="provider-secret")
        )
        service._call_litellm(
            ai_model,
            messages=[{"role": "user", "content": "Hello"}],
            payload={"temperature": 0.2},
            provider="openai",
        )

    upstream_backend.completion.assert_called_once_with(
        model="openai/gpt-5",
        messages=[{"role": "user", "content": "Hello"}],
        api_key="provider-secret",
        timeout=600,
        temperature=0.2,
    )


def test_call_litellm_allows_bedrock_ambient_credentials():
    auth_context = ModelGatewayAuthContext(
        token="token",
        user=SimpleNamespace(id="user-1", account_id="account-1"),
    )
    upstream_backend = MagicMock()
    service = OpenAIGatewayService(
        MagicMock(), auth_context, upstream_backend=upstream_backend
    )
    ai_model = SimpleNamespace(
        provider_name="bedrock",
        model_identifier="us.anthropic.claude-opus-4-6-v1",
        api_endpoint=None,
        meta_data={"provider_runtime": {"region": "us-east-1"}},
    )

    with patch(
        "preloop.services.openai_gateway.get_secret_service"
    ) as mock_secret_service:
        mock_secret_service.return_value.resolve_ai_model_api_key.return_value = None
        service._call_litellm(
            ai_model,
            messages=[{"role": "user", "content": "Hello"}],
            payload={},
            provider="openai",
        )

    upstream_backend.completion.assert_called_once_with(
        model="bedrock/us.anthropic.claude-opus-4-6-v1",
        messages=[{"role": "user", "content": "Hello"}],
        timeout=600,
        aws_region_name="us-east-1",
    )


def test_call_litellm_passes_imported_bedrock_credentials():
    auth_context = ModelGatewayAuthContext(
        token="token",
        user=SimpleNamespace(id="user-1", account_id="account-1"),
    )
    upstream_backend = MagicMock()
    service = OpenAIGatewayService(
        MagicMock(), auth_context, upstream_backend=upstream_backend
    )
    ai_model = SimpleNamespace(
        provider_name="bedrock",
        model_identifier="us.anthropic.claude-opus-4-6-v1",
        api_endpoint=None,
        meta_data={"provider_runtime": {"region": "us-east-1"}},
    )

    with patch(
        "preloop.services.openai_gateway.get_secret_service"
    ) as mock_secret_service:
        mock_secret_service.return_value.resolve_ai_model_api_key.return_value = (
            SimpleNamespace(
                value=json.dumps(
                    {
                        "aws_access_key_id": "AKIA_TEST",
                        "aws_secret_access_key": "secret-test",
                        "aws_session_token": "session-test",
                        "aws_region_name": "eu-central-1",
                    }
                )
            )
        )
        service._call_litellm(
            ai_model,
            messages=[{"role": "user", "content": "Hello"}],
            payload={},
            provider="openai",
        )

    upstream_backend.completion.assert_called_once_with(
        model="bedrock/us.anthropic.claude-opus-4-6-v1",
        messages=[{"role": "user", "content": "Hello"}],
        timeout=600,
        aws_access_key_id="AKIA_TEST",
        aws_secret_access_key="secret-test",
        aws_session_token="session-test",
        aws_region_name="eu-central-1",
    )


def test_create_response_uses_openai_codex_adapter():
    auth_context = ModelGatewayAuthContext(
        token="token",
        user=SimpleNamespace(id="user-1", account_id="account-1"),
    )
    service = OpenAIGatewayService(MagicMock(), auth_context)
    ai_model = SimpleNamespace(
        id="model-1",
        provider_name="openai-codex",
        model_identifier="gpt-5.4",
        api_endpoint="https://chatgpt.com/backend-api/codex",
    )

    with (
        patch.object(service, "_resolve_requested_model", return_value=ai_model),
        patch.object(service, "_check_budget", return_value=None),
        patch.object(service, "_record_gateway_request"),
        patch.object(service, "_emit_gateway_request_started"),
        patch.object(
            service,
            "_create_openai_codex_response",
            return_value={
                "id": "resp_codex_1",
                "created_at": 1234,
                "output": [
                    {
                        "id": "msg_1",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {"type": "output_text", "text": "Hello from Codex"}
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 3,
                    "output_tokens": 4,
                    "total_tokens": 7,
                },
                "output_text": "Hello from Codex",
            },
        ) as mock_create_codex,
        patch.object(service, "_call_litellm") as mock_call_litellm,
    ):
        response = service.create_response({"model": "openai/gpt-5.4", "input": "Hi"})

    mock_create_codex.assert_called_once_with(
        ai_model, {"model": "openai/gpt-5.4", "input": "Hi"}
    )
    mock_call_litellm.assert_not_called()
    assert response["model"] == "openai/gpt-5.4"
    assert response["output_text"] == "Hello from Codex"
    assert response["usage"]["total_tokens"] == 7


def test_stream_response_emits_output_item_before_text_deltas():
    auth_context = ModelGatewayAuthContext(
        token="token",
        user=SimpleNamespace(id="user-1", account_id="account-1"),
    )
    service = OpenAIGatewayService(MagicMock(), auth_context)
    ai_model = SimpleNamespace(id="model-1", provider_name="openai")
    upstream_stream = iter(
        [
            {
                "choices": [{"delta": {"content": "Hello"}}],
            },
            {
                "choices": [{"delta": {"content": " world"}}],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                },
            },
        ]
    )

    with (
        patch.object(service, "_resolve_requested_model", return_value=ai_model),
        patch.object(service, "_check_budget", return_value=None),
        patch.object(service, "_call_litellm", return_value=upstream_stream),
        patch.object(service, "_record_gateway_request"),
    ):
        events = [
            _parse_sse_payload(event)
            for event in service.stream_response(
                {"model": "openai/gpt-5", "input": "Hi"}
            )
        ]

    event_types = [event["type"] for event in events[:-1]]
    assert event_types[:3] == [
        "response.created",
        "response.output_item.added",
        "response.content_part.added",
    ]
    assert event_types[3:5] == [
        "response.output_text.delta",
        "response.output_text.delta",
    ]
    assert event_types[5:] == [
        "response.output_text.done",
        "response.content_part.done",
        "response.output_item.done",
        "response.completed",
    ]
    assert events[1]["item"]["id"] == events[3]["item_id"]
    assert events[2]["part"]["type"] == "output_text"
    assert events[7]["item"]["content"][0]["text"] == "Hello world"
    assert events[8]["response"]["output_text"] == "Hello world"
    assert events[8]["response"]["usage"]["total_tokens"] == 5
    assert events[-1] == "[DONE]"


def test_stream_response_ignores_null_text_deltas():
    """Null upstream text chunks should not leak as literal 'None' output."""
    auth_context = ModelGatewayAuthContext(
        token="token",
        user=SimpleNamespace(id="user-1", account_id="account-1"),
    )
    service = OpenAIGatewayService(MagicMock(), auth_context)
    ai_model = SimpleNamespace(id="model-1", provider_name="openai")
    upstream_stream = iter(
        [
            {
                "choices": [{"delta": {"content": "Hello"}}],
            },
            {
                "choices": [{"delta": {"content": None}}],
            },
            {
                "choices": [{"delta": {"content": " world"}}],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                },
            },
        ]
    )

    with (
        patch.object(service, "_resolve_requested_model", return_value=ai_model),
        patch.object(service, "_check_budget", return_value=None),
        patch.object(service, "_call_litellm", return_value=upstream_stream),
        patch.object(service, "_record_gateway_request"),
    ):
        events = [
            _parse_sse_payload(event)
            for event in service.stream_response(
                {"model": "openai/gpt-5", "input": "Hi"}
            )
        ]

    text_deltas = [
        event["delta"]
        for event in events
        if isinstance(event, dict) and event.get("type") == "response.output_text.delta"
    ]
    assert text_deltas == ["Hello", " world"]
    completed = next(
        event
        for event in events
        if isinstance(event, dict) and event.get("type") == "response.completed"
    )
    assert completed["response"]["output_text"] == "Hello world"
    assert "None" not in completed["response"]["output_text"]


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


def test_create_response_uses_litellm_pricing_when_metadata_missing(
    db_session, test_user
):
    """Gateway request costing should fall back to LiteLLM's model pricing map."""
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5.4",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "openai/gpt-5.4",
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

    with (
        patch(
            "preloop.services.openai_gateway.litellm.completion",
            return_value=litellm_response,
        ) as mock_completion,
        patch(
            "preloop.services.model_pricing.litellm.completion_cost",
            return_value=0.00579,
        ) as mock_completion_cost,
        patch(
            "preloop.services.model_pricing.litellm.cost_per_token",
            return_value=(0.00123, 0.00456),
        ) as mock_cost_per_token,
    ):
        payload = service.create_response(
            {
                "model": "openai/gpt-5.4",
                "instructions": "Be brief",
                "input": "Hello",
            }
        )

    assert payload["output_text"] == "Gateway says hello"
    mock_completion.assert_called_once()
    mock_cost_per_token.assert_called_once_with(
        model="openai/gpt-5.4",
        prompt_tokens=4,
        completion_tokens=1024,
    )
    mock_completion_cost.assert_called_once_with(
        model="openai/gpt-5.4",
        completion_response={"usage": litellm_response["usage"]},
    )

    usage_row = (
        db_session.query(ApiUsage)
        .filter(ApiUsage.endpoint == "/openai/v1/responses")
        .order_by(ApiUsage.timestamp.desc())
        .first()
    )
    assert usage_row is not None
    assert usage_row.estimated_cost == 0.00579
    assert usage_row.meta_data["usage_details"] == litellm_response["usage"]


def test_create_response_forwards_tools_and_returns_function_call_output(
    db_session, test_user
):
    """Responses tool definitions should be forwarded and tool calls preserved."""
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
    tool_payload = {
        "type": "function",
        "name": "get_pull_request",
        "description": "Fetch one pull request",
        "parameters": {"type": "object", "properties": {}},
    }

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value={
            "id": "chatcmpl_123",
            "created": 1710000000,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_pull_request",
                                    "arguments": '{"pull_request":"owner/repo#1"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        },
    ) as mock_completion:
        payload = service.create_response(
            {
                "model": "openai/gpt-5",
                "input": "Review this PR",
                "tools": [tool_payload],
                "tool_choice": {"type": "function", "name": "get_pull_request"},
            }
        )

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get_pull_request",
                "description": "Fetch one pull request",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    assert kwargs["tool_choice"] == {
        "type": "function",
        "function": {"name": "get_pull_request"},
    }
    assert payload["output_text"] == ""
    assert payload["output"][0]["type"] == "function_call"
    assert payload["output"][0]["call_id"] == "call_123"
    assert payload["output"][0]["name"] == "get_pull_request"


def test_create_response_preserves_responses_tool_history_in_chat_messages(
    db_session, test_user
):
    """Responses function call history should remain structured for the upstream model."""
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

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value={
            "id": "chatcmpl_123",
            "created": 1710000000,
            "choices": [{"message": {"role": "assistant", "content": "continue"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ) as mock_completion:
        service.create_response(
            {
                "model": "openai/gpt-5",
                "input": [
                    {
                        "role": "assistant",
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Starting review"}],
                    },
                    {
                        "type": "function_call",
                        "name": "mcp__preloop__update_pull_request",
                        "call_id": "call_eyes",
                        "arguments": '{"pull_request":"mr-22","add_reaction":"eyes"}',
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "call_eyes",
                        "output": '{"result":"reaction added"}',
                    },
                ],
            }
        )

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["messages"] == [
        {"role": "assistant", "content": "Starting review"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_eyes",
                    "type": "function",
                    "function": {
                        "name": "mcp__preloop__update_pull_request",
                        "arguments": '{"pull_request":"mr-22","add_reaction":"eyes"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_eyes",
            "content": '{"result":"reaction added"}',
        },
    ]


def test_create_response_coalesces_multi_tool_turns_for_upstream(db_session, test_user):
    """Contiguous Responses tool calls should become one assistant tool_calls turn."""
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

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value={
            "id": "chatcmpl_123",
            "created": 1710000000,
            "choices": [{"message": {"role": "assistant", "content": "continue"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ) as mock_completion:
        service.create_response(
            {
                "model": "openai/gpt-5",
                "input": [
                    {
                        "role": "assistant",
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Starting review"}],
                    },
                    {
                        "type": "function_call",
                        "name": "mcp__preloop__update_pull_request",
                        "call_id": "call_eyes",
                        "arguments": '{"pull_request":"mr-22","add_reaction":"eyes"}',
                    },
                    {
                        "type": "function_call",
                        "name": "mcp__preloop__get_pull_request",
                        "call_id": "call_fetch",
                        "arguments": '{"pull_request":"mr-22","include_diff":true}',
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "call_eyes",
                        "output": '{"result":"reaction added"}',
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "call_fetch",
                        "output": '{"result":"pull request fetched"}',
                    },
                ],
            }
        )

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["messages"] == [
        {"role": "assistant", "content": "Starting review"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_eyes",
                    "type": "function",
                    "function": {
                        "name": "mcp__preloop__update_pull_request",
                        "arguments": '{"pull_request":"mr-22","add_reaction":"eyes"}',
                    },
                },
                {
                    "id": "call_fetch",
                    "type": "function",
                    "function": {
                        "name": "mcp__preloop__get_pull_request",
                        "arguments": '{"pull_request":"mr-22","include_diff":true}',
                    },
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_eyes",
            "content": '{"result":"reaction added"}',
        },
        {
            "role": "tool",
            "tool_call_id": "call_fetch",
            "content": '{"result":"pull request fetched"}',
        },
    ]


def test_create_response_rejects_incomplete_tool_history(db_session, test_user):
    """Malformed Responses tool history should fail locally before upstream."""
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
            match="tool_call_ids did not have response messages: call_eyes",
        ):
            service.create_response(
                {
                    "model": "openai/gpt-5",
                    "input": [
                        {
                            "type": "function_call",
                            "name": "mcp__preloop__update_pull_request",
                            "call_id": "call_eyes",
                            "arguments": '{"pull_request":"mr-22","add_reaction":"eyes"}',
                        },
                        {
                            "role": "assistant",
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "I should not appear before tool output",
                                }
                            ],
                        },
                    ],
                }
            )

    mock_completion.assert_not_called()


def test_create_response_wraps_flat_custom_tools_for_upstream(db_session, test_user):
    """Flat Responses custom tools should be wrapped in the nested custom block."""
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

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value={
            "id": "chatcmpl_123",
            "created": 1710000000,
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ) as mock_completion:
        service.create_response(
            {
                "model": "openai/gpt-5",
                "input": "Use the available tools",
                "tools": [
                    {
                        "type": "custom",
                        "name": "get_pull_request",
                        "description": "Fetch one pull request",
                        "input_schema": {"type": "object"},
                    }
                ],
            }
        )

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["tools"] == [
        {
            "type": "custom",
            "custom": {
                "name": "get_pull_request",
                "description": "Fetch one pull request",
                "input_schema": {"type": "object"},
            },
        }
    ]


def test_create_response_maps_custom_grammar_definition_for_upstream(
    db_session, test_user
):
    """Grammar custom tools should nest grammar details under format.grammar."""
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

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value={
            "id": "chatcmpl_123",
            "created": 1710000000,
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ) as mock_completion:
        service.create_response(
            {
                "model": "openai/gpt-5",
                "input": "Use the grammar tool",
                "tools": [
                    {
                        "type": "custom",
                        "name": "code_exec",
                        "description": "Executes arbitrary Python code.",
                        "format": {
                            "type": "grammar",
                            "syntax": "lark",
                            "definition": 'start: "hello"',
                        },
                    }
                ],
            }
        )

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["tools"][0]["type"] == "custom"
    assert kwargs["tools"][0]["custom"]["format"]["type"] == "grammar"
    assert kwargs["tools"][0]["custom"]["format"]["grammar"] == {
        "syntax": "lark",
        "definition": 'start: "hello"',
    }
    assert "syntax" not in kwargs["tools"][0]["custom"]["format"]
    assert "definition" not in kwargs["tools"][0]["custom"]["format"]


def test_create_response_drops_unsupported_hosted_tools_for_upstream(
    db_session, test_user
):
    """Hosted Responses tools should be filtered out before calling LiteLLM."""
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

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value={
            "id": "chatcmpl_123",
            "created": 1710000000,
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ) as mock_completion:
        service.create_response(
            {
                "model": "openai/gpt-5",
                "input": "Use tools",
                "tools": [
                    {"type": "web_search"},
                    {
                        "type": "function",
                        "name": "get_pull_request",
                        "description": "Fetch one pull request",
                        "parameters": {"type": "object", "properties": {}},
                    },
                ],
            }
        )

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get_pull_request",
                "description": "Fetch one pull request",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
