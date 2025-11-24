from functools import wraps

try:
    from preloop_ai.plugins.proprietary.rbac.permissions import require_permission
except ModuleNotFoundError:

    def require_permission(x):
        @wraps(x)
        def wrapper(f):
            return f

        return wrapper
