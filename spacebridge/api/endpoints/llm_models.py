import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from spacebridge.api.auth.jwt import get_current_active_user
from spacebridge.schemas.auth import UserResponse
from spacebridge.schemas.llm_model import (
    LLMModelCreate,
    LLMModelRead,
    LLMModelUpdate,
)
from spacemodels.crud import crud_llm_model
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.llm_model import LLMModel

logger = logging.getLogger(__name__)
router = APIRouter()


# TODO: Change functions to accept flat arguments instead of LLMModelCreate and LLMModelUpdate
# LLMModel required parameters
# provider_name: str
# api_key: str
# api_url: str
# model_name: str
# model_version: Optional[str] = None
# is_default: Optional[bool] = False


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
    "/llm-models",
    response_model=LLMModelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create LLM Model",
    tags=["LLM Models"],
)
def create_llm_model(
    llm_model_in: LLMModelCreate,
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
) -> LLMModel:
    """Create a new LLM Model for the authenticated user's account."""
    account_id = get_account_id_from_user(db, current_user)
    created_model = crud_llm_model.create_with_account(
        db=db,
        provider_name=llm_model_in.provider_name,
        api_key=llm_model_in.api_key,
        api_url=llm_model_in.api_url,
        model_name=llm_model_in.model_name,
        model_version=llm_model_in.model_version,
        is_default=llm_model_in.is_default,
        account_id=account_id,
    )
    return created_model


@router.get(
    "/llm-models",
    response_model=List[LLMModelRead],
    summary="List LLM Models",
    tags=["LLM Models"],
)
def list_llm_models(
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
) -> List[LLMModelRead]:
    """List all LLM Models associated with the authenticated user's account."""
    account_id = get_account_id_from_user(db, current_user)
    models = crud_llm_model.get_by_account_id(db=db, account_id=account_id)
    return models


@router.get(
    "/llm-models/{model_id}",
    response_model=LLMModelRead,
    summary="Get LLM Model by ID",
    tags=["LLM Models"],
)
def get_llm_model(
    model_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
) -> LLMModelRead:
    """Retrieve a specific LLM Model by its ID."""
    account_id = get_account_id_from_user(db, current_user)
    db_model = crud_llm_model.get(db=db, id=model_id)

    if not db_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LLM Model not found"
        )
    if db_model.account_id != account_id:
        logger.warning(
            f"User {current_user.username} (account_id: {account_id}) "
            f"attempted to access LLM Model {model_id} "
            f"belonging to account_id {db_model.account_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this LLM Model",
        )
    return db_model


@router.put(
    "/llm-models/{model_id}",
    response_model=LLMModelRead,
    summary="Update LLM Model",
    tags=["LLM Models"],
)
def update_llm_model(
    model_id: str,
    llm_model_in: LLMModelUpdate,
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
) -> LLMModelRead:
    """Update an existing LLM Model by its ID."""
    account_id = get_account_id_from_user(db, current_user)
    db_model = crud_llm_model.get(db=db, id=model_id)

    if not db_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LLM Model not found"
        )
    if db_model.account_id != account_id:
        logger.warning(
            f"User {current_user.username} (account_id: {account_id}) "
            f"attempted to update LLM Model {model_id} "
            f"belonging to account_id {db_model.account_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this LLM Model",
        )

    updated_model = crud_llm_model.update(
        db=db,
        db_obj=db_model,
        provider_name=llm_model_in.provider_name,
        api_key=llm_model_in.api_key,
        api_url=llm_model_in.api_url,
        model_name=llm_model_in.model_name,
        model_version=llm_model_in.model_version,
        is_default=llm_model_in.is_default,
    )
    return updated_model


@router.delete(
    "/llm-models/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete LLM Model",
    tags=["LLM Models"],
)
def delete_llm_model(
    model_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Delete an LLM Model by its ID."""
    account_id = get_account_id_from_user(db, current_user)
    db_model = crud_llm_model.get(db=db, id=model_id)

    if not db_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LLM Model not found"
        )
    if db_model.account_id != account_id:
        logger.warning(
            f"User {current_user.username} (account_id: {account_id}) "
            f"attempted to delete LLM Model {model_id} "
            f"belonging to account_id {db_model.account_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this LLM Model",
        )

    crud_llm_model.delete(db=db, id=model_id)
    # No content returned for HTTP 204
    return
