"""Account-related endpoints."""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from preloop_ai.api.auth import get_current_active_user
from preloop_ai.api.common import get_account_for_user
from preloop_ai.license import Feature, get_available_features, get_feature_info
from preloop_models.crud import crud_account
from preloop_models.db.session import get_db_session
from preloop_models.models.account import Account

logger = logging.getLogger(__name__)

router = APIRouter()


class AccountDetailsResponse(BaseModel):
    """Account details response."""

    id: str
    organization_name: Optional[str] = None
    created_at: str
    updated_at: str


class AccountDetailsUpdate(BaseModel):
    """Account details update request."""

    organization_name: Optional[str] = None


@router.get("/account/features")
async def list_account_features(
    current_user: Annotated[str, Depends(get_current_active_user)],
):
    """List available features for the current account.

    Returns a list of features available to the authenticated user's account.
    This endpoint is used by the frontend to show/hide features based on
    the account's license or subscription.

    Returns:
        Dict with:
            - features: List of available feature names
            - details: Dict mapping feature names to feature info
    """
    logger.info(f"Listing features for user {current_user}")

    # Get list of available features
    available_features = get_available_features(current_user)

    # Get detailed info for each feature
    feature_details = {}
    for feature in Feature:
        feature_details[feature.value] = get_feature_info(feature)

    return {
        "features": available_features,
        "details": feature_details,
    }


@router.get("/account/details", response_model=AccountDetailsResponse)
async def get_account_details(
    account: Annotated[Account, Depends(get_account_for_user)],
):
    """Get current account details.

    Returns:
        Account details including organization name
    """
    return AccountDetailsResponse(
        id=str(account.id),
        organization_name=account.organization_name,
        created_at=account.created_at.isoformat(),
        updated_at=account.updated_at.isoformat(),
    )


@router.patch("/account/details", response_model=AccountDetailsResponse)
async def update_account_details(
    update_data: AccountDetailsUpdate,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
):
    """Update current account details.

    Args:
        update_data: Account update data
        account: Current user's account
        db: Database session

    Returns:
        Updated account details
    """
    # Update account
    update_dict = update_data.model_dump(exclude_unset=True)
    updated_account = crud_account.update(db=db, db_obj=account, obj_in=update_dict)
    db.commit()
    db.refresh(updated_account)

    return AccountDetailsResponse(
        id=str(updated_account.id),
        organization_name=updated_account.organization_name,
        created_at=updated_account.created_at.isoformat(),
        updated_at=updated_account.updated_at.isoformat(),
    )
