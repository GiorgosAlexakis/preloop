"""Tests for OAuth MCP token CRUD operations (auth codes, access tokens, refresh tokens)."""

import hashlib
import time

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from preloop.models.crud.oauth_mcp_token import (
    CRUDOAuthMCPAuthorizationCode,
    CRUDOAuthMCPAccessToken,
    CRUDOAuthMCPRefreshToken,
    _hash_token,
    generate_token,
    generate_authorization_code,
    crud_oauth_mcp_auth_code,
    crud_oauth_mcp_access_token,
    crud_oauth_mcp_refresh_token,
)
from preloop.models.models.oauth_mcp_token import (
    OAuthMCPAuthorizationCode,
    OAuthMCPAccessToken,
    OAuthMCPRefreshToken,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_auth_code():
    return CRUDOAuthMCPAuthorizationCode()


@pytest.fixture
def crud_access():
    return CRUDOAuthMCPAccessToken()


@pytest.fixture
def crud_refresh():
    return CRUDOAuthMCPRefreshToken()


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHashToken:
    """Tests for the _hash_token helper."""

    def test_returns_sha256_hex(self):
        token = "test-token-abc"
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert _hash_token(token) == expected

    def test_deterministic(self):
        assert _hash_token("same") == _hash_token("same")

    def test_different_tokens_different_hashes(self):
        assert _hash_token("token-a") != _hash_token("token-b")


class TestGenerateToken:
    """Tests for the generate_token helper."""

    def test_returns_string(self):
        assert isinstance(generate_token(), str)

    def test_unique(self):
        tokens = {generate_token() for _ in range(20)}
        assert len(tokens) == 20

    def test_custom_length(self):
        short = generate_token(8)
        long = generate_token(64)
        assert len(short) < len(long)


class TestGenerateAuthorizationCode:
    """Tests for the generate_authorization_code helper."""

    def test_returns_string(self):
        assert isinstance(generate_authorization_code(), str)

    def test_sufficient_entropy(self):
        # 24 bytes → 192 bits, base64url ≈ 32 chars
        code = generate_authorization_code()
        assert len(code) >= 30

    def test_unique(self):
        codes = {generate_authorization_code() for _ in range(20)}
        assert len(codes) == 20


# ---------------------------------------------------------------------------
# Authorization Code CRUD
# ---------------------------------------------------------------------------


class TestCRUDAuthorizationCode:
    """Tests for CRUDOAuthMCPAuthorizationCode."""

    def test_create_stores_hashed_code(self, crud_auth_code, mock_db):
        user_id = uuid4()
        account_id = uuid4()
        code = "raw-code-abc"

        crud_auth_code.create(
            mock_db,
            code=code,
            client_id="client_1",
            user_id=user_id,
            account_id=account_id,
            redirect_uri="http://localhost/callback",
            redirect_uri_provided_explicitly=True,
            code_challenge="challenge123",
            scopes=["read"],
            expires_at=time.time() + 300,
        )

        mock_db.add.assert_called_once()
        obj = mock_db.add.call_args[0][0]
        assert isinstance(obj, OAuthMCPAuthorizationCode)
        assert obj.code_hash == _hash_token(code)
        assert obj.client_id == "client_1"
        assert obj.user_id == user_id
        assert obj.is_used is False
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(obj)

    def test_create_with_resource(self, crud_auth_code, mock_db):
        crud_auth_code.create(
            mock_db,
            code="code",
            client_id="c",
            user_id=uuid4(),
            account_id=uuid4(),
            redirect_uri="http://x",
            redirect_uri_provided_explicitly=False,
            code_challenge="ch",
            scopes=[],
            expires_at=time.time() + 300,
            resource="urn:example:resource",
        )
        obj = mock_db.add.call_args[0][0]
        assert obj.resource == "urn:example:resource"
        assert obj.redirect_uri_provided_explicitly is False

    def test_get_by_code_found(self, crud_auth_code, mock_db):
        mock_obj = MagicMock(spec=OAuthMCPAuthorizationCode)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_obj

        result = crud_auth_code.get_by_code(mock_db, code="abc", client_id="c1")
        assert result is mock_obj

    def test_get_by_code_not_found(self, crud_auth_code, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = crud_auth_code.get_by_code(mock_db, code="missing", client_id="c1")
        assert result is None

    def test_mark_used(self, crud_auth_code, mock_db):
        obj = MagicMock(spec=OAuthMCPAuthorizationCode)
        obj.is_used = False
        crud_auth_code.mark_used(mock_db, obj=obj)
        assert obj.is_used is True
        mock_db.add.assert_called_once_with(obj)
        mock_db.commit.assert_called_once()

    def test_delete_expired(self, crud_auth_code, mock_db):
        expired1 = MagicMock()
        expired2 = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [expired1, expired2]

        count = crud_auth_code.delete_expired(mock_db)
        assert count == 2
        assert mock_db.delete.call_count == 2
        mock_db.commit.assert_called_once()

    def test_delete_expired_none(self, crud_auth_code, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        count = crud_auth_code.delete_expired(mock_db)
        assert count == 0
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Access Token CRUD
# ---------------------------------------------------------------------------


class TestCRUDAccessToken:
    """Tests for CRUDOAuthMCPAccessToken."""

    def test_create_stores_hashed_token(self, crud_access, mock_db):
        user_id = uuid4()
        account_id = uuid4()
        token = "raw-access-token"

        crud_access.create(
            mock_db,
            token=token,
            client_id="client_1",
            user_id=user_id,
            account_id=account_id,
            scopes=["read", "write"],
            expires_at=int(time.time()) + 3600,
        )

        obj = mock_db.add.call_args[0][0]
        assert isinstance(obj, OAuthMCPAccessToken)
        assert obj.token_hash == _hash_token(token)
        assert obj.scopes == ["read", "write"]
        assert obj.is_revoked is False
        mock_db.commit.assert_called_once()

    def test_create_with_resource(self, crud_access, mock_db):
        crud_access.create(
            mock_db,
            token="t",
            client_id="c",
            user_id=uuid4(),
            account_id=uuid4(),
            scopes=[],
            resource="urn:example",
        )
        obj = mock_db.add.call_args[0][0]
        assert obj.resource == "urn:example"

    def test_get_by_token_found(self, crud_access, mock_db):
        mock_obj = MagicMock(spec=OAuthMCPAccessToken)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_obj

        result = crud_access.get_by_token(mock_db, token="abc")
        assert result is mock_obj

    def test_get_by_token_not_found(self, crud_access, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = crud_access.get_by_token(mock_db, token="missing")
        assert result is None

    def test_revoke(self, crud_access, mock_db):
        obj = MagicMock(spec=OAuthMCPAccessToken)
        obj.is_revoked = False
        crud_access.revoke(mock_db, obj=obj)
        assert obj.is_revoked is True
        mock_db.add.assert_called_once_with(obj)
        mock_db.commit.assert_called_once()

    def test_revoke_by_user_and_client(self, crud_access, mock_db):
        user_id = uuid4()
        t1 = MagicMock(is_revoked=False)
        t2 = MagicMock(is_revoked=False)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [t1, t2]

        count = crud_access.revoke_by_user_and_client(
            mock_db, user_id=user_id, client_id="c1"
        )
        assert count == 2
        assert t1.is_revoked is True
        assert t2.is_revoked is True
        mock_db.commit.assert_called_once()

    def test_revoke_by_user_and_client_no_tokens(self, crud_access, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        count = crud_access.revoke_by_user_and_client(
            mock_db, user_id=uuid4(), client_id="c1"
        )
        assert count == 0
        mock_db.commit.assert_not_called()

    def test_delete_expired_and_revoked(self, crud_access, mock_db):
        stale1 = MagicMock()
        stale2 = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [stale1, stale2]

        count = crud_access.delete_expired_and_revoked(mock_db)
        assert count == 2
        assert mock_db.delete.call_count == 2
        mock_db.commit.assert_called_once()

    def test_delete_expired_and_revoked_none(self, crud_access, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        count = crud_access.delete_expired_and_revoked(mock_db)
        assert count == 0
        mock_db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Refresh Token CRUD
# ---------------------------------------------------------------------------


class TestCRUDRefreshToken:
    """Tests for CRUDOAuthMCPRefreshToken."""

    def test_create_stores_hashed_token(self, crud_refresh, mock_db):
        user_id = uuid4()
        account_id = uuid4()
        token = "raw-refresh-token"

        crud_refresh.create(
            mock_db,
            token=token,
            client_id="client_1",
            user_id=user_id,
            account_id=account_id,
            scopes=["read"],
            expires_at=int(time.time()) + 2592000,
        )

        obj = mock_db.add.call_args[0][0]
        assert isinstance(obj, OAuthMCPRefreshToken)
        assert obj.token_hash == _hash_token(token)
        assert obj.is_revoked is False
        mock_db.commit.assert_called_once()

    def test_get_by_token_found(self, crud_refresh, mock_db):
        mock_obj = MagicMock(spec=OAuthMCPRefreshToken)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_obj

        result = crud_refresh.get_by_token(mock_db, token="abc")
        assert result is mock_obj

    def test_get_by_token_not_found(self, crud_refresh, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = crud_refresh.get_by_token(mock_db, token="missing")
        assert result is None

    def test_revoke(self, crud_refresh, mock_db):
        obj = MagicMock(spec=OAuthMCPRefreshToken)
        obj.is_revoked = False
        crud_refresh.revoke(mock_db, obj=obj)
        assert obj.is_revoked is True
        mock_db.add.assert_called_once_with(obj)
        mock_db.commit.assert_called_once()

    def test_revoke_by_user_and_client(self, crud_refresh, mock_db):
        user_id = uuid4()
        t1 = MagicMock(is_revoked=False)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [t1]

        count = crud_refresh.revoke_by_user_and_client(
            mock_db, user_id=user_id, client_id="c1"
        )
        assert count == 1
        assert t1.is_revoked is True
        mock_db.commit.assert_called_once()

    def test_revoke_by_user_and_client_no_tokens(self, crud_refresh, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        count = crud_refresh.revoke_by_user_and_client(
            mock_db, user_id=uuid4(), client_id="c1"
        )
        assert count == 0
        mock_db.commit.assert_not_called()

    def test_delete_expired_and_revoked(self, crud_refresh, mock_db):
        stale1 = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [stale1]

        count = crud_refresh.delete_expired_and_revoked(mock_db)
        assert count == 1
        mock_db.delete.assert_called_once_with(stale1)
        mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------


class TestSingletons:
    """Test module-level singleton CRUD instances."""

    def test_auth_code_singleton(self):
        assert crud_oauth_mcp_auth_code is not None
        assert isinstance(crud_oauth_mcp_auth_code, CRUDOAuthMCPAuthorizationCode)

    def test_access_token_singleton(self):
        assert crud_oauth_mcp_access_token is not None
        assert isinstance(crud_oauth_mcp_access_token, CRUDOAuthMCPAccessToken)

    def test_refresh_token_singleton(self):
        assert crud_oauth_mcp_refresh_token is not None
        assert isinstance(crud_oauth_mcp_refresh_token, CRUDOAuthMCPRefreshToken)
