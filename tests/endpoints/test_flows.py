import uuid
from zoneinfo import ZoneInfo
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pytest_mock import MockerFixture

from spacebridge.api.endpoints import flows
from spacemodels import schemas
from spacemodels.models.account import Account


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
        "spacebridge.api.endpoints.flows.crud_flow",
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
    result = await flows.create_flow(
        db=MagicMock(), flow_in=flow_in, current_user=mock_account
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
        "spacebridge.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get_multi.return_value = []

    # Act
    result = await flows.read_flows(db=MagicMock(), current_user=mock_account)

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
        "spacebridge.api.endpoints.flows.crud_flow",
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
    result = await flows.read_flow(
        db=MagicMock(), flow_id=flow_id, current_user=mock_account
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
        "spacebridge.api.endpoints.flows.crud_flow",
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
    result = await flows.update_flow(
        db=MagicMock(),
        flow_id=flow_id,
        flow_in=flow_update,
        current_user=mock_account,
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
        "spacebridge.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_flow = MagicMock()
    mock_crud_flow.get.return_value = mock_flow

    # Act
    await flows.delete_flow(db=MagicMock(), flow_id=flow_id, current_user=mock_account)

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
        "spacebridge.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await flows.read_flow(
            db=MagicMock(), flow_id=flow_id, current_user=mock_account
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
        "spacebridge.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await flows.update_flow(
            db=MagicMock(),
            flow_id=flow_id,
            flow_in=flow_update,
            current_user=mock_account,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_delete_flow_not_found(mock_account: Account, mocker: MockerFixture):
    """Tests that deleting a non-existent flow raises HTTPException."""
    # Arrange
    flow_id = uuid.uuid4()
    mock_crud_flow = mocker.patch(
        "spacebridge.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await flows.delete_flow(
            db=MagicMock(), flow_id=flow_id, current_user=mock_account
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_read_presets(mock_account: Account, mocker: MockerFixture):
    """Tests that flow presets are read correctly."""
    # Arrange
    mock_crud_flow = mocker.patch(
        "spacebridge.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    global_preset = MagicMock()
    global_preset.is_preset = True
    account_preset = MagicMock()
    account_preset.is_preset = False

    mock_crud_flow.get_multi.side_effect = [[global_preset], [account_preset]]

    # Act
    result = await flows.read_presets(db=MagicMock(), current_user=mock_account)

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
        "spacebridge.api.endpoints.flows.crud_flow",
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
    result = await flows.clone_preset(
        db=MagicMock(), flow_id=flow_id, current_user=mock_account
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
        "spacebridge.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await flows.clone_preset(
            db=MagicMock(), flow_id=flow_id, current_user=mock_account
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_clone_preset_not_a_preset(mock_account: Account, mocker: MockerFixture):
    """Tests that cloning a non-preset flow raises HTTPException."""
    # Arrange
    flow_id = uuid.uuid4()
    mock_crud_flow = mocker.patch(
        "spacebridge.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )

    flow = MagicMock()
    flow.is_preset = False
    mock_crud_flow.get.return_value = flow

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await flows.clone_preset(
            db=MagicMock(), flow_id=flow_id, current_user=mock_account
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_read_flow_executions(mock_account: Account, mocker: MockerFixture):
    """Tests that flow executions are read correctly."""
    # Arrange
    mock_crud_flow_execution = mocker.patch(
        "spacebridge.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )
    mock_crud_flow_execution.get_multi.return_value = []

    # Act
    result = await flows.read_flow_executions(db=MagicMock(), current_user=mock_account)

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
        "spacebridge.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )

    execution = MagicMock()
    execution.id = execution_id
    mock_crud_flow_execution.get.return_value = execution

    # Act
    result = await flows.read_flow_execution(
        db=MagicMock(), execution_id=execution_id, current_user=mock_account
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
        "spacebridge.api.endpoints.flows.crud_flow_execution",
        new_callable=MagicMock,
    )
    mock_crud_flow_execution.get.return_value = None

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await flows.read_flow_execution(
            db=MagicMock(), execution_id=execution_id, current_user=mock_account
        )

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()
