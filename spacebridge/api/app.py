"""FastAPI application for SpaceBridge."""

import logging
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from spacebridge import __version__
from spacebridge.api.endpoints import health, organizations, projects
from spacebridge.api.mcp import mcp_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured FastAPI application.
    """
    # Initialize FastAPI app
    app = FastAPI(
        title="SpaceBridge",
        description="Model Context Protocol server for issue tracker management",
        version=__version__,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # This should be more restrictive in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add routers
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(organizations.router, prefix="/api/v1", tags=["Organizations"])
    app.include_router(projects.router, prefix="/api/v1", tags=["Projects"])
    app.include_router(mcp_router, prefix="/mcp", tags=["MCP"])

    # Root endpoint
    @app.get("/", tags=["Root"])
    def root() -> Dict[str, str]:
        """Root endpoint."""
        return {
            "service": "SpaceBridge",
            "version": __version__,
            "status": "running",
        }

    logger.info(f"SpaceBridge API {__version__} initialized")
    return app
