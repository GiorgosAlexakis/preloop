import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from preloop.models.crud import flow_execution as crud_flow_execution
from preloop.models.schemas.flow_execution import (
    FlowExecutionCreate,
    FlowExecutionUpdate,
)
from preloop.models.models.flow_execution import FlowExecution


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_flow_execution(mock_db_session):
    """Test retrieving a flow execution."""
    # Arrange
    flow_execution_id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = FlowExecution(
        id=flow_execution_id
    )
    mock_db_session.execute.return_value = mock_result

    # Act
    result = await crud_flow_execution.get_flow_execution(
        mock_db_session, flow_execution_id
    )

    # Assert
    assert result.id == flow_execution_id
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_flow_execution(mock_db_session):
    """Test creating a flow execution."""
    # Arrange
    flow_execution_in = FlowExecutionCreate(
        flow_id=uuid.uuid4(),
        status="PENDING",
        trigger_event_details={},
    )

    # Act
    await crud_flow_execution.create_flow_execution(mock_db_session, flow_execution_in)

    # Assert
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_flow_execution(mock_db_session):
    """Test updating a flow execution."""
    # Arrange
    flow_execution = FlowExecution(id=uuid.uuid4(), status="PENDING")
    flow_execution_in = FlowExecutionUpdate(status="RUNNING")

    # Act
    result = await crud_flow_execution.update_flow_execution(
        mock_db_session, flow_execution, flow_execution_in
    )

    # Assert
    assert result.status == "RUNNING"
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_delete_flow_execution(mock_db_session):
    """Test deleting a flow execution."""
    # Arrange
    flow_execution_id = uuid.uuid4()
    mock_flow_execution = FlowExecution(id=flow_execution_id)

    with patch(
        "preloop.models.crud.flow_execution.get_flow_execution",
        new=AsyncMock(return_value=mock_flow_execution),
    ):
        # Act
        result = await crud_flow_execution.delete_flow_execution(
            mock_db_session, flow_execution_id
        )

        # Assert
        assert result.id == flow_execution_id
        mock_db_session.delete.assert_called_once_with(mock_flow_execution)
        mock_db_session.commit.assert_called_once()
