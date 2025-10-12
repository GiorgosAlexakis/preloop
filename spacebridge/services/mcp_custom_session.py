"""Custom StreamableHTTP session manager with user context injection.

This module creates a custom session manager that properly injects user context
into the MCP server's request context so handlers can access it.
"""

import logging
from typing import Optional

from mcp.server import Server
from mcp.server.streamable_http import EventStore
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.types import Receive, Scope, Send

logger = logging.getLogger(__name__)


class ContextAwareSessionManager(StreamableHTTPSessionManager):
    """Custom session manager that injects user context from ASGI scope.

    This subclass overrides the ASGI __call__ to extract user context from
    the scope and make it available to MCP handlers via a custom mechanism.
    """

    def __init__(
        self,
        app: Server,
        event_store: EventStore,
        json_response: bool = True,
        stateless: bool = False,
    ):
        super().__init__(app, event_store, json_response, stateless)
        self._user_context_store = {}  # session_id -> user_context

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle ASGI request with user context injection."""
        if scope["type"] != "http":
            await super().__call__(scope, receive, send)
            return

        # Extract user context from scope (set by our auth middleware)
        user_context = scope.get("mcp_user_context")

        if user_context:
            logger.info(
                f"SessionManager: Extracted user context for {user_context.get('username')}"
            )

            # Store it for later retrieval
            # We'll use this in the server's context
            scope["_mcp_injected_context"] = user_context

        # Call the parent implementation
        await super().__call__(scope, receive, send)


class ContextAwareServer:
    """Wrapper around MCP Server that provides user context access.

    This wrapper intercepts access to the MCP server and injects user context
    into handlers by providing a custom context access mechanism.
    """

    def __init__(self, server: Server):
        self.server = server
        self._injected_context: Optional[dict] = None

    def set_user_context(self, context: dict):
        """Set the user context for the current request."""
        self._injected_context = context
        logger.info(f"Set injected context: {context}")

    def get_user_context(self) -> Optional[dict]:
        """Get the user context for the current request."""
        return self._injected_context

    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped server."""
        return getattr(self.server, name)
