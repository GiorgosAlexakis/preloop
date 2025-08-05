import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from spacebridge.api.auth.jwt import get_current_active_user
from spacebridge.schemas.ai_model import (
    AIModelCreate,
    AIModelRead,
    AIModelUpdate,
)
from spacemodels.crud import crud_ai_model
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.ai_model import AIModel

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/ai-models",
    response_model=AIModelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create AI Model",
    tags=["AI Models"],
)
def create_ai_model(
    ai_model_in: AIModelCreate,
    db: Session = Depends(get_db_session),
    current_user: Account = Depends(get_current_active_user),
) -> AIModel:
    """Create a new AI Model for the authenticated user's account."""
    created_model = crud_ai_model.create_with_account(
        db=db,
        obj_in=ai_model_in.dict(),
        account_id=current_user.id,
    )
    return created_model


@router.get(
    "/ai-models",
    response_model=List[AIModelRead],
    summary="List AI Models",
    tags=["AI Models"],
)
def list_ai_models(
    db: Session = Depends(get_db_session),
    current_user: Account = Depends(get_current_active_user),
) -> List[AIModelRead]:
    """List all AI Models associated with the authenticated user's account."""
    models = crud_ai_model.get_by_account(db=db, account_id=current_user.id)
    return models


@router.get(
    "/ai-models/{model_id}",
    response_model=AIModelRead,
    summary="Get AI Model by ID",
    tags=["AI Models"],
)
def get_ai_model(
    model_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: Account = Depends(get_current_active_user),
) -> AIModelRead:
    """Retrieve a specific AI Model by its ID."""
    db_model = crud_ai_model.get(db=db, id=model_id)

    if not db_model or db_model.account_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI Model not found"
        )
    return db_model


@router.put(
    "/ai-models/{model_id}",
    response_model=AIModelRead,
    summary="Update AI Model",
    tags=["AI Models"],
)
def update_ai_model(
    model_id: uuid.UUID,
    ai_model_in: AIModelUpdate,
    db: Session = Depends(get_db_session),
    current_user: Account = Depends(get_current_active_user),
) -> AIModelRead:
    """Update an existing AI Model by its ID."""
    db_model = crud_ai_model.get(db=db, id=model_id)

    if not db_model or db_model.account_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI Model not found"
        )

    updated_model = crud_ai_model.update(
        db=db,
        db_obj=db_model,
        obj_in=ai_model_in.dict(exclude_unset=True),
    )
    return updated_model


@router.delete(
    "/ai-models/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete AI Model",
    tags=["AI Models"],
)
def delete_ai_model(
    model_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: Account = Depends(get_current_active_user),
):
    """Delete an AI Model by its ID."""
    db_model = crud_ai_model.get(db=db, id=model_id)
    if not db_model or db_model.account_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI Model not found"
        )

    crud_ai_model.remove(db=db, id=model_id)

    # No content returned for HTTP 204
    return
