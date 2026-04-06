import pytest
from uuid import uuid4

from preloop.models.models.flow import Flow
from preloop.models.models.user import User
from preloop.services.flow_orchestrator import FlowExecutionOrchestrator
from preloop.services.model_gateway_auth import authenticate_bearer_token


@pytest.mark.asyncio
async def test_bearer_token_end_to_end(db_session, test_flow: Flow, test_user: User):
    orch = FlowExecutionOrchestrator(db_session, test_flow.id)
    execution_id = uuid4()
    orch.execution_log = type(
        "obj", (object,), {"id": execution_id, "start_time": None}
    )()

    token, key_id = orch._create_temporary_api_token()
    assert token is not None

    res = await authenticate_bearer_token(token, db_session)
    assert res is not None
    assert res.user.id == test_user.id
