"""Server entry point for SpaceBridge."""

import logging
import os
from typing import Optional

import uvicorn

from spacebridge.logging import configure_logging

logger = logging.getLogger(__name__)


def start_server(
    host: Optional[str] = None, port: Optional[int] = None, debug: Optional[bool] = None
) -> None:
    """Start the SpaceBridge server.

    Args:
        host: Host to bind to, defaults to HOST env var or 0.0.0.0
        port: Port to bind to, defaults to PORT env var or 8000
        debug: Whether to run in debug mode, defaults to DEBUG env var or False
    """
    # Configure logging
    configure_logging()

    # Set server parameters from environment or defaults
    host = host or os.getenv("HOST", "0.0.0.0")
    port = port or int(os.getenv("PORT", "8000"))
    debug = (
        debug if debug is not None else os.getenv("DEBUG", "false").lower() == "true"
    )

    # Log server startup
    logger.info(f"Starting SpaceBridge server on {host}:{port} (debug={debug})")

    # Start the server
    uvicorn.run(
        "spacebridge.api.app:create_app",
        host=host,
        port=port,
        reload=debug,
        factory=True,
    )


if __name__ == "__main__":
    start_server()
