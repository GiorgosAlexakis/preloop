"""QR code service for mobile device registration."""

import secrets
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# In-memory token store (TODO: move to Redis for production)
_registration_tokens: Dict[str, Dict[str, Any]] = {}


def generate_registration_token(
    user_id: uuid.UUID,
    api_url: str,
    expiry_minutes: int = 15,
) -> Dict[str, Any]:
    """Generate a registration token and QR code data.

    Args:
        user_id: User ID for the registration.
        api_url: Base API URL for the mobile app to connect to.
        expiry_minutes: Token expiry time in minutes.

    Returns:
        Dict with token, qr_data, and expiry.
    """
    # Generate secure random token
    token = secrets.token_urlsafe(32)

    # Calculate expiry
    expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)

    # Store token
    _registration_tokens[token] = {
        "user_id": str(user_id),
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
    }

    # Build QR code data (URL that mobile app will scan)
    # Format: HTTPS URL for Universal Links (iOS) and App Links (Android)
    # This will open the app if installed, or show web page with app store links
    qr_data = f"{api_url}/api/v1/notification-preferences/register-device?token={token}"

    return {
        "token": token,
        "qr_data": qr_data,
        "expires_at": expires_at.isoformat(),
        "expires_in_seconds": expiry_minutes * 60,
    }


def validate_registration_token(token: str) -> Optional[uuid.UUID]:
    """Validate a registration token and return the user ID.

    Args:
        token: Registration token to validate.

    Returns:
        User ID if valid, None if invalid or expired.
    """
    token_data = _registration_tokens.get(token)

    if not token_data:
        logger.warning(f"Invalid registration token: {token[:8]}...")
        return None

    # Check if expired
    if datetime.utcnow() > token_data["expires_at"]:
        logger.warning(f"Expired registration token: {token[:8]}...")
        # Clean up expired token
        del _registration_tokens[token]
        return None

    # Token is valid
    user_id = uuid.UUID(token_data["user_id"])

    # Remove token after successful validation (one-time use)
    del _registration_tokens[token]

    logger.info(f"Validated registration token for user {user_id}")

    return user_id


def cleanup_expired_tokens() -> int:
    """Clean up expired registration tokens.

    Returns:
        Number of tokens cleaned up.
    """
    now = datetime.utcnow()
    expired_tokens = [
        token
        for token, data in _registration_tokens.items()
        if now > data["expires_at"]
    ]

    for token in expired_tokens:
        del _registration_tokens[token]

    if expired_tokens:
        logger.info(f"Cleaned up {len(expired_tokens)} expired registration tokens")

    return len(expired_tokens)
