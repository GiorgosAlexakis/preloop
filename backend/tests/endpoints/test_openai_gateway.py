"""Endpoint tests for the OpenAI-compatible gateway."""

from unittest.mock import patch

from preloop.api.endpoints.openai_gateway import get_model_gateway_auth_context
from preloop.models.crud import crud_account, crud_ai_model, crud_api_key
from preloop.services.model_gateway_auth import ModelGatewayAuthContext


def test_list_models_endpoint_returns_gateway_models(
    app, client, db_session, test_user
):
    """GET /openai/v1/models should return gateway-enabled model aliases."""
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
    api_key, presented_token = crud_api_key.create_runtime_key(
        db_session,
        name="Gateway Runtime Token",
        account_id=test_user.account_id,
        user_id=test_user.id,
        context_data={"flow_execution_id": "flow-123"},
    )
    app.dependency_overrides[get_model_gateway_auth_context] = (
        lambda: ModelGatewayAuthContext(
            token=presented_token, user=test_user, api_key=api_key
        )
    )

    response = client.get(
        "/openai/v1/models", headers={"Authorization": "Bearer ignored"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert body["data"][0]["id"] == "openai/gpt-5"


def test_chat_completions_endpoint_returns_openai_shape(
    app, client, db_session, test_user
):
    """POST /openai/v1/chat/completions should return minimal OpenAI-compatible shape."""
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
    app.dependency_overrides[get_model_gateway_auth_context] = (
        lambda: ModelGatewayAuthContext(token="runtime-token", user=test_user)
    )

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value={
            "id": "chatcmpl_123",
            "created": 1710000000,
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello from gateway"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        },
    ):
        response = client.post(
            "/openai/v1/chat/completions",
            headers={"Authorization": "Bearer ignored"},
            json={
                "model": "openai/gpt-5",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Hello from gateway"
    assert body["usage"]["total_tokens"] == 7


def test_chat_completions_endpoint_rejects_omitted_model_without_gateway_default(
    app, client, db_session, test_user
):
    """Omitted model should not silently use a non-gateway default."""
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
    app.dependency_overrides[get_model_gateway_auth_context] = (
        lambda: ModelGatewayAuthContext(token="runtime-token", user=test_user)
    )

    with patch("preloop.services.openai_gateway.litellm.completion") as mock_completion:
        response = client.post(
            "/openai/v1/chat/completions",
            headers={"Authorization": "Bearer ignored"},
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == (
        "No gateway-enabled default model configured"
    )
    mock_completion.assert_not_called()


def test_chat_completions_endpoint_denies_when_account_budget_exceeded(
    app, client, db_session, test_user
):
    """Gateway should return 403 when the account hard budget would be exceeded."""
    account = crud_account.get(db_session, id=test_user.account_id)
    crud_account.update(
        db_session,
        db_obj=account,
        obj_in={"meta_data": {"model_gateway_budget": {"monthly_usd_limit": 0.00001}}},
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
        },
        account_id=test_user.account_id,
    )
    app.dependency_overrides[get_model_gateway_auth_context] = (
        lambda: ModelGatewayAuthContext(token="runtime-token", user=test_user)
    )

    with patch("preloop.services.openai_gateway.litellm.completion") as mock_completion:
        response = client.post(
            "/openai/v1/chat/completions",
            headers={"Authorization": "Bearer ignored"},
            json={
                "model": "openai/gpt-5",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

    assert response.status_code == 403
    body = response.json()
    assert "account monthly limit reached" in body["error"]["message"]
    assert body["error"]["type"] == "permission_error"
    mock_completion.assert_not_called()


def test_chat_completions_endpoint_returns_openai_error_envelope_for_upstream_failures(
    app, client, db_session, test_user
):
    """Gateway failures should match the OpenAI client error shape."""
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
    app.dependency_overrides[get_model_gateway_auth_context] = (
        lambda: ModelGatewayAuthContext(token="runtime-token", user=test_user)
    )

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        side_effect=Exception("upstream exploded"),
    ):
        response = client.post(
            "/openai/v1/chat/completions",
            headers={"Authorization": "Bearer ignored"},
            json={
                "model": "openai/gpt-5",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "message": "Gateway upstream error: upstream exploded",
            "type": "api_error",
            "param": None,
            "code": None,
        }
    }


def test_chat_completions_endpoint_streams_sse(app, client, db_session, test_user):
    """Streaming chat completions should return SSE chunks and DONE."""
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
    app.dependency_overrides[get_model_gateway_auth_context] = (
        lambda: ModelGatewayAuthContext(token="runtime-token", user=test_user)
    )

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value=iter(
            [
                {
                    "id": "chatcmpl_123",
                    "created": 1710000000,
                    "choices": [{"index": 0, "delta": {"content": "Hello"}}],
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
        ),
    ):
        response = client.post(
            "/openai/v1/chat/completions",
            headers={"Authorization": "Bearer ignored"},
            json={
                "model": "openai/gpt-5",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "chat.completion.chunk" in response.text
    assert "data: [DONE]" in response.text


def test_responses_endpoint_streams_sse(app, client, db_session, test_user):
    """Streaming responses should emit response.created and response.completed events."""
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
    app.dependency_overrides[get_model_gateway_auth_context] = (
        lambda: ModelGatewayAuthContext(token="runtime-token", user=test_user)
    )

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value=iter(
            [
                {
                    "id": "chatcmpl_123",
                    "created": 1710000000,
                    "choices": [{"index": 0, "delta": {"content": "Hello"}}],
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
        ),
    ):
        response = client.post(
            "/openai/v1/responses",
            headers={"Authorization": "Bearer ignored"},
            json={
                "model": "openai/gpt-5",
                "input": "Hello",
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "response.created" in response.text
    assert "response.completed" in response.text
    assert "data: [DONE]" in response.text
