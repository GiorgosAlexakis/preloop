"""FastAPI application for SpaceBridge.

This FastAPI application provides HTTP endpoints for authentication and management
of issue tracking systems.
"""

import logging
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
from pyinstrument import Profiler
from pyinstrument.renderers import SpeedscopeRenderer
from starlette.middleware.base import BaseHTTPMiddleware

from spacebridge import __version__
from spacebridge.api.middleware import UIRoutingMiddleware
from fastapi.encoders import jsonable_encoder
from spacebridge.api.auth import auth_router, get_current_active_user
from spacebridge.api.endpoints import (
    comments,
    health,
    issues,
    issue_compliance,
    issue_dependencies,
    organizations,
    projects,
    search as search_router,
    trackers,
    version,
    embedding as embedding_router,
    issue_duplicates,
    webhooks,
    flows,
    ai_models,
    billing,
    websockets,
    mcp as mcp_router,
)
from spacemodels.sentry import init_sentry
from spacemodels.db.session import get_db_session
from spacemodels.db.setup import setup_database
from spacemodels.models.api_usage import ApiUsage
from spacesync.services.event_bus import connect_nats, close_nats  # NATS integration


logger = logging.getLogger(__name__)


class PyinstrumentMiddleware(BaseHTTPMiddleware):
    """Middleware to profile requests using pyinstrument."""

    async def dispatch(self, request: Request, call_next):
        """Process a request and profile it.
        Args:
            request: The request to process.
            call_next: The next middleware to call.
        Returns:
            The response from the next middleware.
        """
        profiling_enabled = os.getenv("PROFILING_ENABLED", "false").lower() == "true"
        if not profiling_enabled or not request.url.path.startswith("/api/v1"):
            return await call_next(request)

        profiler = Profiler()
        start_time = time.time()

        profiler.start()
        response = await call_next(request)
        profiler.stop()

        duration = time.time() - start_time

        # Ensure the profiling directory exists
        output_dir = Path("/tmp/profiling")
        output_dir.mkdir(exist_ok=True)

        # Generate a unique filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        path_slug = request.url.path.replace("/", "_").strip("_")
        filename_base = f"{timestamp}_{request.method}_{path_slug}"

        # Save HTML report
        html_path = output_dir / f"{filename_base}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(profiler.output_html())

        # Save speedscope report
        speedscope_path = output_dir / f"{filename_base}.speedscope.json"
        renderer = SpeedscopeRenderer()
        with open(speedscope_path, "w", encoding="utf-8") as f:
            f.write(renderer.render(profiler.last_session))

        logger.info(
            f"Profiled request {request.method} {request.url.path} in {duration:.4f}s. "
            f"Reports saved to {html_path} and {speedscope_path}"
        )

        return response


class ApiUsageMiddleware(BaseHTTPMiddleware):
    """Middleware to track API usage."""

    async def dispatch(self, request: Request, call_next):
        """Process a request and track API usage.

        Args:
            request: The request to process.
            call_next: The next middleware to call.

        Returns:
            The response from the next middleware.
        """
        # Skip tracking for non-api routes
        path = request.url.path
        if (
            not path.startswith("/api/v1")
            or path.startswith("/api/v1/health")
            or path.startswith("/api/v1/billing/plans")
            or path.startswith("/api/v1/billing/create-checkout-session")
            or path.startswith("/api/v1/billing/webhooks")
        ):
            return await call_next(request)

        start_time = datetime.now(timezone.utc)
        response = await call_next(request)
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Extract tracking information
        method = request.method
        status_code = response.status_code
        user = None
        action_type = None

        # Determine the action type based on the path and method
        if "/issues" in path:
            if method == "POST":
                action_type = "create_issue"
            elif method == "PUT" or method == "PATCH":
                action_type = "update_issue"
            elif method == "DELETE":
                action_type = "delete_issue"

        # Get username from auth token if available
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            from spacebridge.api.auth.jwt import decode_token

            try:
                token = auth_header.replace("Bearer ", "")
                token_data = decode_token(token)
                user = getattr(token_data, "sub", None)
            except Exception:
                # Ignore errors in token decoding
                pass

        # Log usage in database
        if user and status_code < 500:  # Only log successful API calls
            try:
                session_generator = get_db_session()
                session = next(session_generator)

                try:
                    # Create usage entry
                    usage_entry = ApiUsage(
                        username=user,
                        endpoint=path,
                        method=method,
                        status_code=status_code,
                        duration=duration,
                        action_type=action_type,
                        timestamp=start_time,
                    )

                    session.add(usage_entry)
                    session.commit()
                finally:
                    session.close()
                    try:
                        # Clean up the generator
                        next(session_generator, None)
                    except StopIteration:
                        pass
            except Exception as e:
                # Don't let tracking issues affect the response
                logger.error(f"Error logging API usage: {str(e)}")

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting up application and database...")

    # Initialize Sentry if DSN is configured
    init_sentry()

    # Initialize database connection and optionally create tables.
    logger.info("Setting up database connection...")
    try:
        # Check if running in test mode or if INIT_DB is set
        init_db = os.getenv("INIT_DB", "false").lower() == "true"
        if init_db:
            logger.info("Initializing database schema...")
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://user:password@db:5432/spacebridge",
            )
            setup_database(database_url)
            logger.info("Database schema initialized.")
        else:
            logger.info("Skipping database schema initialization (INIT_DB not true).")

        # Check if test data initialization is enabled
        if os.getenv("INIT_TEST_DATA", "false").lower() == "true":
            logger.info("Initializing test data...")
            # Import and run the test data initialization script
            from scripts.init_test_data import main as init_data_main

            init_data_main()
            logger.info("Test data initialization complete.")

    except Exception as e:
        logger.error(f"Database setup failed: {e}", exc_info=True)
        raise RuntimeError("Database setup failed") from e

    # Connect to NATS
    logger.info("Connecting to NATS...")
    try:
        await connect_nats()
        logger.info("NATS connection established.")
    except Exception as e:
        logger.error(f"NATS connection failed: {e}", exc_info=True)
        raise RuntimeError("NATS connection failed") from e

    # Start the NATS consumer for WebSocket broadcasting
    from spacebridge.services.websocket_manager import manager, nats_consumer
    import asyncio

    # Start the NATS consumer as a background task
    loop = asyncio.get_event_loop()
    app.state.nats_consumer_task = loop.create_task(nats_consumer(manager))
    logger.info("NATS consumer for WebSockets started.")

    yield

    # Shutdown logic
    # Cancel the NATS consumer task
    if hasattr(app.state, "nats_consumer_task"):
        app.state.nats_consumer_task.cancel()
        logger.info("NATS consumer for WebSockets stopped.")

    logger.info("Shutting down NATS connection...")
    try:
        await close_nats()
        logger.info("NATS connection closed.")
    except Exception as e:
        logger.error(f"Error closing NATS connection: {e}", exc_info=True)

    logger.info("Shutting down application...")
    # Restore the original jsonable_encoder
    import fastapi.encoders

    if hasattr(app.state, "original_jsonable_encoder"):
        fastapi.encoders.jsonable_encoder = app.state.original_jsonable_encoder
        logger.info("Restored original jsonable_encoder.")
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured FastAPI application.
    """
    # Load environment variables from .env file
    # load_dotenv()

    # Define base directory relative to this file's location
    base_dir = Path(__file__).resolve().parent.parent.parent
    mcp = FastMCP(name="Spacebridge MCP")

    @mcp.tool
    async def get_issue(issue: str):
        return await mcp_router.get_issue(issue)

    @mcp.tool
    async def create_issue(
        project: str,
        title: str,
        description: str,
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        similarity_search: bool = True,
    ):
        return await mcp_router.create_issue(
            project=project,
            title=title,
            description=description,
            labels=labels,
            assignee=assignee,
            priority=priority,
            status=status,
            similarity_search=similarity_search,
        )

    @mcp.tool
    async def update_issue(
        issue: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ):
        return await mcp_router.update_issue(
            issue, title, description, status, priority, assignee, labels
        )

    @mcp.tool
    async def search(
        query: str,
        project: Optional[str] = None,
        limit: int = 10,
    ):
        return await mcp_router.search(
            query=query,
            project=project,
            limit=limit,
            search_type="similarity",
        )

    @mcp.tool
    async def estimate_compliance(
        issues: List[str],
    ):
        return await mcp_router.estimate_compliance(issues)

    @mcp.tool
    async def improve_compliance(
        issues: List[str],
    ):
        return await mcp_router.improve_compliance(issues)

    mcp_app = mcp.streamable_http_app(path="/v1")

    # Combine both lifespans
    @asynccontextmanager
    async def combined_lifespan(app: FastAPI):
        # Run both lifespans
        async with lifespan(app):
            async with mcp_app.lifespan(app):
                yield

    # Initialize FastAPI app
    app = FastAPI(
        title="SpaceBridge API",
        description="REST API for SpaceBridge issue tracking management",
        version=__version__,
        openapi_url="/api/v1/openapi.json",  # Keep OpenAPI schema URL
        docs_url=None,  # Disable the automatic docs at /docs
        redoc_url=None,  # Disable the automatic redoc at /redoc
        lifespan=combined_lifespan,
    )

    app.mount(
        "/mcp",
        mcp_app,
        name="mcp",
    )

    # Override the default JSON encoder to handle datetime objects
    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)

    # Replace the default jsonable_encoder function with our custom one
    def custom_jsonable_encoder(obj, *args, **kwargs):
        # First let FastAPI's encoder prepare the object
        encoded = jsonable_encoder(obj, *args, **kwargs)
        # Then manually process any datetime objects that might have been missed
        if isinstance(encoded, dict):
            for key, value in encoded.items():
                if isinstance(value, datetime):
                    encoded[key] = value.isoformat()
        elif isinstance(encoded, list):
            for i, item in enumerate(encoded):
                if isinstance(item, datetime):
                    encoded[i] = item.isoformat()
                elif isinstance(item, dict):
                    for key, value in item.items():
                        if isinstance(value, datetime):
                            item[key] = value.isoformat()
        return encoded

    # Patch FastAPI's jsonable_encoder
    import fastapi.encoders

    app.state.original_jsonable_encoder = fastapi.encoders.jsonable_encoder
    fastapi.encoders.jsonable_encoder = custom_jsonable_encoder

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add profiling middleware
    app.add_middleware(PyinstrumentMiddleware)

    # Add API usage tracking
    if os.getenv("TESTING") != "true":
        app.add_middleware(ApiUsageMiddleware)
    app.add_middleware(UIRoutingMiddleware)

    # --- Static Files Setup ---
    mkdocs_site_dir = base_dir / "site"  # Directory where 'mkdocs build' outputs

    # Mount general static files (CSS, JS for landing/auth pages)
    try:
        app.mount(
            "/assets",
            StaticFiles(directory=str(base_dir / "SpaceLit" / "dist" / "assets")),
            name="spacelit_assets",
        )
        app.mount(
            "/images",
            StaticFiles(directory=str(base_dir / "SpaceLit" / "public" / "images")),
            name="spacelit_images",
        )
    except Exception as e:
        logger.error(f"Failed to mount SpaceLit static files: {e}")

    # --- Mount MkDocs Site ---
    # Check if the 'site' directory exists (created by 'mkdocs build')
    if mkdocs_site_dir.exists() and mkdocs_site_dir.is_dir():
        logger.info(f"Mounting MkDocs site from: {mkdocs_site_dir}")
        app.mount(
            "/docs",  # Serve the built MkDocs site here
            StaticFiles(directory=str(mkdocs_site_dir), html=True),
            name="documentation",
        )
    else:
        logger.warning(
            f"MkDocs site directory '{mkdocs_site_dir}' not found or not a directory. Documentation will not be served at /docs."
        )

        # Optionally, mount a placeholder or raise an error during development
        @app.get("/docs", include_in_schema=False)
        async def docs_placeholder():
            return HTMLResponse(
                """
                <html>
                    <head><title>Documentation Not Found</title></head>
                    <body>
                        <h1>Documentation Not Found</h1>
                        <p>The documentation site has not been built. Please run 'mkdocs build' in the project root.</p>
                        <p>API documentation is available at <a href="/docs/api">/docs/api</a>.</p>
                    </body>
                </html>
            """,
                status_code=404,
            )

    # --- Custom API Docs Routes (Moved to /docs/api and /docs/redoc) ---
    @app.get("/docs/api", include_in_schema=False)  # Changed path
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
        )

    @app.get("/docs/redoc", include_in_schema=False)  # Changed path
    async def custom_redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js",
        )

    # Add custom OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Add security schemes and requirements
        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token for authentication",
            }
        }

        # Apply security to all endpoints except auth endpoints, landing page, health checks, and docs
        excluded_prefixes = [
            "/api/v1/auth",
            "/api/v1/billing/plans",
            "/api/v1/billing/create-checkout-session",
            "/",
            "/static",
            "/docs",  # Exclude the main docs path and subpaths
            "/register",
            "/logout",
            "/api/v1/health",
        ]
        for path in openapi_schema["paths"]:
            # Check if path starts with any excluded prefix
            is_excluded = False
            for prefix in excluded_prefixes:
                if path == prefix or (prefix != "/" and path.startswith(prefix)):
                    is_excluded = True
                    break
            if not is_excluded:
                # Check if path is exactly /api/v1/openapi.json
                if path == app.openapi_url:
                    continue  # Don't require auth for the schema itself

                for method in openapi_schema["paths"][path]:
                    if method.lower() != "options":  # Skip OPTIONS method
                        openapi_schema["paths"][path][method]["security"] = [
                            {"bearerAuth": []}
                        ]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # Add routers
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(version.router, prefix="/api/v1", tags=["Version"])
    app.include_router(
        trackers.router,
        prefix="/api/v1",
        tags=["Trackers"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        issue_dependencies.router,
        prefix="/api/v1",
        tags=["Issues"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        organizations.router,
        prefix="/api/v1",
        tags=["Organizations"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        projects.router,
        prefix="/api/v1",
        tags=["Projects"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        issues.router,
        prefix="/api/v1",
        tags=["Issues"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        issue_compliance.router,
        prefix="/api/v1",
        tags=["Issues"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        comments.router,
        prefix="/api/v1",
        tags=["Comments"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        search_router.router,
        prefix="/api/v1",
        tags=["Search"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        embedding_router.router,
        prefix="/api/v1",
        tags=["Embeddings"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        ai_models.router,
        prefix="/api/v1",
        tags=["AI Models"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        issue_duplicates.router,
        prefix="/api/v1",
        tags=["Issue Duplicates"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        version.router, prefix="/api/v1", tags=["Version"]
    )  # No auth dependency for version check
    app.include_router(webhooks.router, prefix="/api/v1", tags=["Webhooks"])
    app.include_router(
        flows.router,
        prefix="/api/v1",
        tags=["Flows"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        ai_models.router,
        prefix="/api/v1",
        tags=["AI Models"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        billing.router,
        prefix="/api/v1",
        tags=["Billing"],
        # dependencies=[Depends(get_current_active_user)],
    )

    # WebSocket router
    app.include_router(websockets.router, prefix="/api/v1", tags=["WebSockets"])

    # --- SPA Static Files (Production) ---
    # In production, serve the built Lit frontend from the root
    # This should be mounted *after* all API routes are defined.
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    if not dev_mode:
        logger.info("DEV_MODE is false, serving SPA from 'SpaceLit/dist'")
        try:
            app.mount(
                "/",
                StaticFiles(directory=str(base_dir / "SpaceLit" / "dist"), html=True),
                name="spa",
            )
        except Exception as e:
            logger.error(f"Failed to mount SPA static files: {e}")
    else:
        logger.info("DEV_MODE is true, SPA is served by the frontend dev server.")

    app.mount("/mcp", mcp_app)
    return app
