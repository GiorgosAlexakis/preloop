"""Tests for OAuth server endpoints (/oauth/token, /oauth/revoke)."""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import timedelta
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from preloop.api.endpoints.oauth_server import (
    CLI_JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    _issue_jwt_tokens,
    router,
)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /oauth/token — redirect_uri enforcement
# ---------------------------------------------------------------------------


class TestTokenExchangeRedirectUri:
    """Tests for redirect_uri enforcement during authorization code exchange."""

    def _make_db_code(self, redirect_uri="http://localhost/cb", code_challenge=""):
        code = MagicMock()
        code.is_used = False
        code.expires_at = time.time() + 600
        code.redirect_uri = redirect_uri
        code.code_challenge = code_challenge
        code.client_id = "test_client"
        code.user_id = uuid4()
        code.account_id = uuid4()
        code.scopes = []
        code.resource = None
        return code

    def test_rejects_missing_redirect_uri_when_stored(self, client):
        """If auth code has a redirect_uri, token request MUST include it."""
        db_code = self._make_db_code(redirect_uri="http://localhost/cb")

        with (
            patch("preloop.models.db.session.get_db_session") as mock_gen,
            patch(
                "preloop.models.crud.oauth_mcp_token.crud_oauth_mcp_auth_code"
            ) as mock_crud,
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])
            mock_crud.get_by_code.return_value = db_code

            response = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "test_code",
                    "client_id": "test_client",
                    "redirect_uri": "",  # empty — should be rejected
                },
            )

        assert response.status_code == 400
        assert response.json()["error"] == "invalid_grant"
        assert "redirect_uri is required" in response.json()["error_description"]

    def test_rejects_mismatched_redirect_uri(self, client):
        """redirect_uri must exactly match the one stored in the auth code."""
        db_code = self._make_db_code(redirect_uri="http://localhost/cb")

        with (
            patch("preloop.models.db.session.get_db_session") as mock_gen,
            patch(
                "preloop.models.crud.oauth_mcp_token.crud_oauth_mcp_auth_code"
            ) as mock_crud,
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])
            mock_crud.get_by_code.return_value = db_code

            response = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "test_code",
                    "client_id": "test_client",
                    "redirect_uri": "http://evil.com/steal",
                },
            )

        assert response.status_code == 400
        assert response.json()["error"] == "invalid_grant"
        assert "does not match" in response.json()["error_description"]

    def test_allows_matching_redirect_uri(self, client):
        """Matching redirect_uri should pass validation and proceed to token issuance."""
        db_code = self._make_db_code(
            redirect_uri="http://localhost/cb", code_challenge=""
        )

        with (
            patch("preloop.models.db.session.get_db_session") as mock_gen,
            patch(
                "preloop.models.crud.oauth_mcp_token.crud_oauth_mcp_auth_code"
            ) as mock_crud,
            patch(
                "preloop.api.endpoints.oauth_server._issue_jwt_tokens",
                new_callable=AsyncMock,
                return_value={"access_token": "t", "token_type": "bearer"},
            ),
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])
            mock_crud.get_by_code.return_value = db_code

            response = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "test_code",
                    "client_id": "test_client",
                    "redirect_uri": "http://localhost/cb",
                },
            )

        # Should not be a 400 — it passed redirect_uri validation
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /oauth/revoke — refresh token revocation
# ---------------------------------------------------------------------------


class TestTokenRevocation:
    """Tests for token revocation endpoint."""

    def test_revokes_access_token(self, client):
        """Access tokens should be revoked via the provider."""
        mock_provider = MagicMock()
        mock_token = MagicMock()
        mock_provider.load_access_token = AsyncMock(return_value=mock_token)
        mock_provider.revoke_token = AsyncMock()

        with patch(
            "preloop.api.endpoints.oauth_consent.get_oauth_provider",
            return_value=mock_provider,
        ):
            response = client.post("/oauth/revoke", data={"token": "access_tok"})

        assert response.status_code == 200
        assert response.json()["status"] == "revoked"
        mock_provider.revoke_token.assert_called_once_with(mock_token)

    def test_revokes_refresh_token(self, client):
        """Refresh tokens should be revoked when access token lookup fails."""
        mock_provider = MagicMock()
        mock_provider.load_access_token = AsyncMock(return_value=None)

        mock_db_refresh = MagicMock()
        mock_db_refresh.is_revoked = False
        mock_crud = MagicMock()
        mock_crud.get_by_token.return_value = mock_db_refresh

        with (
            patch(
                "preloop.api.endpoints.oauth_consent.get_oauth_provider",
                return_value=mock_provider,
            ),
            patch(
                "preloop.models.crud.oauth_mcp_token.crud_oauth_mcp_refresh_token",
                mock_crud,
            ),
            patch("preloop.models.db.session.get_db_session") as mock_gen,
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])

            response = client.post("/oauth/revoke", data={"token": "refresh_tok"})

        assert response.status_code == 200
        assert response.json()["status"] == "revoked"
        mock_crud.revoke.assert_called_once_with(mock_db, obj=mock_db_refresh)

    def test_unknown_token_returns_success(self, client):
        """Per RFC 7009, revocation of an unknown token should still return success."""
        mock_provider = MagicMock()
        mock_provider.load_access_token = AsyncMock(return_value=None)

        mock_crud = MagicMock()
        mock_crud.get_by_token.return_value = None

        with (
            patch(
                "preloop.api.endpoints.oauth_consent.get_oauth_provider",
                return_value=mock_provider,
            ),
            patch(
                "preloop.models.crud.oauth_mcp_token.crud_oauth_mcp_refresh_token",
                mock_crud,
            ),
            patch("preloop.models.db.session.get_db_session") as mock_gen,
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])

            response = client.post("/oauth/revoke", data={"token": "unknown_tok"})

        assert response.status_code == 200
        assert response.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_issue_jwt_tokens_uses_long_lived_cli_refresh_tokens():
    db_code = MagicMock()
    db_code.user_id = uuid4()

    user = MagicMock()
    captured_expiries = []

    def _capture_token(*args, **kwargs):
        captured_expiries.append(kwargs.get("expires_delta"))
        return f"token-{len(captured_expiries)}"

    with (
        patch("preloop.models.crud.crud_user.get", return_value=user),
        patch("preloop.api.auth.jwt.create_access_token", side_effect=_capture_token),
        patch("preloop.api.auth.jwt.ACCESS_TOKEN_EXPIRE_MINUTES", 60),
    ):
        response = await _issue_jwt_tokens(MagicMock(), db_code)

    assert response.status_code == 200
    assert captured_expiries[0] == timedelta(minutes=60)
    assert captured_expiries[1] == timedelta(days=CLI_JWT_REFRESH_TOKEN_EXPIRE_DAYS)
