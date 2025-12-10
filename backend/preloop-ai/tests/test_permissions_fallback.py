"""Tests for OSS permissions fallback behavior.

Ensures that the no-op require_permission decorator in OSS builds
preserves FastAPI's sync/async dispatch behavior.
"""

import asyncio
import inspect


def _create_fallback_decorator():
    """Create the fallback require_permission decorator directly.

    This avoids import issues with the proprietary module symlink.
    """

    def require_permission(permission_name: str):
        """No-op permission decorator for OSS builds."""

        def decorator(func):
            return func

        return decorator

    return require_permission


class TestRequirePermissionFallback:
    """Tests for the OSS require_permission fallback decorator."""

    def test_sync_function_stays_sync(self):
        """Test that sync functions remain sync after decoration.

        This is critical for FastAPI to dispatch them to the threadpool.
        """
        require_permission = _create_fallback_decorator()

        @require_permission("test.permission")
        def sync_handler():
            return "sync result"

        # The decorated function should NOT be a coroutine function
        assert not asyncio.iscoroutinefunction(sync_handler), (
            "Sync handler should remain sync for FastAPI threadpool dispatch"
        )

        # Should be callable and return the expected result
        result = sync_handler()
        assert result == "sync result"

    def test_async_function_stays_async(self):
        """Test that async functions remain async after decoration."""
        require_permission = _create_fallback_decorator()

        @require_permission("test.permission")
        async def async_handler():
            return "async result"

        # The decorated function should still be a coroutine function
        assert asyncio.iscoroutinefunction(async_handler), (
            "Async handler should remain async"
        )

        # Should be callable and return the expected result
        result = asyncio.run(async_handler())
        assert result == "async result"

    def test_function_signature_preserved(self):
        """Test that function signature is preserved for FastAPI dependency injection."""
        require_permission = _create_fallback_decorator()

        @require_permission("test.permission")
        def handler_with_params(db, user_id: str, limit: int = 10):
            return f"user={user_id}, limit={limit}"

        # Check signature is preserved
        sig = inspect.signature(handler_with_params)
        params = list(sig.parameters.keys())
        assert "db" in params
        assert "user_id" in params
        assert "limit" in params

    def test_decorator_is_noop(self):
        """Test that the fallback decorator returns the original function unchanged."""
        require_permission = _create_fallback_decorator()

        def original_func():
            pass

        decorated = require_permission("test.permission")(original_func)

        # Should be the exact same function object
        assert decorated is original_func, (
            "Fallback should return original function unchanged"
        )

    def test_fallback_matches_implementation(self):
        """Verify the test fallback matches the actual implementation in permissions.py."""
        # Read the actual implementation
        from pathlib import Path

        perms_file = (
            Path(__file__).parent.parent / "preloop_ai" / "utils" / "permissions.py"
        )
        content = perms_file.read_text()

        # Verify the fallback returns the function unchanged
        assert "return func" in content, "Fallback should return func unchanged"
        # Verify no async wrapper is created
        assert "async def wrapper" not in content, (
            "Fallback should not create async wrapper"
        )
