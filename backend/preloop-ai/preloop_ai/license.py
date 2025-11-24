"""License and feature flag system for Preloop AI.

This module provides a simple feature flag system that allows
differentiating between open source and proprietary features.
"""

import logging
from enum import Enum
from functools import wraps
from typing import Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class Feature(str, Enum):
    """Available features in Preloop AI.

    Features are used to gate functionality based on license or plan.
    Open source features are available to everyone, while proprietary
    features require a valid license or subscription.
    """

    # Phase 0: Open Source Core
    BASIC_APPROVAL = "basic_approval"  # Simple preloop approval with Slack/Mattermost
    APPROVAL_RULES = "approval_rules"  # CEL-based conditional approval (Phase 1)
    ARGUMENT_EVALUATION = "argument_evaluation"  # Argument-based conditions

    # Phase 2+: Proprietary Features
    STATE_EVALUATION = "state_evaluation"  # State-based conditions (proprietary)
    RISK_EVALUATION = "risk_evaluation"  # Risk-based conditions (proprietary)
    MULTI_STAGE_APPROVAL = "multi_stage_approval"  # Multi-stage workflows (proprietary)
    CONSENSUS_APPROVAL = "consensus_approval"  # Consensus voting (proprietary)


# Define which features are open source vs proprietary
OPEN_SOURCE_FEATURES = {
    Feature.BASIC_APPROVAL,
    Feature.APPROVAL_RULES,
    Feature.ARGUMENT_EVALUATION,
}

PROPRIETARY_FEATURES = {
    Feature.STATE_EVALUATION,
    Feature.RISK_EVALUATION,
    Feature.MULTI_STAGE_APPROVAL,
    Feature.CONSENSUS_APPROVAL,
}


def is_feature_available(feature: Feature, account_id: Optional[str] = None) -> bool:
    """Check if a feature is available for the given account.

    Args:
        feature: The feature to check.
        account_id: The account ID to check (unused in Phase 0).

    Returns:
        True if the feature is available, False otherwise.

    Note:
        In Phase 0, all open source features are available to everyone.
        Proprietary features always return False.
        In future phases, this will check account subscriptions/licenses.
    """
    # Phase 0: Only open source features are available
    if feature in OPEN_SOURCE_FEATURES:
        return True

    # Proprietary features not available in Phase 0
    if feature in PROPRIETARY_FEATURES:
        logger.debug(
            f"Feature {feature.value} is a proprietary feature not available in Phase 0"
        )
        return False

    # Unknown feature
    logger.warning(f"Unknown feature requested: {feature.value}")
    return False


def has_feature(feature: Feature, account_id: Optional[str] = None) -> bool:
    """Alias for is_feature_available for convenience.

    Args:
        feature: The feature to check.
        account_id: The account ID to check (unused in Phase 0).

    Returns:
        True if the feature is available, False otherwise.
    """
    return is_feature_available(feature, account_id)


def require_feature(feature: Feature):
    """Decorator to require a feature for an endpoint.

    This decorator checks if the specified feature is available for the
    account making the request. If not, it raises a 403 Forbidden error.

    Args:
        feature: The feature required for this endpoint.

    Returns:
        Decorated function that checks feature availability.

    Raises:
        HTTPException: 403 Forbidden if feature is not available.

    Example:
        @router.post("/api/v1/tools/{tool_id}/approval-rules")
        @require_feature(Feature.APPROVAL_RULES)
        async def create_approval_rule(...):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract account_id from kwargs if present
            account_id = kwargs.get("account_id")

            # Check if feature is available
            if not is_feature_available(feature, account_id):
                logger.warning(
                    f"Feature {feature.value} not available for account {account_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "feature_not_available",
                        "message": f"The feature '{feature.value}' is not available for your account",
                        "feature": feature.value,
                    },
                )

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract account_id from kwargs if present
            account_id = kwargs.get("account_id")

            # Check if feature is available
            if not is_feature_available(feature, account_id):
                logger.warning(
                    f"Feature {feature.value} not available for account {account_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "feature_not_available",
                        "message": f"The feature '{feature.value}' is not available for your account",
                        "feature": feature.value,
                    },
                )

            return func(*args, **kwargs)

        # Return appropriate wrapper based on whether function is async
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def get_available_features(account_id: Optional[str] = None) -> list[str]:
    """Get list of available features for an account.

    Args:
        account_id: The account ID to check (unused in Phase 0).

    Returns:
        List of feature names available for the account.
    """
    available = []

    for feature in Feature:
        if is_feature_available(feature, account_id):
            available.append(feature.value)

    return available


def get_feature_info(feature: Feature) -> dict:
    """Get information about a feature.

    Args:
        feature: The feature to get information about.

    Returns:
        Dictionary with feature information.
    """
    is_open_source = feature in OPEN_SOURCE_FEATURES
    is_proprietary = feature in PROPRIETARY_FEATURES

    return {
        "name": feature.value,
        "is_open_source": is_open_source,
        "is_proprietary": is_proprietary,
        "is_available": is_feature_available(feature),
    }
