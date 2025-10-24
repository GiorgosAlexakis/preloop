"""StreamableHTTP transport implementation for MCP with authentication.

This module uses FastMCP's proven transport infrastructure adapted for dynamic tool filtering.
Adapted from fastmcp.server.http.create_streamable_http_app()
"""

import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, Optional

# Use FastMCP's infrastructure
from fastmcp.server.http import (
    StarletteWithLifespan,
    StreamableHTTPASGIApp,
    create_base_app,
)
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.streamable_http import EventStore
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server import Server
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from spacebridge.services.dynamic_mcp_server import (
    has_tracker,
    initialize_dynamic_mcp_server,
)
from spacebridge.services.mcp_http import SpaceBridgeBearerAuthBackend
from spacemodels.db.session import get_db_session as get_db

logger = logging.getLogger(__name__)

# Context variable to store user context for the current request
_user_context_var: ContextVar[Optional[dict]] = ContextVar(
    "mcp_user_context", default=None
)

# TEMPORARY: Global fallback for context propagation across async boundaries
# This stores the last authenticated user's context and works for single-user testing
# NOTE: This is NOT thread-safe and will only work correctly with a single concurrent user
# TODO: Replace with proper session-based context mapping in Phase 1B using session IDs
_last_user_context: Optional[dict] = None


class MCPContextInjectingASGIApp:
    """Custom ASGI wrapper that injects user context into MCP server request context.

    This is the bridge between Starlette authentication and MCP Server's request_context.
    It extracts user info from the ASGI scope and injects it into the MCP server's
    request context where handlers can access it via server.request_context.
    """

    def __init__(self, app: ASGIApp, mcp_server: Server):
        self.app = app
        self.mcp_server = mcp_server

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        logger.info(
            f"MCPContextInjector: Processing HTTP request to {scope.get('path')}"
        )

        # Extract authenticated user from scope
        auth_user = scope.get("user")

        if isinstance(auth_user, AuthenticatedUser):
            account = getattr(auth_user.access_token, "account", None)

            if account:
                # Get database session to check tracker status
                db = next(get_db())
                try:
                    user_has_tracker = has_tracker(account, db)

                    # Build user context dict
                    user_context = {
                        "user_id": str(account.id),
                        "account_id": str(account.id),
                        "username": account.username,
                        "has_tracker": user_has_tracker,
                        "enabled_default_tools": [],  # Empty = all tools
                        "enabled_proxied_tools": [],
                    }

                    logger.info(
                        f"Injecting user context into MCP server for {account.username}: "
                        f"has_tracker={user_has_tracker}"
                    )

                    # Store in scope for downstream access
                    scope["mcp_user_context"] = user_context

                    # CRITICAL: Inject into MCP server's request context
                    # This makes it accessible via server.request_context in handlers
                    # Use the server's run_sync to set request context

                    # Try to set metadata that will be accessible in request_context
                    # This is the key to making user context available to handlers
                    if hasattr(self.mcp_server, "_request_context"):
                        self.mcp_server._request_context.meta = user_context
                        logger.info(
                            "Injected user context into server._request_context.meta"
                        )

                    # Also store in scope for any other middleware
                    scope["_mcp_meta"] = user_context

                finally:
                    db.close()

        # Call the wrapped app
        logger.info("Calling wrapped ASGI app (StreamableHTTPASGIApp)")
        await self.app(scope, receive, send)
        logger.info("Returned from wrapped ASGI app")


class InMemoryEventStore(EventStore):
    """Simple in-memory event store for MCP sessions.

    This stores events in memory for the lifetime of the server process.
    For production use with multiple workers, consider using Redis or a database.
    """

    def __init__(self):
        self._events: dict[str, list[Any]] = defaultdict(list)

    async def store_event(self, session_id: str, event: Any) -> None:
        """Store an event for a session."""
        self._events[session_id].append(event)

    async def replay_events_after(
        self, session_id: str, after_event_id: int
    ) -> list[Any]:
        """Replay events after a given event ID."""
        events = self._events.get(session_id, [])
        # Event IDs are 0-indexed, so return events after the given index
        return events[after_event_id + 1 :] if after_event_id >= 0 else events


def create_streamable_http_app() -> StarletteWithLifespan:
    """Create a Starlette app with StreamableHTTP transport and authentication.

    This function is adapted from FastMCP's create_streamable_http_app() but works
    with our DynamicMCPServer for per-user tool filtering.

    Returns:
        Starlette application with MCP StreamableHTTP support and authentication
    """
    # Initialize the DynamicMCPServer
    mcp_server = initialize_dynamic_mcp_server()
    logger.info("DynamicMCPServer initialized for StreamableHTTP transport")

    # Create event store for session management
    event_store = InMemoryEventStore()

    # Create session manager using the underlying mcp.server.Server instance
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server.server,  # Our DynamicMCPServer.server is an mcp.server.Server
        event_store=event_store,
        json_response=True,  # Use JSON responses (not SSE text format)
        stateless=False,  # Use stateful sessions for persistent connections
    )

    # Create the ASGI app wrapper (using FastMCP's implementation)
    streamable_http_app = StreamableHTTPASGIApp(session_manager)

    # Configure routes
    server_routes = [
        Route(
            "/",  # Root path since we'll be mounted at /mcp/v1
            endpoint=streamable_http_app,
            methods=["POST", "GET"],  # StreamableHTTP uses POST
        )
    ]

    # Configure authentication middleware
    server_middleware = [
        Middleware(
            AuthenticationMiddleware,
            backend=SpaceBridgeBearerAuthBackend(),
        )
    ]

    # Create lifespan manager to start/stop the session manager
    @asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            logger.info("StreamableHTTP session manager started")
            yield
        logger.info("StreamableHTTP session manager stopped")

    # Create and return the Starlette app with lifespan
    # Using FastMCP's create_base_app helper
    app = create_base_app(
        routes=server_routes,
        middleware=server_middleware,
        debug=False,
        lifespan=lifespan,
    )

    logger.info("StreamableHTTP app created with authentication")
    return app


# Global handler instance
_streamable_http_handler = None
_session_manager = None
_session_manager_context = None


def get_streamable_http_handler():
    """Get the StreamableHTTP ASGI handler.

    Returns:
        Callable ASGI application for handling MCP StreamableHTTP requests
    """
    global _streamable_http_handler, _session_manager

    if _streamable_http_handler is None:
        # Initialize the DynamicMCPServer
        mcp_server = initialize_dynamic_mcp_server()
        logger.info("DynamicMCPServer initialized for StreamableHTTP transport")

        # Create event store for session management
        event_store = InMemoryEventStore()

        # Create session manager
        _session_manager = StreamableHTTPSessionManager(
            app=mcp_server.server,
            event_store=event_store,
            json_response=True,
            stateless=False,
        )

        # Create the ASGI app wrapper
        from fastmcp.server.http import StreamableHTTPASGIApp

        base_handler = StreamableHTTPASGIApp(_session_manager)

        # Wrap with MCP context injector (injects user context into server.request_context)
        context_injector = MCPContextInjectingASGIApp(base_handler, mcp_server.server)

        # Wrap with authentication middleware (outermost - validates token first)
        from starlette.middleware.authentication import AuthenticationMiddleware

        auth_middleware = AuthenticationMiddleware(
            context_injector,
            backend=SpaceBridgeBearerAuthBackend(),
        )

        _streamable_http_handler = auth_middleware

        logger.info(
            "StreamableHTTP handler created with authentication and MCP context injection"
        )

    return _streamable_http_handler


async def start_session_manager():
    """Start the StreamableHTTP session manager.

    This should be called during application startup.
    """
    global _session_manager, _session_manager_context
    # Ensure handler is initialized
    get_streamable_http_handler()
    # Start the session manager using run() context manager
    if _session_manager:
        _session_manager_context = _session_manager.run()
        await _session_manager_context.__aenter__()
        logger.info("Session manager started")


async def stop_session_manager():
    """Stop the StreamableHTTP session manager.

    This should be called during application shutdown.
    """
    global _session_manager_context
    if _session_manager_context:
        await _session_manager_context.__aexit__(None, None, None)
        logger.info("Session manager stopped")


def get_current_user_context() -> Optional[dict]:
    """Get the current user context from the context variable.

    This is called by DynamicMCPServer to get authenticated user info.

    Tries multiple sources in order:
    1. Context variable (preferred, works in same async context)
    2. Global fallback (temporary workaround for async boundary issues)

    Returns:
        User context dict or None if no user is authenticated
    """
    # Try context variable first
    context = _user_context_var.get()
    if context:
        logger.debug("Retrieved user context from context variable")
        return context

    # Fall back to global variable (for async boundary crossing)
    global _last_user_context
    if _last_user_context:
        logger.info(
            f"Retrieved user context from global fallback: {_last_user_context['username']}"
        )
        return _last_user_context

    logger.warning("No user context available from any source")
    return None
