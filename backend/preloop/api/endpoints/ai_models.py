import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session

from preloop.api.auth.jwt import get_current_active_user
from preloop.schemas.ai_model import (
    AIModelCreate,
    AIModelRead,
    AIModelUpdate,
)
from preloop.models.crud import crud_ai_model
from preloop.models.db.session import get_db_session
from preloop.models.models.user import User
from preloop.models.models.ai_model import AIModel
from preloop.utils.permissions import require_permission
from preloop.services.ai_model_provider import get_available_models_for_provider

logger = logging.getLogger(__name__)
router = APIRouter()
public_router = APIRouter()  # Router for endpoints that don't require authentication


@router.post(
    "/ai-models",
    response_model=AIModelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create AI Model",
    tags=["AI Models"],
)
@require_permission("create_ai_models")
def create_ai_model(
    ai_model_in: AIModelCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> AIModel:
    """Create a new AI Model for the authenticated user's account."""
    created_model = crud_ai_model.create_with_account(
        db=db,
        obj_in=ai_model_in.dict(),
        account_id=current_user.account_id,
    )
    return created_model


@router.get(
    "/ai-models",
    response_model=List[AIModelRead],
    summary="List AI Models",
    tags=["AI Models"],
)
@require_permission("view_ai_models")
def list_ai_models(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> List[AIModelRead]:
    """List all AI Models associated with the authenticated user's account."""
    models = crud_ai_model.get_by_account(db=db, account_id=current_user.account_id)
    return models


@router.get(
    "/ai-models/{model_id}",
    response_model=AIModelRead,
    summary="Get AI Model by ID",
    tags=["AI Models"],
)
@require_permission("view_ai_models")
def get_ai_model(
    model_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> AIModelRead:
    """Retrieve a specific AI Model by its ID."""
    db_model = crud_ai_model.get(db=db, id=model_id)

    if not db_model or db_model.account_id != current_user.account_id:
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
@require_permission("edit_ai_models")
def update_ai_model(
    model_id: uuid.UUID,
    ai_model_in: AIModelUpdate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> AIModelRead:
    """Update an existing AI Model by its ID."""
    db_model = crud_ai_model.get(db=db, id=model_id)

    if not db_model or db_model.account_id != current_user.account_id:
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
@require_permission("delete_ai_models")
def delete_ai_model(
    model_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """Delete an AI Model by its ID."""
    db_model = crud_ai_model.get(db=db, id=model_id)
    if not db_model or db_model.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI Model not found"
        )

    crud_ai_model.remove(db=db, id=model_id)

    # No content returned for HTTP 204
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public_router.get(
    "/ai-models/providers/{provider}/available-models",
    response_model=List[str],
    summary="Get Available Models for Provider",
    tags=["AI Models"],
)
async def get_provider_available_models(
    provider: str,
    api_key: Optional[str] = Query(
        None, description="Optional API key for fetching models"
    ),
) -> List[str]:
    """
    Fetch available models from the specified AI provider.

    For OpenAI, this will fetch the latest available models from their API.
    For Anthropic and Google, this returns a curated list of known models.

    Note: This endpoint does not require authentication as it's just fetching
    publicly available model names. The api_key parameter is optional for
    fetching live data from OpenAI.
    """
    try:
        models = await get_available_models_for_provider(provider, api_key)
        return models
    except ValueError as e:
        # ValueError is raised for authentication errors
        logger.warning(f"Authentication failed for provider {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to fetch models for provider {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available models: {str(e)}",
        )
