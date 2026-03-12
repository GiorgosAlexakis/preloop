"""Tests for model gateway auth helpers."""

from unittest.mock import AsyncMock, patch

import pytest

from preloop.models.crud import crud_api_key
from preloop.services.model_gateway_auth import authenticate_bearer_token


from datetime import datetime
from preloop.models.models.runtime_session import RuntimeSession


@pytest.mark.asyncio
async def test_authenticate_bearer_token_preserves_api_key_context(
    db_session, test_user
):
    """Runtime API key auth should preserve the ApiKey object and context_data."""
    session_id = "12345678-1234-5678-1234-567812345678"

    runtime_session = RuntimeSession(
        id=session_id,
        account_id=test_user.account_id,
        session_source_type="flow_execution",
        session_source_id="flow-123",
        started_at=datetime.utcnow(),
    )
    db_session.add(runtime_session)
    db_session.commit()

    api_key, presented_token = crud_api_key.create_runtime_key(
        db_session,
        name="Gateway Runtime Token",
        account_id=test_user.account_id,
        user_id=test_user.id,
        context_data={
            "flow_execution_id": "flow-123",
            "runtime_session_id": session_id,
            "runtime_principal": {"type": "flow_execution", "id": "flow-123"},
        },
    )

    with patch(
        "preloop.services.model_gateway_auth.get_user_from_token_if_valid",
        new=AsyncMock(return_value=test_user),
    ):
        auth_context = await authenticate_bearer_token(presented_token, db_session)

    assert auth_context is not None
    assert auth_context.user.id == test_user.id
    assert auth_context.api_key is not None
    assert auth_context.api_key.id == api_key.id
    assert auth_context.api_key.context_data["flow_execution_id"] == "flow-123"
    assert auth_context.api_key.context_data["runtime_session_id"] == session_id
