"""Instance registration service for self-hosted Preloop installations.

This service:
1. Creates/retrieves the local instance record on startup
2. Sends version check POST to preloop.ai for telemetry
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from preloop_ai import __version__

logger = logging.getLogger(__name__)

# Preloop.ai version check endpoint
VERSION_CHECK_URL = "https://preloop.ai/api/v1/version"

# Environment variable to disable telemetry
DISABLE_TELEMETRY_ENV = "PRELOOP_DISABLE_TELEMETRY"


def get_or_create_instance() -> Optional["Instance"]:
    """Get or create the local instance record.

    For self-hosted installations, this creates a single Instance record
    that represents this installation. The instance_uuid is generated once
    and persisted in the database.

    Returns:
        The Instance record, or None if database is not available.
    """
    from preloop_models.db.session import get_db_session
    from preloop_models.models import Instance

    try:
        db = next(get_db_session())
        try:
            # Check if we already have a local instance record
            instance = db.query(Instance).first()

            if instance:
                # Update version if it changed
                if instance.version != __version__:
                    logger.info(
                        f"Updating instance version from {instance.version} to {__version__}"
                    )
                    instance.version = __version__
                    instance.last_seen = datetime.now(timezone.utc)
                    db.commit()
                    db.refresh(instance)
                return instance

            # Create new instance record
            edition = "enterprise" if _is_enterprise() else "oss"
            instance = Instance(
                instance_uuid=uuid.uuid4(),
                version=__version__,
                edition=edition,
                first_seen=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc),
                is_active=True,
            )
            db.add(instance)
            db.commit()
            db.refresh(instance)

            logger.info(
                f"Created new instance record: {instance.instance_uuid} "
                f"(version={instance.version}, edition={instance.edition})"
            )
            return instance

        finally:
            db.close()

    except Exception as e:
        logger.warning(f"Could not get/create instance record: {e}")
        return None


def _is_enterprise() -> bool:
    """Check if this is an enterprise installation."""
    # Check for enterprise plugins or features
    try:
        # If proprietary plugins are available, it's enterprise
        import preloop_ai.plugins.proprietary  # noqa: F401

        return True
    except ImportError:
        return False


async def send_version_check(instance: "Instance") -> bool:
    """Send version check POST to preloop.ai.

    This is opt-out telemetry that helps us understand adoption.
    Set PRELOOP_DISABLE_TELEMETRY=true to disable.

    Args:
        instance: The local instance record.

    Returns:
        True if successful, False otherwise.
    """
    if os.getenv(DISABLE_TELEMETRY_ENV, "").lower() == "true":
        logger.debug("Telemetry disabled via environment variable")
        return False

    try:
        payload = {
            "instance_uuid": str(instance.instance_uuid),
            "version": instance.version,
            "edition": instance.edition,
            "metadata": instance.metadata_ or {},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(VERSION_CHECK_URL, json=payload)

            if response.status_code == 200:
                data = response.json()
                if data.get("update_available"):
                    logger.info(
                        f"Update available: {data.get('current_version')} "
                        f"(you have {instance.version})"
                    )
                return True
            else:
                logger.debug(
                    f"Version check returned {response.status_code}: {response.text}"
                )
                return False

    except httpx.TimeoutException:
        logger.debug("Version check timed out")
        return False
    except Exception as e:
        logger.debug(f"Version check failed: {e}")
        return False


async def register_instance() -> None:
    """Register the local instance and send version check.

    Called during application startup. Creates the local instance record
    and sends a version check to preloop.ai in the background.
    """
    logger.info("Registering instance...")

    instance = get_or_create_instance()
    if not instance:
        logger.warning("Could not register instance - database not available")
        return

    logger.info(
        f"Instance registered: {instance.instance_uuid} "
        f"(version={instance.version}, edition={instance.edition})"
    )

    # Send version check in background (don't block startup)
    asyncio.create_task(_background_version_check(instance))


async def _background_version_check(instance: "Instance") -> None:
    """Background task to send version check."""
    # Small delay to let the app fully start
    await asyncio.sleep(5)

    success = await send_version_check(instance)
    if success:
        logger.debug("Version check sent successfully")
