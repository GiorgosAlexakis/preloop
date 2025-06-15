import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from spacebridge.api.auth.jwt import get_current_active_user
from spacebridge.schemas.auth import UserResponse
from spacebridge.schemas.llm_provider import (
    LLMProviderCreate,
    LLMProviderRead,
    LLMProviderUpdate,
)
from spacemodels.crud import crud_llm_provider
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.llm_provider import LLMProvider as LLMProviderModel

logger = logging.getLogger(__name__)
router = APIRouter()


def get_account_id_from_user(db: Session, current_user: UserResponse) -> int:
    """Retrieve the account ID for the currently authenticated user."""
    account = (
        db.query(Account).filter(Account.username == current_user.username).first()
    )
    if not account:
        logger.error(f"Account not found for user {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )
    return account.id


@router.post(
    "/",
    response_model=LLMProviderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create LLM Provider",
    tags=["LLM Providers"],
)
def create_llm_provider(
    llm_provider_in: LLMProviderCreate,
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
) -> LLMProviderModel:
    """Create a new LLM Provider for the authenticated user's account."""
    account_id = get_account_id_from_user(db, current_user)
    created_provider = crud_llm_provider.create_with_account(
        db=db, obj_in=llm_provider_in, account_id=account_id
    )
    return created_provider


@router.get(
    "/",
    response_model=List[LLMProviderRead],
    summary="List LLM Providers",
    tags=["LLM Providers"],
)
def list_llm_providers(
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
) -> List[LLMProviderModel]:
    """List all LLM Providers associated with the authenticated user's account."""
    account_id = get_account_id_from_user(db, current_user)
    providers = crud_llm_provider.get_by_account_id(db=db, account_id=account_id)
    return providers


@router.get(
    "/{provider_id}",
    response_model=LLMProviderRead,
    summary="Get LLM Provider by ID",
    tags=["LLM Providers"],
)
def get_llm_provider(
    provider_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
) -> LLMProviderModel:
    """Retrieve a specific LLM Provider by its ID."""
    account_id = get_account_id_from_user(db, current_user)
    db_provider = crud_llm_provider.get(db=db, id=provider_id)

    if not db_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LLM Provider not found"
        )
    if db_provider.account_id != account_id:
        logger.warning(
            f"User {current_user.username} (account_id: {account_id}) "
            f"attempted to access LLM Provider {provider_id} "
            f"belonging to account_id {db_provider.account_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this LLM Provider",
        )
    return db_provider


@router.put(
    "/{provider_id}",
    response_model=LLMProviderRead,
    summary="Update LLM Provider",
    tags=["LLM Providers"],
)
def update_llm_provider(
    provider_id: str,
    llm_provider_in: LLMProviderUpdate,
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
) -> LLMProviderModel:
    """Update an existing LLM Provider by its ID."""
    account_id = get_account_id_from_user(db, current_user)
    db_provider = crud_llm_provider.get(db=db, id=provider_id)

    if not db_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LLM Provider not found"
        )
    if db_provider.account_id != account_id:
        logger.warning(
            f"User {current_user.username} (account_id: {account_id}) "
            f"attempted to update LLM Provider {provider_id} "
            f"belonging to account_id {db_provider.account_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this LLM Provider",
        )

    updated_provider = crud_llm_provider.update(
        db=db, db_obj=db_provider, obj_in=llm_provider_in
    )
    return updated_provider


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete LLM Provider",
    tags=["LLM Providers"],
)
def delete_llm_provider(
    provider_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Delete an LLM Provider by its ID."""
    account_id = get_account_id_from_user(db, current_user)
    db_provider = crud_llm_provider.get(db=db, id=provider_id)

    if not db_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LLM Provider not found"
        )
    if db_provider.account_id != account_id:
        logger.warning(
            f"User {current_user.username} (account_id: {account_id}) "
            f"attempted to delete LLM Provider {provider_id} "
            f"belonging to account_id {db_provider.account_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this LLM Provider",
        )

    crud_llm_provider.delete(db=db, id=provider_id)
    # No content returned for HTTP 204
    return
