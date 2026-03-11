"""Permission utilities with OSS fallback.

When the proprietary RBAC plugin is unavailable, this module exposes a no-op
decorator. When it is available, the exported decorator preserves the wrapped
function's sync/async nature so FastAPI can keep dispatching sync handlers via
its threadpool.
"""

from __future__ import annotations

import asyncio
import functools

try:
    from preloop.plugins.proprietary.rbac.permissions import (
        require_permission as _plugin_require_permission,
    )
except ModuleNotFoundError:
    _plugin_require_permission = None


def require_permission(permission_name: str):
    """Return a decorator that preserves sync/async behavior."""

    def decorator(func):
        if _plugin_require_permission is None:
            return func

        plugin_wrapped = _plugin_require_permission(permission_name)(func)

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if "current_user" not in kwargs or "db" not in kwargs:
                    return await func(*args, **kwargs)
                return await plugin_wrapped(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if "current_user" not in kwargs or "db" not in kwargs:
                return func(*args, **kwargs)
            return asyncio.run(plugin_wrapped(*args, **kwargs))

        return sync_wrapper

    return decorator
