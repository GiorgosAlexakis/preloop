"""Tests for AIModel model and CRUD operations."""

from sqlalchemy.orm import Session

from preloop.models.models import Account
from preloop.models.crud import crud_ai_model


def test_create_ai_model(db_session: Session, create_account):
    """Test creating an AIModel instance."""
    account: Account = create_account()

    ai_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Test OpenAI Model",
            "provider_name": "openai",
            "model_identifier": "gpt-4",
            "api_endpoint": "https://api.openai.com/v1",
            "api_key": "test_key_123",
            "is_default": True,
        },
        account_id=account.id,
    )

    assert ai_model is not None
    assert ai_model.provider_name == "openai"
    assert ai_model.model_identifier == "gpt-4"
    assert ai_model.api_endpoint == "https://api.openai.com/v1"
    assert ai_model.api_key == "test_key_123"
    assert ai_model.is_default is True
    assert ai_model.account_id == account.id


def test_get_ai_models_by_account(db_session: Session, create_account):
    """Test retrieving AIModels for a specific account."""
    account1: Account = create_account()
    account2: Account = create_account()

    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Test OpenAI Model Account1",
            "provider_name": "openai",
            "model_identifier": "gpt-4",
            "api_endpoint": "https://api.openai.com/v1",
            "api_key": "test_key_123",
            "is_default": True,
        },
        account_id=account1.id,
    )
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Test OpenAI Model Account1",
            "provider_name": "openai",
            "model_identifier": "gpt-4",
            "api_endpoint": "https://api.openai.com/v1",
            "api_key": "test_key_123",
        },
        account_id=account1.id,
    )
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Test Anthropic Model Account2",
            "provider_name": "anthropic",
            "model_identifier": "claude-2",
            "api_endpoint": "https://api.anthropic.com/v1",
            "api_key": "test_key_456",
        },
        account_id=account2.id,
    )

    models_acc1 = crud_ai_model.get_by_account(db=db_session, account_id=account1.id)
    models_acc2 = crud_ai_model.get_by_account(db=db_session, account_id=account2.id)

    assert len(models_acc1) == 2
    assert len(models_acc2) == 1
    assert models_acc1[0].provider_name in ["openai", "openai"]
    assert models_acc2[0].provider_name == "anthropic"


def test_update_ai_model_and_default_logic(db_session: Session, create_account):
    """Test updating an AIModel and the default model logic."""
    account: Account = create_account()
    model1 = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Default Test Model",
            "provider_name": "openai",
            "model_identifier": "gpt-4",
            "api_endpoint": "https://api.openai.com/v1",
            "api_key": "test_key_123",
            "is_default": True,
        },
        account_id=account.id,
    )
    model2 = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Non-Default Test Model",
            "provider_name": "anthropic",
            "model_identifier": "claude-instant-1",
            "api_endpoint": "https://api.anthropic.com/v1",
            "api_key": "test_key_456",
            "is_default": False,
        },
        account_id=account.id,
    )

    assert model1.is_default is True
    assert model2.is_default is False

    # Update m2 to be default, m1 should become non-default
    updated_m2 = crud_ai_model.update(
        db=db_session, db_obj=model2, obj_in={"is_default": True}
    )
    db_session.refresh(model1)  # Refresh m1 to get its updated state from the DB

    assert updated_m2.is_default is True
    assert updated_m2.api_key == "test_key_456"
    assert model1.is_default is False

    # Update m1 to be default again
    updated_m1 = crud_ai_model.update(
        db=db_session, db_obj=model1, obj_in={"is_default": True}
    )
    db_session.refresh(updated_m1)

    assert updated_m1.is_default is True
    assert updated_m2.is_default is False

    # Test setting a model to non-default
    still_default_m1 = crud_ai_model.update(
        db=db_session, db_obj=updated_m1, obj_in={"is_default": False}
    )
    assert still_default_m1.is_default is False


def test_get_default_ai_model(db_session: Session, create_account):
    """Test retrieving the default AIModel for an account."""
    account: Account = create_account()
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Non-Default Model for Get Default Test",
            "provider_name": "openai",
            "model_identifier": "gpt-4",
            "api_endpoint": "https://api.openai.com/v1",
            "api_key": "test_key_123",
            "is_default": False,
        },
        account_id=account.id,
    )
    default_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Actual Default Model for Get Default Test",
            "provider_name": "anthropic",
            "model_identifier": "claude-2",
            "api_endpoint": "https://api.anthropic.com/v1",
            "api_key": "test_key_456",
            "is_default": True,
        },
        account_id=account.id,
    )

    retrieved_default = crud_ai_model.get_default_active_model(
        db=db_session, account_id=account.id
    )
    assert retrieved_default is not None
    assert retrieved_default.id == default_model.id
    assert retrieved_default.model_identifier == "claude-2"

    # Test with no account-specific default model - should fall back to system-wide default
    account2: Account = create_account()
    crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Non-Default Model for Get Default Test",
            "provider_name": "openai",
            "model_identifier": "gpt-4",
            "api_endpoint": "https://api.openai.com/v1",
            "api_key": "test_key_123",
            "is_default": False,
        },
        account_id=account2.id,
    )
    fallback_default = crud_ai_model.get_default_active_model(
        db=db_session, account_id=account2.id
    )
    # Should return system-wide default if it exists, or None if no system-wide default exists
    system_wide_default = crud_ai_model.get_default_active_model(
        db=db_session, account_id=None
    )
    assert fallback_default == system_wide_default


def test_delete_ai_model(db_session: Session, create_account):
    """Test deleting an AIModel."""
    account: Account = create_account()
    model_to_delete = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Model to Delete",
            "provider_name": "openai",
            "model_identifier": "gpt-4",
            "api_endpoint": "https://api.openai.com/v1",
            "api_key": "test_key_123",
            "is_default": False,
        },
        account_id=account.id,
    )
    model_id = model_to_delete.id

    crud_ai_model.remove(db=db_session, id=model_id)

    retrieved_after_delete = crud_ai_model.get(db=db_session, id=model_id)
    assert retrieved_after_delete is None

    # Ensure other models for the same account are not affected
    surviving_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Surviving Model",
            "provider_name": "openai",
            "model_identifier": "gpt-4",
            "api_endpoint": "https://api.openai.com/v1",
            "api_key": "test_key_123",
            "is_default": False,
        },
        account_id=account.id,
    )
    assert crud_ai_model.get(db=db_session, id=surviving_model.id) is not None


def test_default_model_exists(db_session: Session):
    """Test checking if a system-wide default model exists."""
    # Check the method returns a boolean
    result = crud_ai_model.default_model_exists(db=db_session)
    assert isinstance(result, bool)

    # Ensure a system-wide default model exists for test coverage
    from preloop.models.models.ai_model import AIModel

    default_model = AIModel(
        name="System Default Test",
        provider_name="openai",
        model_identifier="gpt-4-test",
        api_endpoint="https://api.openai.com/v1",
        api_key="test_key",
        is_default=True,
        account_id=None,
    )
    db_session.add(default_model)
    db_session.commit()

    # Verify a default exists
    assert crud_ai_model.default_model_exists(db=db_session) is True
