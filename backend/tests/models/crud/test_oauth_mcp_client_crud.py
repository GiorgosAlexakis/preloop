"""Tests for OAuth MCP client CRUD operations (Dynamic Client Registration)."""

import hashlib

import pytest
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from preloop.models.crud.oauth_mcp_client import (
    CRUDOAuthMCPClient,
    crud_oauth_mcp_client,
)
from preloop.models.models.oauth_mcp_client import OAuthMCPClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_client():
    return CRUDOAuthMCPClient(OAuthMCPClient)


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------


class TestGenerateClientId:
    """Tests for generate_client_id."""

    def test_prefix(self):
        cid = CRUDOAuthMCPClient.generate_client_id()
        assert cid.startswith("preloop_")

    def test_unique(self):
        ids = {CRUDOAuthMCPClient.generate_client_id() for _ in range(20)}
        assert len(ids) == 20

    def test_sufficient_length(self):
        # 24 bytes → 32 chars base64url + "preloop_" prefix
        cid = CRUDOAuthMCPClient.generate_client_id()
        assert len(cid) > 30


class TestGenerateClientSecret:
    """Tests for generate_client_secret."""

    def test_returns_string(self):
        secret = CRUDOAuthMCPClient.generate_client_secret()
        assert isinstance(secret, str)

    def test_unique(self):
        secrets = {CRUDOAuthMCPClient.generate_client_secret() for _ in range(20)}
        assert len(secrets) == 20

    def test_sufficient_length(self):
        # 48 bytes → 64 chars base64url
        secret = CRUDOAuthMCPClient.generate_client_secret()
        assert len(secret) >= 60


class TestHashSecret:
    """Tests for hash_secret."""

    def test_returns_sha256_hex(self):
        secret = "test-secret"
        expected = hashlib.sha256(secret.encode()).hexdigest()
        assert CRUDOAuthMCPClient.hash_secret(secret) == expected

    def test_deterministic(self):
        assert CRUDOAuthMCPClient.hash_secret("x") == CRUDOAuthMCPClient.hash_secret(
            "x"
        )

    def test_different_inputs(self):
        assert CRUDOAuthMCPClient.hash_secret("a") != CRUDOAuthMCPClient.hash_secret(
            "b"
        )


# ---------------------------------------------------------------------------
# CRUD methods
# ---------------------------------------------------------------------------


class TestGetByClientId:
    """Tests for get_by_client_id."""

    def test_found(self, crud_client, mock_db):
        mock_obj = MagicMock(spec=OAuthMCPClient)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_obj

        result = crud_client.get_by_client_id(mock_db, client_id="preloop_abc")
        assert result is mock_obj

    def test_not_found(self, crud_client, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = crud_client.get_by_client_id(mock_db, client_id="missing")
        assert result is None


class TestVerifyClientSecret:
    """Tests for verify_client_secret."""

    def test_correct_secret(self, crud_client):
        secret = "my-secret"
        db_client = MagicMock(spec=OAuthMCPClient)
        db_client.client_secret_hash = CRUDOAuthMCPClient.hash_secret(secret)

        assert crud_client.verify_client_secret(db_client, secret) is True

    def test_wrong_secret(self, crud_client):
        db_client = MagicMock(spec=OAuthMCPClient)
        db_client.client_secret_hash = CRUDOAuthMCPClient.hash_secret("correct")

        assert crud_client.verify_client_secret(db_client, "wrong") is False

    def test_no_secret_hash(self, crud_client):
        db_client = MagicMock(spec=OAuthMCPClient)
        db_client.client_secret_hash = None

        assert crud_client.verify_client_secret(db_client, "any") is False


class TestDeleteByClientId:
    """Tests for delete_by_client_id."""

    def test_delete_existing(self, crud_client, mock_db):
        mock_obj = MagicMock(spec=OAuthMCPClient)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_obj

        result = crud_client.delete_by_client_id(mock_db, client_id="preloop_abc")
        assert result is mock_obj
        mock_db.delete.assert_called_once_with(mock_obj)
        mock_db.commit.assert_called_once()

    def test_delete_nonexistent(self, crud_client, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = crud_client.delete_by_client_id(mock_db, client_id="missing")
        assert result is None
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()


class TestCleanupExpired:
    """Tests for cleanup_expired."""

    def test_cleanup_deletes_expired(self, crud_client, mock_db):
        expired1 = MagicMock()
        expired2 = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [expired1, expired2]

        count = crud_client.cleanup_expired(mock_db)
        assert count == 2
        assert mock_db.delete.call_count == 2
        mock_db.commit.assert_called_once()

    def test_cleanup_none_expired(self, crud_client, mock_db):
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        count = crud_client.cleanup_expired(mock_db)
        assert count == 0
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    """Test module-level singleton."""

    def test_exists(self):
        assert crud_oauth_mcp_client is not None
        assert isinstance(crud_oauth_mcp_client, CRUDOAuthMCPClient)

    def test_model(self):
        assert crud_oauth_mcp_client.model == OAuthMCPClient
