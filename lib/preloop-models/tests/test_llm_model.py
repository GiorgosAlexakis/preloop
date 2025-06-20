"""Tests for LLMModel model and CRUD operations."""

from sqlalchemy.orm import Session

from spacemodels.models import Account
from spacemodels.crud import crud_llm_model


def test_create_llm_model(db_session: Session, create_account):
    """Test creating an LLMModel instance."""
    account: Account = create_account()

    llm_model = crud_llm_model.create_with_account(
        db=db_session,
        name="Test OpenAI Model",
        provider_name="openai",
        model_name="gpt-4",
        model_version="1",
        api_url="https://api.openai.com/v1",
        api_key="test_key_123",
        is_default=True,
        account_id=account.id,
    )

    assert llm_model is not None
    assert llm_model.provider_name == "openai"
    assert llm_model.model_name == "gpt-4"
    assert llm_model.model_version == "1"
    assert llm_model.api_url == "https://api.openai.com/v1"
    assert llm_model.api_key == "test_key_123"
    assert llm_model.is_default is True
    assert llm_model.account_id == account.id


def test_get_llm_models_by_account(db_session: Session, create_account):
    """Test retrieving LLMModels for a specific account."""
    account1: Account = create_account(
        username="user1_llm", email="user1_llm@example.com"
    )
    account2: Account = create_account(
        username="user2_llm", email="user2_llm@example.com"
    )

    crud_llm_model.create_with_account(
        db=db_session,
        name="Test OpenAI Model Account1",
        provider_name="openai",
        model_name="gpt-4",
        model_version="1",
        api_url="https://api.openai.com/v1",
        api_key="test_key_123",
        is_default=True,
        account_id=account1.id,
    )
    crud_llm_model.create_with_account(
        db=db_session,
        name="Test OpenAI Model Account1",
        provider_name="openai",
        model_name="gpt-4",
        model_version="1",
        api_url="https://api.openai.com/v1",
        api_key="test_key_123",
        account_id=account1.id,
    )
    crud_llm_model.create_with_account(
        db=db_session,
        name="Test Anthropic Model Account2",
        provider_name="anthropic",
        model_name="claude-2",
        model_version="1",
        api_url="https://api.anthropic.com/v1",
        api_key="test_key_456",
        account_id=account2.id,
    )

    models_acc1 = crud_llm_model.get_by_account_id(
        db=db_session, account_id=account1.id
    )
    models_acc2 = crud_llm_model.get_by_account_id(
        db=db_session, account_id=account2.id
    )

    assert len(models_acc1) == 2
    assert len(models_acc2) == 1
    assert models_acc1[0].provider_name in ["openai", "openai"]
    assert models_acc2[0].provider_name == "anthropic"


def test_update_llm_model_and_default_logic(db_session: Session, create_account):
    """Test updating an LLMModel and the default model logic."""
    account: Account = create_account()
    model1 = crud_llm_model.create_with_account(
        db=db_session,
        name="Default Test Model",
        provider_name="openai",
        model_name="gpt-4",
        model_version="1",
        api_url="https://api.openai.com/v1",
        api_key="test_key_123",
        is_default=True,
        account_id=account.id,
    )
    model2 = crud_llm_model.create_with_account(
        db=db_session,
        name="Non-Default Test Model",
        provider_name="anthropic",
        model_name="claude-instant-1",
        model_version="1",
        api_url="https://api.anthropic.com/v1",
        api_key="test_key_456",
        is_default=False,
        account_id=account.id,
    )

    assert model1.is_default is True
    assert model2.is_default is False

    # Update m2 to be default, m1 should become non-default
    updated_m2 = crud_llm_model.update(db=db_session, db_obj=model2, is_default=True)
    db_session.refresh(model1)  # Refresh m1 to get its updated state from the DB

    assert updated_m2.is_default is True
    assert updated_m2.api_key == "test_key_456"
    assert model1.is_default is False

    # Update m1 to be default again
    updated_m1 = crud_llm_model.update(db=db_session, db_obj=model1, is_default=True)
    db_session.refresh(updated_m1)

    assert updated_m1.is_default is True
    assert updated_m2.is_default is False

    # Test setting a model to non-default
    still_default_m1 = crud_llm_model.update(
        db=db_session, db_obj=updated_m1, is_default=False
    )
    assert still_default_m1.is_default is False


def test_get_default_llm_model(db_session: Session, create_account):
    """Test retrieving the default LLMModel for an account."""
    account: Account = create_account()
    crud_llm_model.create_with_account(
        db=db_session,
        name="Non-Default Model for Get Default Test",
        provider_name="openai",
        model_name="gpt-4",
        model_version="1",
        api_url="https://api.openai.com/v1",
        api_key="test_key_123",
        is_default=False,
        account_id=account.id,
    )
    default_model = crud_llm_model.create_with_account(
        db=db_session,
        name="Actual Default Model for Get Default Test",
        provider_name="anthropic",
        model_name="claude-2",
        model_version="1",
        api_url="https://api.anthropic.com/v1",
        api_key="test_key_456",
        is_default=True,
        account_id=account.id,
    )

    retrieved_default = crud_llm_model.get_default_by_account_id(
        db=db_session, account_id=account.id
    )
    assert retrieved_default is not None
    assert retrieved_default.id == default_model.id
    assert retrieved_default.model_name == "claude-2"

    # Test with no default model
    account2: Account = create_account(
        username="no_default_user", email="no_default@example.com"
    )
    crud_llm_model.create_with_account(
        db=db_session,
        name="Non-Default Model for Get Default Test",
        provider_name="openai",
        model_name="gpt-4",
        model_version="1",
        api_url="https://api.openai.com/v1",
        api_key="test_key_123",
        is_default=False,
        account_id=account2.id,
    )
    no_default = crud_llm_model.get_default_by_account_id(
        db=db_session, account_id=account2.id
    )
    assert no_default is None


def test_delete_llm_model(db_session: Session, create_account):
    """Test deleting an LLMModel."""
    account: Account = create_account()
    model_to_delete = crud_llm_model.create_with_account(
        db=db_session,
        name="Model to Delete",
        provider_name="openai",
        model_name="gpt-4",
        model_version="1",
        api_url="https://api.openai.com/v1",
        api_key="test_key_123",
        is_default=False,
        account_id=account.id,
    )
    model_id = model_to_delete.id

    deleted_model = crud_llm_model.delete(db=db_session, id=model_id)
    assert deleted_model is not None
    assert deleted_model.id == model_id

    retrieved_after_delete = crud_llm_model.get(db=db_session, id=model_id)
    assert retrieved_after_delete is None

    # Ensure other models for the same account are not affected
    surviving_model = crud_llm_model.create_with_account(
        db=db_session,
        name="Surviving Model",
        provider_name="openai",
        model_name="gpt-4",
        model_version="1",
        api_url="https://api.openai.com/v1",
        api_key="test_key_123",
        is_default=False,
        account_id=account.id,
    )
    assert crud_llm_model.get(db=db_session, id=surviving_model.id) is not None
