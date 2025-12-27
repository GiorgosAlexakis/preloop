"""Push notification services for mobile approval notifications."""

import os
import logging
from typing import Optional

from .apns_service import APNsService
from .fcm_service import send_fcm_notification
from .notification_payloads import NotificationPayloadBuilder
from .qr_service import (
    generate_registration_token,
    validate_registration_token,
    check_token_validity,
)

logger = logging.getLogger(__name__)

# Global APNs service instance
_apns_service: Optional[APNsService] = None


def get_apns_service() -> Optional[APNsService]:
    """Get or create APNs service singleton.

    Returns:
        APNsService instance if configured, None otherwise.
    """
    global _apns_service

    if _apns_service is not None:
        return _apns_service

    # Check if APNs is configured
    team_id = os.getenv("APNS_TEAM_ID")
    key_id = os.getenv("APNS_KEY_ID")
    auth_key_path = os.getenv("APNS_AUTH_KEY_PATH")
    bundle_id = os.getenv("APNS_BUNDLE_ID", "spacecode.ai.PreloopAI")
    use_sandbox = os.getenv("APNS_USE_SANDBOX", "true").lower() == "true"

    if not team_id or not key_id or not auth_key_path:
        logger.warning("APNs not configured (missing credentials)")
        return None

    try:
        _apns_service = APNsService(
            team_id=team_id,
            key_id=key_id,
            auth_key_path=auth_key_path,
            bundle_id=bundle_id,
            use_sandbox=use_sandbox,
        )
        logger.info(f"APNs service initialized (sandbox={use_sandbox})")
        return _apns_service
    except Exception as e:
        logger.error(f"Failed to initialize APNs service: {e}")
        return None


__all__ = [
    "APNsService",
    "get_apns_service",
    "NotificationPayloadBuilder",
    "send_fcm_notification",
    "generate_registration_token",
    "validate_registration_token",
    "check_token_validity",
]
