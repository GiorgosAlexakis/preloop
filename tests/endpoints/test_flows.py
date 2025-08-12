import uuid
from zoneinfo import ZoneInfo
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from spacebridge.api.endpoints import flows
from spacemodels import schemas
from spacemodels.models.account import Account


@pytest.fixture
def mock_account(mocker: MockerFixture) -> Account:
    """Provides a mock Account object for testing."""
    account = MagicMock(spec=Account)
    account.id = uuid.uuid4()
    account.email = "test@example.com"
    return account


def test_create_flow(mock_account: Account, mocker: MockerFixture):
    """Tests that a flow is created correctly."""
    # Arrange
    flow_in = schemas.FlowCreate(
        name="Test Flow",
        description="A test flow",
        trigger_event_source="github",
        trigger_event_type="commit_to_main",
        prompt_template="Test prompt",
        ai_model_id=uuid.uuid4(),
        openhands_agent_config={"agent_type": "CodeActAgent"},
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
    result = flows.create_flow(
        db=MagicMock(), flow_in=flow_in, current_user=mock_account
    )

    # Assert
    assert result.name == flow_in.name
    mock_crud_flow.create.assert_called_once_with(
        db=mocker.ANY, obj_in=flow_in, account_id=mock_account.id
    )


def test_read_flows(mock_account: Account, mocker: MockerFixture):
    """Tests that flows are read correctly."""
    # Arrange
    mock_crud_flow = mocker.patch(
        "spacebridge.api.endpoints.flows.crud_flow",
        new_callable=MagicMock,
    )
    mock_crud_flow.get_multi.return_value = []

    # Act
    result = flows.read_flows(db=MagicMock(), current_user=mock_account)

    # Assert
    assert isinstance(result, list)
    mock_crud_flow.get_multi.assert_called_once_with(
        mocker.ANY, account_id=mock_account.id, skip=0, limit=100
    )


def test_read_flow(mock_account: Account, mocker: MockerFixture):
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
        account_id=mock_account.id,
    )

    # Act
    result = flows.read_flow(db=MagicMock(), flow_id=flow_id, current_user=mock_account)

    # Assert
    assert result.id == flow_id
    mock_crud_flow.get.assert_called_once_with(
        db=mocker.ANY, id=flow_id, account_id=mock_account.id
    )


def test_update_flow(mock_account: Account, mocker: MockerFixture):
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
        account_id=mock_account.id,
    )

    # Act
    result = flows.update_flow(
        db=MagicMock(),
        flow_id=flow_id,
        flow_in=flow_update,
        current_user=mock_account,
    )

    # Assert
    assert result.name == flow_update.name
    mock_crud_flow.get.assert_called_once_with(
        db=mocker.ANY, id=flow_id, account_id=mock_account.id
    )
    mock_crud_flow.update.assert_called_once_with(
        db=mocker.ANY, db_obj=mock_flow, obj_in=flow_update
    )


def test_delete_flow(mock_account: Account, mocker: MockerFixture):
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
    flows.delete_flow(db=MagicMock(), flow_id=flow_id, current_user=mock_account)

    # Assert
    mock_crud_flow.get.assert_called_once_with(
        db=mocker.ANY, id=flow_id, account_id=mock_account.id
    )
    mock_crud_flow.remove.assert_called_once_with(
        db=mocker.ANY, id=flow_id, account_id=mock_account.id
    )
