from functools import wraps
import asyncio

try:
    from preloop_ai.plugins.proprietary.rbac.permissions import require_permission
except ModuleNotFoundError:

    def require_permission(permission_name: str):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            return wrapper

        return decorator
