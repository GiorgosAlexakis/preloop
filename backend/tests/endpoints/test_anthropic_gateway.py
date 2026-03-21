"""Endpoint tests for the Anthropic-compatible gateway."""

from unittest.mock import patch

from preloop.api.endpoints.anthropic_gateway import get_anthropic_gateway_auth_context
from preloop.models.crud import crud_account, crud_ai_model
from preloop.services.model_gateway_auth import ModelGatewayAuthContext


def test_messages_endpoint_returns_anthropic_shape(app, client, db_session, test_user):
    """POST /anthropic/v1/messages should return minimal Anthropic-compatible shape."""
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Claude Gateway Model",
            "provider_name": "anthropic",
            "model_identifier": "claude-sonnet-4-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "anthropic/claude-sonnet-4-5",
                    "provider_adapter": "preloop",
                }
            },
        },
        account_id=test_user.account_id,
    )
    app.dependency_overrides[get_anthropic_gateway_auth_context] = lambda: (
        ModelGatewayAuthContext(token="runtime-token", user=test_user)
    )

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value={
            "id": "msg_123",
            "created": 1710000000,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello from Claude gateway",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        },
    ):
        response = client.post(
            "/anthropic/v1/messages",
            headers={
                "x-api-key": "ignored",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "anthropic/claude-sonnet-4-5",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 256,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "message"
    assert body["role"] == "assistant"
    assert body["content"][0]["text"] == "Hello from Claude gateway"
    assert body["usage"]["input_tokens"] == 3
    assert body["usage"]["output_tokens"] == 4


def test_messages_endpoint_streams_anthropic_sse(app, client, db_session, test_user):
    """POST /anthropic/v1/messages should emit Anthropic-style SSE events."""
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Claude Gateway Model",
            "provider_name": "anthropic",
            "model_identifier": "claude-sonnet-4-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "anthropic/claude-sonnet-4-5",
                    "provider_adapter": "preloop",
                }
            },
        },
        account_id=test_user.account_id,
    )
    app.dependency_overrides[get_anthropic_gateway_auth_context] = lambda: (
        ModelGatewayAuthContext(token="runtime-token", user=test_user)
    )

    with patch(
        "preloop.services.openai_gateway.litellm.completion",
        return_value=iter(
            [
                {
                    "id": "msg_123",
                    "choices": [{"index": 0, "delta": {"content": "Hello"}}],
                },
                {
                    "id": "msg_123",
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
            "/anthropic/v1/messages",
            headers={
                "x-api-key": "ignored",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "anthropic/claude-sonnet-4-5",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 256,
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: message_start" in response.text
    assert "event: content_block_delta" in response.text
    assert "event: message_delta" in response.text
    assert "event: message_stop" in response.text


def test_messages_endpoint_requires_anthropic_version(client):
    """Anthropic gateway should require anthropic-version header."""
    response = client.post(
        "/anthropic/v1/messages",
        headers={"x-api-key": "ignored"},
        json={
            "model": "anthropic/claude-sonnet-4-5",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 256,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "type": "error",
        "error": {
            "type": "invalid_request_error",
            "message": "Missing anthropic-version header",
        },
    }


def test_messages_endpoint_denies_when_account_budget_exceeded(
    app, client, db_session, test_user
):
    """Anthropic gateway should return 403 when the account hard budget would be exceeded."""
    account = crud_account.get(db_session, id=test_user.account_id)
    crud_account.update(
        db_session,
        db_obj=account,
        obj_in={"meta_data": {"model_gateway_budget": {"monthly_usd_limit": 0.00001}}},
    )
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Claude Gateway Model",
            "provider_name": "anthropic",
            "model_identifier": "claude-sonnet-4-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "model_alias": "anthropic/claude-sonnet-4-5",
                    "provider_adapter": "preloop",
                },
                "pricing": {"input_price_per_1k": 0.01, "output_price_per_1k": 0.02},
            },
        },
        account_id=test_user.account_id,
    )
    app.dependency_overrides[get_anthropic_gateway_auth_context] = lambda: (
        ModelGatewayAuthContext(token="runtime-token", user=test_user)
    )

    with patch("preloop.services.openai_gateway.litellm.completion") as mock_completion:
        response = client.post(
            "/anthropic/v1/messages",
            headers={
                "x-api-key": "ignored",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "anthropic/claude-sonnet-4-5",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 256,
            },
        )

    assert response.status_code == 403
    body = response.json()
    assert "account monthly limit reached" in body["error"]["message"]
    assert body["error"]["type"] == "permission_error"
    mock_completion.assert_not_called()
