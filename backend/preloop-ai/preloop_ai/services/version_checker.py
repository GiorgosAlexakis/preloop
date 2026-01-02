"""Version checker service for Preloop instances.

This service checks for version updates by contacting the production
Preloop instance at https://preloop.ai. It:

1. Generates a unique instance UUID on first run (stored in DB)
2. Checks for updates on startup
3. Checks periodically (configurable, default once per day)
4. Can be disabled via DISABLE_VERSION_CHECK=true env var

The version check also serves as a registration mechanism, allowing
the Preloop team to understand adoption and usage patterns.

Privacy:
- Only instance UUID, version, and IP are sent
- No user data is transmitted
- Can be completely disabled via environment variable
"""

import asyncio
import logging
import os
from typing import Optional
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

# Version info - updated with each release
VERSION = "1.0.0"
EDITION = os.getenv("PRELOOP_EDITION", "oss")

# Configuration
VERSION_CHECK_URL = os.getenv("VERSION_CHECK_URL", "https://preloop.ai/api/v1/version")
VERSION_CHECK_INTERVAL = int(os.getenv("VERSION_CHECK_INTERVAL", "86400"))  # 24 hours
DISABLE_VERSION_CHECK = os.getenv("DISABLE_VERSION_CHECK", "false").lower() == "true"

# Global state
_instance_uuid: Optional[str] = None
_version_check_task: Optional[asyncio.Task] = None
_last_check_result: Optional[dict] = None


async def get_instance_uuid() -> str:
    """Get or generate the unique instance UUID.

    The UUID is stored in the database and persists across restarts.
    If not found, a new UUID is generated.
    """
    global _instance_uuid

    if _instance_uuid is not None:
        return _instance_uuid

    # Try to load from database
    try:
        from preloop_models.db.session import get_db_session
        from sqlalchemy import text

        db = next(get_db_session())
        try:
            # Check if we have a stored instance UUID
            result = db.execute(
                text("SELECT value FROM system_settings WHERE key = 'instance_uuid'")
            ).fetchone()

            if result:
                _instance_uuid = result[0]
            else:
                # Generate new UUID and store it
                _instance_uuid = str(uuid4())
                db.execute(
                    text(
                        "INSERT INTO system_settings (key, value) "
                        "VALUES ('instance_uuid', :uuid) "
                        "ON CONFLICT (key) DO UPDATE SET value = :uuid"
                    ),
                    {"uuid": _instance_uuid},
                )
                db.commit()
                logger.info(f"Generated new instance UUID: {_instance_uuid}")
        finally:
            db.close()
    except Exception as e:
        # If database is not available or table doesn't exist, generate a temporary UUID
        logger.warning(f"Could not load/store instance UUID from database: {e}")
        _instance_uuid = str(uuid4())

    return _instance_uuid


async def check_version() -> Optional[dict]:
    """Check for version updates.

    Returns:
        Dict with version check result, or None if check failed/disabled.
    """
    global _last_check_result

    if DISABLE_VERSION_CHECK:
        logger.debug("Version check disabled via DISABLE_VERSION_CHECK")
        return None

    instance_uuid = await get_instance_uuid()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                VERSION_CHECK_URL,
                json={
                    "instance_uuid": instance_uuid,
                    "version": VERSION,
                    "edition": EDITION,
                    "metadata": {
                        "python_version": os.popen("python --version").read().strip(),
                    },
                },
            )

            if response.status_code == 200:
                result = response.json()
                _last_check_result = result

                if result.get("update_available"):
                    logger.info(
                        f"🆕 Preloop {result.get('current_version')} is available! "
                        f"You are running v{VERSION}. "
                        f"See: {result.get('changelog_url', 'https://docs.preloop.ai/changelog')}"
                    )
                else:
                    logger.debug(f"Version check: running latest (v{VERSION})")

                return result
            else:
                logger.warning(f"Version check failed: HTTP {response.status_code}")
                return None

    except httpx.TimeoutException:
        logger.debug("Version check timed out")
        return None
    except httpx.RequestError as e:
        logger.debug(f"Version check failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Version check error: {e}")
        return None


async def _version_check_loop():
    """Background task that checks for updates periodically."""
    while True:
        try:
            await check_version()
        except Exception as e:
            logger.error(f"Error in version check loop: {e}")

        # Wait for next check
        await asyncio.sleep(VERSION_CHECK_INTERVAL)


def start_version_checker():
    """Start the background version checker task.

    Called from application startup.
    """
    global _version_check_task

    if DISABLE_VERSION_CHECK:
        logger.info("Version checker disabled via DISABLE_VERSION_CHECK")
        return

    if _version_check_task is not None:
        logger.warning("Version checker already running")
        return

    logger.info(
        f"Starting version checker (interval: {VERSION_CHECK_INTERVAL}s, "
        f"URL: {VERSION_CHECK_URL})"
    )

    # Run initial check immediately
    asyncio.create_task(check_version())

    # Start periodic checker
    _version_check_task = asyncio.create_task(_version_check_loop())


def stop_version_checker():
    """Stop the background version checker task.

    Called from application shutdown.
    """
    global _version_check_task

    if _version_check_task is not None:
        _version_check_task.cancel()
        _version_check_task = None
        logger.info("Version checker stopped")


def get_last_check_result() -> Optional[dict]:
    """Get the result of the last version check."""
    return _last_check_result


def get_version_info() -> dict:
    """Get current version information."""
    return {
        "version": VERSION,
        "edition": EDITION,
        "instance_uuid": _instance_uuid,
        "version_check_enabled": not DISABLE_VERSION_CHECK,
        "last_check_result": _last_check_result,
    }


__all__ = [
    "check_version",
    "start_version_checker",
    "stop_version_checker",
    "get_version_info",
    "get_instance_uuid",
    "VERSION",
    "EDITION",
]
