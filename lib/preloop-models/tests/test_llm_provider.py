"""Tests for LLMProvider model and CRUD operations."""

import pytest
from sqlalchemy.orm import Session

from spacemodels.models import Account, LLMProvider
from spacemodels.crud import crud_llm_provider
from spacebridge.schemas.llm_provider import LLMProviderCreate, LLMProviderUpdate


def test_create_llm_provider(db_session: Session, create_account):
    """Test creating an LLMProvider instance."""
    account: Account = create_account()
    provider_data = LLMProviderCreate(
        provider_name="openai",
        credentials={"api_key": "test_key_123"},
        is_default=True,
    )

    llm_provider = crud_llm_provider.create_with_account(
        db=db_session, obj_in=provider_data, account_id=account.id
    )

    assert llm_provider is not None
    assert llm_provider.provider_name == "openai"
    assert llm_provider.credentials == {"api_key": "test_key_123"}
    assert llm_provider.is_default is True
    assert llm_provider.account_id == account.id


def test_get_llm_providers_by_account(db_session: Session, create_account):
    """Test retrieving LLMProviders for a specific account."""
    account1: Account = create_account(username="user1_llm", email="user1_llm@example.com")
    account2: Account = create_account(username="user2_llm", email="user2_llm@example.com")

    crud_llm_provider.create_with_account(
        db=db_session,
        obj_in=LLMProviderCreate(provider_name="p1", credentials={}),
        account_id=account1.id,
    )
    crud_llm_provider.create_with_account(
        db=db_session,
        obj_in=LLMProviderCreate(provider_name="p2", credentials={}),
        account_id=account1.id,
    )
    crud_llm_provider.create_with_account(
        db=db_session,
        obj_in=LLMProviderCreate(provider_name="p3", credentials={}),
        account_id=account2.id,
    )

    providers_acc1 = crud_llm_provider.get_by_account_id(db=db_session, account_id=account1.id)
    providers_acc2 = crud_llm_provider.get_by_account_id(db=db_session, account_id=account2.id)

    assert len(providers_acc1) == 2
    assert len(providers_acc2) == 1
    assert providers_acc1[0].provider_name in ["p1", "p2"]
    assert providers_acc2[0].provider_name == "p3"


def test_update_llm_provider_and_default_logic(db_session: Session, create_account):
    """Test updating an LLMProvider and the default provider logic."""
    account: Account = create_account()
    provider1_data = LLMProviderCreate(
        provider_name="provider1", credentials={"key": "v1"}, is_default=True
    )
    provider2_data = LLMProviderCreate(
        provider_name="provider2", credentials={"key": "v2"}, is_default=False
    )

    p1 = crud_llm_provider.create_with_account(
        db=db_session, obj_in=provider1_data, account_id=account.id
    )
    p2 = crud_llm_provider.create_with_account(
        db=db_session, obj_in=provider2_data, account_id=account.id
    )

    assert p1.is_default is True
    assert p2.is_default is False

    # Update p2 to be default, p1 should become non-default
    update_data = LLMProviderUpdate(is_default=True, credentials={"key": "v2_updated"})
    updated_p2 = crud_llm_provider.update(db=db_session, db_obj=p2, obj_in=update_data)
    db_session.refresh(p1) # Refresh p1 to get its updated state from the DB

    assert updated_p2.is_default is True
    assert updated_p2.credentials == {"key": "v2_updated"}
    assert p1.is_default is False

    # Update p1 to be default again
    updated_p1 = crud_llm_provider.update(db=db_session, db_obj=p1, obj_in=LLMProviderUpdate(is_default=True))
    db_session.refresh(updated_p2)

    assert updated_p1.is_default is True
    assert updated_p2.is_default is False

    # Test setting a provider to non-default
    still_default_p1 = crud_llm_provider.update(db=db_session, db_obj=updated_p1, obj_in=LLMProviderUpdate(is_default=False))
    assert still_default_p1.is_default is False


def test_get_default_llm_provider(db_session: Session, create_account):
    """Test retrieving the default LLMProvider for an account."""
    account: Account = create_account()
    crud_llm_provider.create_with_account(
        db=db_session,
        obj_in=LLMProviderCreate(provider_name="non_default", credentials={}, is_default=False),
        account_id=account.id,
    )
    default_provider_obj = crud_llm_provider.create_with_account(
        db=db_session,
        obj_in=LLMProviderCreate(provider_name="default_one", credentials={}, is_default=True),
        account_id=account.id,
    )

    retrieved_default = crud_llm_provider.get_default_by_account_id(db=db_session, account_id=account.id)
    assert retrieved_default is not None
    assert retrieved_default.id == default_provider_obj.id
    assert retrieved_default.provider_name == "default_one"

    # Test with no default provider
    account2: Account = create_account(username="no_default_user", email="no_default@example.com")
    crud_llm_provider.create_with_account(
        db=db_session,
        obj_in=LLMProviderCreate(provider_name="another_non_default", credentials={}, is_default=False),
        account_id=account2.id,
    )
    no_default = crud_llm_provider.get_default_by_account_id(db=db_session, account_id=account2.id)
    assert no_default is None


def test_delete_llm_provider(db_session: Session, create_account):
    """Test deleting an LLMProvider."""
    account: Account = create_account()
    provider_to_delete = crud_llm_provider.create_with_account(
        db=db_session,
        obj_in=LLMProviderCreate(provider_name="to_delete", credentials={}),
        account_id=account.id,
    )
    provider_id = provider_to_delete.id

    deleted_provider = crud_llm_provider.delete(db=db_session, id=provider_id)
    assert deleted_provider is not None
    assert deleted_provider.id == provider_id

    retrieved_after_delete = crud_llm_provider.get(db=db_session, id=provider_id)
    assert retrieved_after_delete is None

    # Ensure other providers for the same account are not affected
    surviving_provider = crud_llm_provider.create_with_account(
        db=db_session,
        obj_in=LLMProviderCreate(provider_name="survivor", credentials={}),
        account_id=account.id,
    )
    assert crud_llm_provider.get(db=db_session, id=surviving_provider.id) is not None
