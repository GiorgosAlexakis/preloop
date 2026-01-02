"""Firebase Cloud Messaging (FCM) service for Android push notifications."""

import json
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Global FCM service instance
_fcm_initialized = False


def _initialize_fcm() -> bool:
    """Initialize Firebase Admin SDK if not already done.

    Environment variables:
        FCM_CREDENTIALS_JSON: JSON string of Firebase service account credentials (preferred for K8s)
        FCM_CREDENTIALS_PATH: Path to Firebase service account JSON file (fallback)

    Returns:
        True if initialization succeeded, False otherwise.
    """
    global _fcm_initialized

    if _fcm_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            _fcm_initialized = True
            return True

        # Try JSON string first (preferred for Kubernetes secrets)
        creds_json = os.getenv("FCM_CREDENTIALS_JSON")
        if creds_json:
            try:
                cred_dict = json.loads(creds_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                _fcm_initialized = True
                logger.info("FCM initialized from FCM_CREDENTIALS_JSON")
                return True
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse FCM_CREDENTIALS_JSON: {e}")

        # Fallback to file path
        creds_path = os.getenv("FCM_CREDENTIALS_PATH")
        if creds_path and os.path.exists(creds_path):
            cred = credentials.Certificate(creds_path)
            firebase_admin.initialize_app(cred)
            _fcm_initialized = True
            logger.info(f"FCM initialized from {creds_path}")
            return True

        logger.warning(
            "FCM not configured (no FCM_CREDENTIALS_JSON or FCM_CREDENTIALS_PATH)"
        )
        return False

    except ImportError:
        logger.warning("firebase-admin package not installed")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize FCM: {e}")
        return False


def is_fcm_configured() -> bool:
    """Check if FCM is configured and can be initialized."""
    creds_json = os.getenv("FCM_CREDENTIALS_JSON")
    creds_path = os.getenv("FCM_CREDENTIALS_PATH")
    return bool(creds_json or (creds_path and os.path.exists(creds_path)))


async def send_fcm_notification(
    token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    priority: str = "high",
) -> Dict[str, Any]:
    """Send a push notification via Firebase Cloud Messaging.

    Args:
        token: FCM device token.
        title: Notification title.
        body: Notification body.
        data: Optional data payload.
        priority: Message priority ("high" or "normal").

    Returns:
        Dict with send result including:
            - success: bool
            - message_id: str (if successful)
            - error: str (if failed)
            - invalid_token: bool (if token is invalid/expired)
    """
    if not _initialize_fcm():
        return {"success": False, "error": "FCM not configured"}

    try:
        from firebase_admin import messaging

        # Convert data values to strings (FCM requirement)
        string_data = {}
        if data:
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    string_data[key] = json.dumps(value)
                else:
                    string_data[key] = str(value)

        # Build FCM message
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=string_data,
            token=token,
            android=messaging.AndroidConfig(
                priority=priority,
                notification=messaging.AndroidNotification(
                    channel_id="approvals",
                    priority="max" if priority == "high" else "default",
                ),
            ),
        )

        # Send message
        response = messaging.send(message)
        logger.info(f"FCM notification sent: {response}")

        return {
            "success": True,
            "message_id": response,
        }

    except Exception as e:
        error_str = str(e)
        logger.error(f"Failed to send FCM notification: {error_str}")

        # Check for invalid token errors
        invalid_token = any(
            err in error_str.lower()
            for err in ["not registered", "invalid registration", "unregistered"]
        )

        return {
            "success": False,
            "error": error_str,
            "invalid_token": invalid_token,
        }
