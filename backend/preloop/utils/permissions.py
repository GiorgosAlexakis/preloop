"""Permission utilities with OSS fallback.

When the proprietary RBAC plugin is not available, provides a no-op decorator
that preserves the original function signature (sync vs async) so FastAPI
continues to dispatch sync handlers through its threadpool.
"""

try:
    from preloop.plugins.proprietary.rbac.permissions import require_permission
except ModuleNotFoundError:

    def require_permission(permission_name: str):
        """No-op permission decorator for OSS builds.

        Returns the original function unchanged to preserve FastAPI's
        sync/async dispatch behavior. Sync functions will continue to
        run in the threadpool; async functions run on the event loop.
        """

        def decorator(func):
            # Return the original function unchanged - no wrapper needed
            # This preserves FastAPI's ability to detect sync vs async
            # and dispatch sync handlers to the threadpool
            return func

        return decorator
