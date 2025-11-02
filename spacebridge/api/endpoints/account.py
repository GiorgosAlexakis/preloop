"""Account-related endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from spacebridge.api.auth import get_current_active_user
from spacebridge.license import Feature, get_available_features, get_feature_info

logger = logging.getLogger(__name__)

router = APIRouter()


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
