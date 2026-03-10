"""Tests for utils.permissions OSS fallback."""

import asyncio

from preloop.utils import permissions


class TestRequirePermissionOSSFallback:
    """Test require_permission decorator (OSS build uses no-op fallback)."""

    def test_require_permission_preserves_sync_function(self):
        """require_permission decorator preserves sync function behavior."""

        @permissions.require_permission("admin:read")
        def my_sync_func(x: int) -> int:
            return x + 1

        assert my_sync_func(41) == 42

    def test_require_permission_preserves_async_function(self):
        """require_permission decorator preserves async function for FastAPI."""

        @permissions.require_permission("admin:write")
        async def my_async_func(x: int) -> int:
            return x * 2

        result = asyncio.run(my_async_func(21))
        assert result == 42

    def test_require_permission_with_different_permission_names(self):
        """Decorator accepts various permission names."""

        @permissions.require_permission("flows:create")
        def create_flow():
            return "created"

        assert create_flow() == "created"
