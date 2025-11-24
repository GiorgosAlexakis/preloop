"""Tests for account prompt resolver."""

from unittest.mock import MagicMock, patch

import pytest

from preloop_ai.services.prompt_resolvers.account import AccountResolver
from preloop_ai.services.prompt_resolvers.base import ResolverContext


class TestAccountResolver:
    """Test AccountResolver class."""

    def test_prefix_property(self):
        """Test that prefix returns 'account'."""
        resolver = AccountResolver()
        assert resolver.prefix == "account"

    @pytest.mark.asyncio
    @patch("preloop_ai.services.prompt_resolvers.account.crud_user")
    @patch("preloop_ai.services.prompt_resolvers.account.crud_account")
    async def test_resolve_email_success(self, mock_crud_account, mock_crud_user):
        """Test resolving account email successfully."""
        resolver = AccountResolver()

        # Mock context
        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"account_id": "acc-123"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        # Mock account with primary user
        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_account.primary_user_id = "user-456"
        mock_crud_account.get.return_value = mock_account

        # Mock primary user
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_crud_user.get.return_value = mock_user

        result = await resolver.resolve("email", context)

        assert result == "test@example.com"
        mock_crud_account.get.assert_called_once_with(mock_db, id="acc-123")
        mock_crud_user.get.assert_called_once_with(mock_db, id="user-456")

    @pytest.mark.asyncio
    @patch("preloop_ai.services.prompt_resolvers.account.crud_account")
    async def test_resolve_name_success(self, mock_crud_account):
        """Test resolving account name successfully."""
        resolver = AccountResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"account_id": "acc-123"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_account.organization_name = "Test Organization"
        mock_crud_account.get.return_value = mock_account

        result = await resolver.resolve("name", context)

        assert result == "Test Organization"

    @pytest.mark.asyncio
    @patch("preloop_ai.services.prompt_resolvers.account.crud_account")
    async def test_resolve_name_empty(self, mock_crud_account):
        """Test resolving account name when None."""
        resolver = AccountResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"account_id": "acc-123"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_account.organization_name = None
        mock_crud_account.get.return_value = mock_account

        result = await resolver.resolve("name", context)

        assert result == ""

    @pytest.mark.asyncio
    @patch("preloop_ai.services.prompt_resolvers.account.crud_account")
    async def test_resolve_id_success(self, mock_crud_account):
        """Test resolving account ID successfully."""
        resolver = AccountResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"account_id": "acc-123"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        mock_account = MagicMock()
        mock_account.id = "acc-456"
        mock_crud_account.get.return_value = mock_account

        result = await resolver.resolve("id", context)

        assert result == "acc-456"

    @pytest.mark.asyncio
    async def test_resolve_no_account_id(self):
        """Test resolve when no account_id in trigger data."""
        resolver = AccountResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        result = await resolver.resolve("email", context)

        assert result is None

    @pytest.mark.asyncio
    @patch("preloop_ai.services.prompt_resolvers.account.crud_account")
    async def test_resolve_account_not_found(self, mock_crud_account):
        """Test resolve when account not found in database."""
        resolver = AccountResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"account_id": "acc-999"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        mock_crud_account.get.return_value = None

        result = await resolver.resolve("email", context)

        assert result is None

    @pytest.mark.asyncio
    @patch("preloop_ai.services.prompt_resolvers.account.crud_user")
    @patch("preloop_ai.services.prompt_resolvers.account.crud_account")
    async def test_resolve_email_no_primary_user(
        self, mock_crud_account, mock_crud_user
    ):
        """Test resolving email when account has no primary user."""
        resolver = AccountResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"account_id": "acc-123"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_account.primary_user_id = None
        mock_crud_account.get.return_value = mock_account

        result = await resolver.resolve("email", context)

        assert result is None
        mock_crud_user.get.assert_not_called()

    @pytest.mark.asyncio
    @patch("preloop_ai.services.prompt_resolvers.account.crud_user")
    @patch("preloop_ai.services.prompt_resolvers.account.crud_account")
    async def test_resolve_email_primary_user_not_found(
        self, mock_crud_account, mock_crud_user
    ):
        """Test resolving email when primary user not found."""
        resolver = AccountResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"account_id": "acc-123"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_account.primary_user_id = "user-999"
        mock_crud_account.get.return_value = mock_account

        mock_crud_user.get.return_value = None

        result = await resolver.resolve("email", context)

        assert result is None

    @pytest.mark.asyncio
    @patch("preloop_ai.services.prompt_resolvers.account.crud_account")
    async def test_resolve_unknown_field(self, mock_crud_account):
        """Test resolving unknown field returns None."""
        resolver = AccountResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"account_id": "acc-123"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_crud_account.get.return_value = mock_account

        result = await resolver.resolve("unknown_field", context)

        assert result is None
