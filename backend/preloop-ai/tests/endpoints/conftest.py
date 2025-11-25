"""Shared test fixtures for endpoint tests."""

import pytest
from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def mock_has_permission(mocker: MockerFixture):
    """
    Mock has_permission to always return True for unit tests.

    This allows unit tests to call endpoint functions directly without
    needing to set up proper user roles and permissions.
    """
    try:
        import preloop_ai.plugins.proprietary.rbac.permissions

        mocker.patch(
            "preloop_ai.plugins.proprietary.rbac.permissions.has_permission",
            return_value=True,
        )
    except ImportError:
        pass
