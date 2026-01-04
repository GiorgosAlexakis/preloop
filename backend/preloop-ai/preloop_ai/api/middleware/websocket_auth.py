"""WebSocket authentication middleware.

This middleware validates Bearer tokens during the HTTP upgrade request,
before the WebSocket connection is established. This is more secure than
passing tokens as query parameters.
"""

import logging
from typing import Optional
from uuid import UUID

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# WebSocket paths that require authentication (with and without API prefix)
AUTHENTICATED_WS_PATHS = {"/ws", "/api/v1/ws"}

# WebSocket paths that allow anonymous connections (with and without API prefix)
ANONYMOUS_WS_PATHS = {
    "/ws/unified",
    "/api/v1/ws/unified",
    "/ws/execution",
    "/api/v1/ws/execution",
}


class WebSocketAuthMiddleware:
    """ASGI middleware for WebSocket authentication.

    Validates Bearer token from Authorization header during HTTP upgrade.
    For authenticated paths, rejects connection if token is invalid.
    For anonymous paths, validates token if present but allows anonymous.

    The authenticated user is stored in scope["state"]["user"] for use
    by WebSocket handlers.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "websocket":
            await self.app(scope, receive, send)
            return

        path = scope["path"]

        # Check if this is a WebSocket path we handle
        is_authenticated_path = path in AUTHENTICATED_WS_PATHS
        is_anonymous_path = path in ANONYMOUS_WS_PATHS

        if not is_authenticated_path and not is_anonymous_path:
            # Not a WebSocket path we manage, pass through
            await self.app(scope, receive, send)
            return

        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()

        # Also check query params for backwards compatibility
        query_string = scope.get("query_string", b"").decode()
        query_params = dict(
            param.split("=", 1) if "=" in param else (param, "")
            for param in query_string.split("&")
            if param
        )
        query_token = query_params.get("token", "")

        # Prefer header, fall back to query param
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        elif query_token:
            token = query_token

        # Validate token if present
        user = None
        user_id = None
        account_id = None

        if token:
            user = await self._validate_token(token)
            if user:
                user_id = user.id
                account_id = user.account_id
                logger.debug(
                    f"WebSocket auth: validated user {user.username} for {path}"
                )
            else:
                logger.warning(f"WebSocket auth: invalid token for {path}")

        # For authenticated paths, reject if no valid user
        if is_authenticated_path and not user:
            logger.warning(
                f"WebSocket auth: rejecting unauthenticated request to {path}"
            )
            await self._send_close(send, 1008, "Authentication required")
            return

        # Store auth info in scope for handlers
        if "state" not in scope:
            scope["state"] = {}

        scope["state"]["user"] = user
        scope["state"]["user_id"] = user_id
        scope["state"]["account_id"] = account_id
        scope["state"]["is_authenticated"] = user is not None

        await self.app(scope, receive, send)

    async def _validate_token(self, token: str) -> Optional["User"]:
        """Validate JWT token and return user if valid.

        Args:
            token: JWT token string

        Returns:
            User object if valid, None otherwise
        """
        try:
            from preloop_ai.api.auth.jwt import decode_token
            from preloop_models.db.session import get_db_session
            from preloop_models.models import User

            token_data = decode_token(token)
            if not token_data or not token_data.sub:
                return None

            # Get user from database
            db = next(get_db_session())
            try:
                user = db.query(User).filter(User.id == UUID(token_data.sub)).first()
                if user and user.is_active:
                    # Detach from session so it can be used in handlers
                    db.expunge(user)
                    return user
                return None
            finally:
                db.close()

        except Exception as e:
            logger.debug(f"Token validation failed: {e}")
            return None

    async def _send_close(self, send: Send, code: int, reason: str) -> None:
        """Send WebSocket close frame before connection is established.

        This sends HTTP 403 response since the upgrade hasn't happened yet.
        """
        # For WebSocket, we need to accept then close with error
        # because the ASGI spec requires accept before close
        await send(
            {
                "type": "websocket.close",
                "code": code,
                "reason": reason,
            }
        )
