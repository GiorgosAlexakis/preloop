import uuid
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from spacebridge.api.endpoints import ai_models
from spacebridge.schemas.ai_model import (
    AIModelCreate,
    AIModelRead,
    AIModelUpdate,
)
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
async def test_create_ai_model(mock_account: Account, mocker: MockerFixture):
    """Tests that an AI model is created correctly."""
    # Arrange
    ai_model_in = AIModelCreate(
        name="Test AI Model",
        description="A test AI model",
        provider_name="openai",
        model_identifier="gpt-4",
        api_key="test_key",
    )

    mock_crud_ai_model = mocker.patch(
        "spacebridge.api.endpoints.ai_models.crud_ai_model",
        new_callable=MagicMock,
    )
    mock_crud_ai_model.create_with_account.return_value = AIModelRead(
        **ai_model_in.model_dump(), id=uuid.uuid4(), account_id=str(mock_account.id)
    )

    # Act
    result = await ai_models.create_ai_model(
        db=MagicMock(),
        ai_model_in=ai_model_in,
        current_user=mock_account,
    )

    # Assert
    assert result.name == ai_model_in.name
    mock_crud_ai_model.create_with_account.assert_called_once_with(
        db=mocker.ANY,
        obj_in=ai_model_in.model_dump(),
        account_id=mock_account.account_id,
    )


@pytest.mark.asyncio
async def test_list_ai_models(mock_account: Account, mocker: MockerFixture):
    """Tests that AI models are listed correctly."""
    # Arrange
    mock_crud_ai_model = mocker.patch(
        "spacebridge.api.endpoints.ai_models.crud_ai_model",
        new_callable=MagicMock,
    )
    mock_crud_ai_model.get_by_account.return_value = []

    # Act
    result = await ai_models.list_ai_models(db=MagicMock(), current_user=mock_account)

    # Assert
    assert isinstance(result, list)
    mock_crud_ai_model.get_by_account.assert_called_once_with(
        db=mocker.ANY, account_id=mock_account.account_id
    )


@pytest.mark.asyncio
async def test_get_ai_model(mock_account: Account, mocker: MockerFixture):
    """Tests that a single AI model is read correctly."""
    # Arrange
    model_id = uuid.uuid4()
    mock_crud_ai_model = mocker.patch(
        "spacebridge.api.endpoints.ai_models.crud_ai_model",
        new_callable=MagicMock,
    )
    mock_db_model = MagicMock()
    mock_db_model.account_id = mock_account.id
    mock_crud_ai_model.get.return_value = mock_db_model

    # Act
    result = await ai_models.get_ai_model(
        db=MagicMock(), model_id=model_id, current_user=mock_account
    )

    # Assert
    assert result == mock_db_model
    mock_crud_ai_model.get.assert_called_once_with(db=mocker.ANY, id=model_id)


@pytest.mark.asyncio
async def test_update_ai_model(mock_account: Account, mocker: MockerFixture):
    """Tests that an AI model is updated correctly."""
    # Arrange
    model_id = uuid.uuid4()
    ai_model_update = AIModelUpdate(name="Updated Model Name")
    mock_crud_ai_model = mocker.patch(
        "spacebridge.api.endpoints.ai_models.crud_ai_model",
        new_callable=MagicMock,
    )
    mock_ai_model = MagicMock(account_id=mock_account.id)
    mock_crud_ai_model.get.return_value = mock_ai_model
    mock_crud_ai_model.update.return_value = AIModelRead(
        id=model_id,
        name=ai_model_update.name,
        description="A test AI model",
        provider_name="openai",
        model_identifier="gpt-4",
        api_key="test_key",
        account_id=str(mock_account.id),
    )

    # Act
    result = await ai_models.update_ai_model(
        db=MagicMock(),
        model_id=model_id,
        ai_model_in=ai_model_update,
        current_user=mock_account,
    )

    # Assert
    assert result.name == ai_model_update.name
    mock_crud_ai_model.get.assert_called_once_with(db=mocker.ANY, id=model_id)
    mock_crud_ai_model.update.assert_called_once_with(
        db=mocker.ANY,
        db_obj=mock_ai_model,
        obj_in=ai_model_update.model_dump(exclude_unset=True),
    )


@pytest.mark.asyncio
async def test_delete_ai_model(mock_account: Account, mocker: MockerFixture):
    """Tests that an AI model is deleted correctly."""
    # Arrange
    model_id = uuid.uuid4()
    mock_crud_ai_model = mocker.patch(
        "spacebridge.api.endpoints.ai_models.crud_ai_model",
        new_callable=MagicMock,
    )
    mock_ai_model = MagicMock(account_id=mock_account.id)
    mock_crud_ai_model.get.return_value = mock_ai_model

    # Act
    await ai_models.delete_ai_model(
        db=MagicMock(), model_id=model_id, current_user=mock_account
    )

    # Assert
    mock_crud_ai_model.get.assert_called_once_with(db=mocker.ANY, id=model_id)
    mock_crud_ai_model.remove.assert_called_once_with(db=mocker.ANY, id=model_id)
