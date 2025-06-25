"""FastAPI application for SpaceBridge.

This FastAPI application provides HTTP endpoints for authentication and management
of issue tracking systems.
"""

import logging
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from spacebridge.api.middleware import UIRoutingMiddleware
from fastapi.encoders import jsonable_encoder

from spacebridge import __version__
from spacebridge.api.auth import auth_router, get_current_active_user
from spacebridge.api.endpoints import (
    comments,
    health,
    issues,
    organizations,
    projects,
    search,
    trackers,
    version,
    embedding as embedding_router,
    llm_models,
    issue_duplicates,
    webhooks,
)
from spacemodels.db.session import get_db_session
from spacemodels.db.setup import setup_database
from spacemodels.models.api_usage import ApiUsage

logger = logging.getLogger(__name__)


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
        # Also skip tracking for the new /docs and existing static/template routes
        if (
            not path.startswith("/api/v1")
            or path.startswith("/api/v1/health")
            or path.startswith("/docs")
            or path.startswith("/static")
            or path == "/"
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
        # Depending on the severity, you might want to exit or handle differently
        # raise RuntimeError("Database setup failed") from e

    yield

    # Shutdown logic
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

    # Initialize FastAPI app
    app = FastAPI(
        title="SpaceBridge API",
        description="REST API for SpaceBridge issue tracking management",
        version=__version__,
        openapi_url="/api/v1/openapi.json",  # Keep OpenAPI schema URL
        docs_url=None,  # Disable the automatic docs at /docs
        redoc_url=None,  # Disable the automatic redoc at /redoc
        lifespan=lifespan,  # Use the new lifespan context manager
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

    # Add API usage tracking
    app.add_middleware(ApiUsageMiddleware)
    app.add_middleware(UIRoutingMiddleware)

    # --- Static Files Setup ---
    static_dir = base_dir / "static"
    static_css_dir = static_dir / "css"
    static_js_dir = static_dir / "js"
    templates_dir = base_dir / "templates"
    mkdocs_site_dir = base_dir / "site"  # Directory where 'mkdocs build' outputs

    os.makedirs(static_dir, exist_ok=True)
    os.makedirs(static_css_dir, exist_ok=True)
    os.makedirs(static_js_dir, exist_ok=True)
    os.makedirs(templates_dir, exist_ok=True)

    logger.info(f"Static files directory: {static_dir}")
    logger.info(f"Templates directory: {templates_dir}")

    # Mount general static files (CSS, JS for landing/auth pages)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
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
            "/",
            "/static",
            "/docs",  # Exclude the main docs path and subpaths
            "/register",
            "/verify-email",
            "/forgot-password",
            "/reset-password",
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
        comments.router,
        prefix="/api/v1",
        tags=["Comments"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        search.router,
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
        llm_models.router,
        prefix="/api/v1",
        tags=["LLM Models"],
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
    app.include_router(
        webhooks.router, prefix="/api/v1", tags=["Webhooks"]
    )  # No user auth needed for incoming webhooks

    # --- HTML Page Routes ---
    templates = Jinja2Templates(directory=str(templates_dir))

    # Create landing page template if not exists (simplified)
    landing_page_path = templates_dir / "landing.html"
    if not landing_page_path.exists():
        # (HTML content omitted for brevity - assume it exists or is created elsewhere)
        logger.warning(f"{landing_page_path} not found. Landing page will not work.")
        pass  # Don't overwrite if managed elsewhere

    # Create other page templates if not exist (simplified)
    for page_name in [
        "login",
        "register",
        "forgot-password",
        "reset-password",
        "verify-email",
        "logout",
        "dashboard",
        "trackers",
        "privacy",
        "terms",
    ]:
        page_path = templates_dir / f"{page_name}.html"
        if not page_path.exists():
            # (HTML content omitted for brevity)
            logger.warning(f"{page_path} not found. Page / {page_name} will not work.")
            pass  # Don't overwrite

    @app.get("/", response_class=HTMLResponse, tags=["Pages"])
    async def landing_page(request: Request):
        return templates.TemplateResponse("landing.html", {"request": request})

    @app.get("/login", response_class=HTMLResponse, tags=["Pages"])
    async def login_page(request: Request):
        return templates.TemplateResponse("login.html", {"request": request})

    @app.get("/forgot-password", response_class=HTMLResponse, tags=["Pages"])
    async def forgot_password_page(request: Request):
        # Placeholder - Implement actual logic if needed
        return templates.TemplateResponse("forgot-password.html", {"request": request})

    @app.get("/reset-password", response_class=HTMLResponse, tags=["Pages"])
    async def reset_password_page(request: Request):
        # Placeholder - Implement actual logic if needed
        return templates.TemplateResponse("reset-password.html", {"request": request})

    @app.get("/verify-email", response_class=HTMLResponse, tags=["Pages"])
    async def verify_email_page(request: Request):
        # Placeholder - Implement actual logic if needed
        return templates.TemplateResponse("verify-email.html", {"request": request})

    @app.get("/logout", response_class=HTMLResponse, tags=["Pages"])
    async def logout_page(request: Request):
        # Placeholder - Implement actual logic if needed
        return templates.TemplateResponse("logout.html", {"request": request})

    @app.get("/register", response_class=HTMLResponse, tags=["Pages"])
    async def register_page(request: Request):
        return templates.TemplateResponse("register.html", {"request": request})

    @app.get("/dashboard", response_class=HTMLResponse, tags=["Pages"])
    async def dashboard_page(request: Request):
        # Placeholder - Requires auth
        return templates.TemplateResponse("dashboard.html", {"request": request})

    @app.get("/explore", response_class=HTMLResponse, tags=["Pages"])
    async def explore_page(request: Request):
        # Placeholder - Requires auth
        return templates.TemplateResponse("explore.html", {"request": request})

    @app.get("/trackers", response_class=HTMLResponse, tags=["Pages"])
    async def trackers_page(request: Request):
        # Placeholder - Requires auth
        return templates.TemplateResponse("trackers.html", {"request": request})

    @app.get("/privacy", response_class=HTMLResponse, tags=["Pages"])
    async def privacy_page(request: Request):
        return templates.TemplateResponse("privacy.html", {"request": request})

    @app.get("/terms", response_class=HTMLResponse, tags=["Pages"])
    async def terms_page(request: Request):
        return templates.TemplateResponse("terms.html", {"request": request})

    @app.get("/whatis-mcp", response_class=HTMLResponse, tags=["Pages"])
    async def whatis_mcp_page(request: Request):
        # Placeholder - Implement actual logic if needed
        return templates.TemplateResponse("whatis-mcp.html", {"request": request})

    # --- SPA Static Files (Production) ---
    # In production, serve the built Lit frontend from the root
    # This should be mounted *after* all API routes are defined.
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    if not dev_mode:
        logger.info("DEV_MODE is false, serving SPA from 'SpaceLit/dist'")
        app.mount(
            "/",
            StaticFiles(directory=str(base_dir / "SpaceLit" / "dist"), html=True),
            name="spa",
        )
    else:
        logger.info("DEV_MODE is true, SPA is served by the frontend dev server.")

    return app
