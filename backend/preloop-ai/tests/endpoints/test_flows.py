import uuid
from zoneinfo import ZoneInfo
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pytest_mock import MockerFixture

from preloop_ai.api.endpoints import flows
from preloop_models import schemas
from preloop_models.models.account import Account

from tests.conftest import maybe_await


@pytest.fixture
def mock_account(mocker: MockerFixture) -> Account:
    """Provides a mock Account object for testing."""
    account = MagicMock(spec=Account)
    account.id = uuid.uuid4()
    account.account_id = uuid.uuid4()
    account.email = "test@example.com"
    return account


@pytest.mark.asyncio
async def test_create_flow(mock_account: Account, mocker: MockerFixture):
    """Tests that a flow is created correctly."""
    # Arrange
    flow_in = schemas.FlowCreate(
        name="Test Flow",
        description="A test flow",
        trigger_event_source="github",
        trigger_event_type="commit_to_main",
        prompt_template="Test prompt",
        ai_model_id=uuid.uuid4(),
        agent_type="openhands",
        agent_config={"agent_type": "CodeActAgent"},
        allowed_mcp_servers=[],
        allowed_mcp_tools=[],
    )

    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    flow_in.account_id = mock_account.id
    mock_crud_flow.create.return_value = schemas.FlowResponse(
        **flow_in.model_dump(),
        id=uuid.uuid4(),
        created_at=datetime.now(ZoneInfo("UTC")),
        updated_at=datetime.now(ZoneInfo("UTC")),
    )

    # Act
    result = await maybe_await(
        flows.create_flow(db=MagicMock(), flow_in=flow_in, current_user=mock_account)
    )

    # Assert
    assert result.name == flow_in.name
    mock_crud_flow.create.assert_called_once_with(
        db=mocker.ANY, flow_in=flow_in, account_id=mock_account.account_id
    )


@pytest.mark.asyncio
async def test_read_flows(mock_account: Account, mocker: MockerFixture):
    """Tests that flows are read correctly."""
    # Arrange
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get_multi.return_value = []

    # Act
    result = await maybe_await(
        flows.read_flows(db=MagicMock(), current_user=mock_account)
    )

    # Assert
    assert isinstance(result, list)
    mock_crud_flow.get_multi.assert_called_once_with(
        mocker.ANY, account_id=mock_account.account_id, skip=0, limit=100
    )


@pytest.mark.asyncio
async def test_read_flow(mock_account: Account, mocker: MockerFixture):
    """Tests that a single flow is read correctly."""
    # Arrange
    flow_id = uuid.uuid4()
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = schemas.FlowResponse(
        id=flow_id,
        name="Test Flow",
        description="A test flow",
        trigger_event_source="github",
        trigger_event_type="commit_to_main",
        prompt_template="Test prompt",
        ai_model_id=uuid.uuid4(),
        created_at=datetime.now(ZoneInfo("UTC")),
        updated_at=datetime.now(ZoneInfo("UTC")),
        account_id=mock_account.account_id,
    )

    # Act
    result = await maybe_await(
        flows.read_flow(db=MagicMock(), flow_id=flow_id, current_user=mock_account)
    )

    # Assert
    assert result.id == flow_id
    mock_crud_flow.get.assert_called_once_with(
        db=mocker.ANY, id=flow_id, account_id=mock_account.account_id
    )


@pytest.mark.asyncio
async def test_update_flow(mock_account: Account, mocker: MockerFixture):
    """Tests that a flow is updated correctly."""
    # Arrange
    flow_id = uuid.uuid4()
    flow_update = schemas.FlowUpdate(name="Updated Name", current_user=mock_account)
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_flow = MagicMock()
    mock_crud_flow.get.return_value = mock_flow
    mock_crud_flow.update.return_value = schemas.FlowResponse(
        id=flow_id,
        name=flow_update.name,
        description="A test flow",
        trigger_event_source="github",
        trigger_event_type="commit_to_main",
        prompt_template="Test prompt",
        ai_model_id=uuid.uuid4(),
        created_at=datetime.now(ZoneInfo("UTC")),
        updated_at=datetime.now(ZoneInfo("UTC")),
        account_id=mock_account.account_id,
    )

    # Act
    result = await maybe_await(
        flows.update_flow(
            db=MagicMock(),
            flow_id=flow_id,
            flow_in=flow_update,
            current_user=mock_account,
        )
    )

    # Assert
    assert result.name == flow_update.name
    mock_crud_flow.get.assert_called_once_with(
        db=mocker.ANY, id=flow_id, account_id=mock_account.account_id
    )
    mock_crud_flow.update.assert_called_once_with(
        db=mocker.ANY,
        db_obj=mock_flow,
        flow_in=flow_update,
        account_id=mock_account.account_id,
    )


@pytest.mark.asyncio
async def test_delete_flow(mock_account: Account, mocker: MockerFixture):
    """Tests that a flow is deleted correctly."""
    # Arrange
    flow_id = uuid.uuid4()
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_flow = MagicMock()
    mock_crud_flow.get.return_value = mock_flow

    # Act
    await maybe_await(
        flows.delete_flow(db=MagicMock(), flow_id=flow_id, current_user=mock_account)
    )

    # Assert
    mock_crud_flow.get.assert_called_once_with(
        db=mocker.ANY, id=flow_id, account_id=mock_account.account_id
    )
    mock_crud_flow.remove.assert_called_once_with(
        db=mocker.ANY, id=flow_id, account_id=mock_account.account_id
    )


@pytest.mark.asyncio
async def test_read_flow_not_found(mock_account: Account, mocker: MockerFixture):
    """Tests that reading a non-existent flow raises HTTPException."""
    # Arrange
    flow_id = uuid.uuid4()
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await maybe_await(
            flows.read_flow(db=MagicMock(), flow_id=flow_id, current_user=mock_account)
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_update_flow_not_found(mock_account: Account, mocker: MockerFixture):
    """Tests that updating a non-existent flow raises HTTPException."""
    # Arrange
    flow_id = uuid.uuid4()
    flow_update = schemas.FlowUpdate(name="Updated Name", current_user=mock_account)
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await maybe_await(
            flows.update_flow(
                db=MagicMock(),
                flow_id=flow_id,
                flow_in=flow_update,
                current_user=mock_account,
            )
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_delete_flow_not_found(mock_account: Account, mocker: MockerFixture):
    """Tests that deleting a non-existent flow raises HTTPException."""
    # Arrange
    flow_id = uuid.uuid4()
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await maybe_await(
            flows.delete_flow(
                db=MagicMock(), flow_id=flow_id, current_user=mock_account
            )
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_read_presets(mock_account: Account, mocker: MockerFixture):
    """Tests that flow presets are read correctly."""
    # Arrange
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    global_preset = MagicMock()
    global_preset.is_preset = True
    account_preset = MagicMock()
    account_preset.is_preset = False

    mock_crud_flow.get_multi.side_effect = [[global_preset], [account_preset]]

    # Act
    result = await maybe_await(
        flows.read_presets(db=MagicMock(), current_user=mock_account)
    )

    # Assert
    assert len(result) == 2
    assert result[0] == global_preset
    assert result[1] == account_preset


@pytest.mark.asyncio
async def test_clone_preset(mock_account: Account, mocker: MockerFixture):
    """Tests that cloning a preset works correctly."""
    # Arrange
    flow_id = uuid.uuid4()
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )

    # Create a simple object with __dict__ support
    class PresetObj:
        pass

    preset = PresetObj()
    preset.id = flow_id
    preset.name = "Preset Flow"
    preset.description = "A preset"
    preset.is_preset = True
    preset.trigger_event_source = "github"
    preset.trigger_event_type = "commit"
    preset.prompt_template = "test"
    preset.ai_model_id = uuid.uuid4()
    preset.agent_type = "openhands"
    preset.agent_config = {"agent_type": "CodeActAgent"}
    preset.allowed_mcp_servers = []
    preset.allowed_mcp_tools = []

    mock_crud_flow.get.return_value = preset

    # Convert mock_account.id to string for validation
    mock_account.id = str(mock_account.id)

    cloned_flow = MagicMock()
    cloned_flow.name = "Copy of Preset Flow"
    mock_crud_flow.create.return_value = cloned_flow

    # Act
    result = await maybe_await(
        flows.clone_preset(db=MagicMock(), flow_id=flow_id, current_user=mock_account)
    )

    # Assert
    assert result == cloned_flow
    mock_crud_flow.create.assert_called_once()


@pytest.mark.asyncio
async def test_clone_preset_not_found(mock_account: Account, mocker: MockerFixture):
    """Tests that cloning a non-existent preset raises HTTPException."""
    # Arrange
    flow_id = uuid.uuid4()
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await maybe_await(
            flows.clone_preset(
                db=MagicMock(), flow_id=flow_id, current_user=mock_account
            )
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_clone_preset_not_a_preset(mock_account: Account, mocker: MockerFixture):
    """Tests that cloning a non-preset flow raises HTTPException."""
    # Arrange
    flow_id = uuid.uuid4()
    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )

    flow = MagicMock()
    flow.is_preset = False
    mock_crud_flow.get.return_value = flow

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await maybe_await(
            flows.clone_preset(
                db=MagicMock(), flow_id=flow_id, current_user=mock_account
            )
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_read_flow_executions(mock_account: Account, mocker: MockerFixture):
    """Tests that flow executions are read correctly."""
    # Arrange
    mock_crud_flow_execution = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )
    mock_crud_flow_execution.get_multi.return_value = []

    # Act
    result = await maybe_await(
        flows.read_flow_executions(db=MagicMock(), current_user=mock_account)
    )

    # Assert
    assert isinstance(result, list)
    mock_crud_flow_execution.get_multi.assert_called_once_with(
        mocker.ANY, account_id=mock_account.account_id, skip=0, limit=100
    )


@pytest.mark.asyncio
async def test_read_flow_execution(mock_account: Account, mocker: MockerFixture):
    """Tests that reading a single flow execution works correctly."""
    # Arrange
    execution_id = uuid.uuid4()
    mock_crud_flow_execution = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )

    execution = MagicMock()
    execution.id = execution_id
    mock_crud_flow_execution.get.return_value = execution

    # Act
    result = await maybe_await(
        flows.read_flow_execution(
            db=MagicMock(), execution_id=execution_id, current_user=mock_account
        )
    )

    # Assert
    assert result == execution
    mock_crud_flow_execution.get.assert_called_once_with(
        db=mocker.ANY, id=execution_id, account_id=mock_account.account_id
    )


@pytest.mark.asyncio
async def test_read_flow_execution_not_found(
    mock_account: Account, mocker: MockerFixture
):
    """Tests that reading a non-existent flow execution raises HTTPException."""
    # Arrange
    execution_id = uuid.uuid4()
    mock_crud_flow_execution = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )
    mock_crud_flow_execution.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await maybe_await(
            flows.read_flow_execution(
                db=MagicMock(), execution_id=execution_id, current_user=mock_account
            )
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_send_execution_command_execution_not_found(
    mock_account: Account, mocker: MockerFixture
):
    """Tests that sending a command to non-existent execution raises HTTPException."""
    # Arrange
    execution_id = uuid.uuid4()
    mock_crud_flow_execution = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )
    mock_crud_flow_execution.get.return_value = None

    # Mock get_nats_client
    mocker.patch(
        "preloop_sync.services.event_bus.get_nats_client",
        return_value=MagicMock(),
    )

    command_data = schemas.FlowExecutionCommand(
        command="stop",
        payload={},
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await maybe_await(
            flows.send_execution_command(
                db=MagicMock(),
                execution_id=execution_id,
                command_data=command_data,
                current_user=mock_account,
            )
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_send_execution_command_stop_success(
    mock_account: Account, mocker: MockerFixture
):
    """Tests that sending a stop command works correctly."""
    # Arrange
    execution_id = uuid.uuid4()
    flow_id = uuid.uuid4()

    mock_execution = MagicMock()
    mock_execution.id = execution_id
    mock_execution.flow_id = flow_id
    mock_execution.status = "RUNNING"
    mock_execution.agent_session_reference = "test-session-123"

    mock_flow = MagicMock()
    mock_flow.agent_type = "codex"

    mock_crud_flow_execution = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )
    mock_crud_flow_execution.get.return_value = mock_execution
    mock_crud_flow_execution.update.return_value = mock_execution

    mock_crud_flow = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = mock_flow

    # Mock get_nats_client
    mock_nats_client = MagicMock()
    mock_get_nats_client = mocker.patch(
        "preloop_sync.services.event_bus.get_nats_client",
        return_value=mock_nats_client,
    )

    # Mock CodexAgent
    mock_agent = MagicMock()
    mock_agent.get_logs = mocker.AsyncMock(return_value=["log line 1", "log line 2"])
    mock_agent.stop = mocker.AsyncMock()
    mock_codex_agent_class = mocker.patch(
        "preloop_ai.agents.codex.CodexAgent",
        return_value=mock_agent,
    )

    # Mock FlowExecutionOrchestrator.send_command
    mock_send_command = mocker.patch(
        "preloop_ai.services.flow_orchestrator.FlowExecutionOrchestrator.send_command",
        new=mocker.AsyncMock(),
    )

    command_data = schemas.FlowExecutionCommand(
        command="stop",
        payload={},
    )

    # Act
    result = await maybe_await(
        flows.send_execution_command(
            db=MagicMock(),
            execution_id=execution_id,
            command_data=command_data,
            current_user=mock_account,
        )
    )

    # Assert
    assert result == {"status": "stopped"}
    mock_get_nats_client.assert_called_once()
    mock_agent.stop.assert_called_once_with("test-session-123")

    # Update is called twice: once for logs, once for status
    assert mock_crud_flow_execution.update.call_count == 2

    # Verify the final update call has status='STOPPED'
    final_call = mock_crud_flow_execution.update.call_args
    assert final_call.kwargs["obj_in"].status == "STOPPED"
    assert final_call.kwargs["obj_in"].error_message == "Manually stopped by user"

    # Verify send_command was called with nats_client
    mock_send_command.assert_called_once()
    call_kwargs = mock_send_command.call_args.kwargs
    assert call_kwargs["execution_id"] == str(execution_id)
    assert call_kwargs["command"] == "stop"
    assert call_kwargs["nats_client"] == mock_nats_client


@pytest.mark.asyncio
async def test_send_execution_command_other_command_success(
    mock_account: Account, mocker: MockerFixture
):
    """Tests that sending a non-stop command works correctly via NATS."""
    # Arrange
    execution_id = uuid.uuid4()

    mock_execution = MagicMock()
    mock_execution.id = execution_id

    mock_crud_flow_execution = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )
    mock_crud_flow_execution.get.return_value = mock_execution

    # Mock get_nats_client
    mock_nats_client = MagicMock()
    mock_get_nats_client = mocker.patch(
        "preloop_sync.services.event_bus.get_nats_client",
        return_value=mock_nats_client,
    )

    # Mock FlowExecutionOrchestrator.send_command
    mock_send_command = mocker.patch(
        "preloop_ai.services.flow_orchestrator.FlowExecutionOrchestrator.send_command",
        new=mocker.AsyncMock(),
    )

    command_data = schemas.FlowExecutionCommand(
        command="send_message",
        payload={"message": "test message"},
    )

    # Act
    result = await maybe_await(
        flows.send_execution_command(
            db=MagicMock(),
            execution_id=execution_id,
            command_data=command_data,
            current_user=mock_account,
        )
    )

    # Assert
    assert result == {"status": "command_sent"}
    mock_get_nats_client.assert_called_once()

    # Verify send_command was called with nats_client
    mock_send_command.assert_called_once()
    call_kwargs = mock_send_command.call_args.kwargs
    assert call_kwargs["execution_id"] == str(execution_id)
    assert call_kwargs["command"] == "send_message"
    assert call_kwargs["payload"] == {"message": "test message"}
    assert call_kwargs["nats_client"] == mock_nats_client


@pytest.mark.asyncio
async def test_send_execution_command_nats_failure(
    mock_account: Account, mocker: MockerFixture
):
    """Tests that command sending fails gracefully when NATS is unavailable."""
    # Arrange
    execution_id = uuid.uuid4()

    mock_execution = MagicMock()
    mock_execution.id = execution_id

    mock_crud_flow_execution = mocker.patch(
        "preloop_ai.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )
    mock_crud_flow_execution.get.return_value = mock_execution

    # Mock get_nats_client to raise an exception
    mocker.patch(
        "preloop_sync.services.event_bus.get_nats_client",
        side_effect=Exception("NATS connection failed"),
    )

    # Mock FlowExecutionOrchestrator.send_command to raise an exception
    mocker.patch(
        "preloop_ai.services.flow_orchestrator.FlowExecutionOrchestrator.send_command",
        new=mocker.AsyncMock(side_effect=RuntimeError("NATS client not available")),
    )

    command_data = schemas.FlowExecutionCommand(
        command="send_message",
        payload={"message": "test message"},
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await maybe_await(
            flows.send_execution_command(
                db=MagicMock(),
                execution_id=execution_id,
                command_data=command_data,
                current_user=mock_account,
            )
        )

    assert exc_info.value.status_code == 500
    assert "Failed to send command" in str(exc_info.value.detail)
