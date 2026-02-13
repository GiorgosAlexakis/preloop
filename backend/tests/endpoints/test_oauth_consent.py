"""Tests for OAuth consent page endpoints (GET + POST /mcp/authorize/consent)."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from preloop.api.endpoints.oauth_consent import router, _render_template


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_provider_singleton():
    """Reset the module-level singleton before each test."""
    import preloop.api.endpoints.oauth_consent as mod

    mod._oauth_provider_instance = None
    yield
    mod._oauth_provider_instance = None


@pytest.fixture
def app():
    """Create a test FastAPI app with the consent router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# _render_template
# ---------------------------------------------------------------------------


class TestRenderTemplate:
    """Tests for the simple template renderer."""

    def test_replaces_variables(self, tmp_path):
        template = tmp_path / "test.html"
        template.write_text("<p>{{ name }} - {{ value }}</p>")

        with patch("preloop.api.endpoints.oauth_consent._TEMPLATE_DIR", tmp_path):
            result = _render_template("test.html", {"name": "hello", "value": "world"})

        assert result == "<p>hello - world</p>"

    def test_handles_none_values(self, tmp_path):
        template = tmp_path / "test.html"
        template.write_text("<p>{{ maybe }}</p>")

        with patch("preloop.api.endpoints.oauth_consent._TEMPLATE_DIR", tmp_path):
            result = _render_template("test.html", {"maybe": None})

        assert result == "<p></p>"


# ---------------------------------------------------------------------------
# GET /mcp/authorize/consent
# ---------------------------------------------------------------------------


class TestConsentPageGet:
    """Tests for the GET consent page endpoint."""

    def test_renders_html(self, client):
        with (
            patch("preloop.api.endpoints.oauth_consent.get_db_session") as mock_gen,
            patch(
                "preloop.api.endpoints.oauth_consent._render_template",
                return_value="<html>OK</html>",
            ),
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])

            # Patch the inner crud import
            with patch(
                "preloop.api.endpoints.oauth_consent.crud_oauth_mcp_client",
                create=True,
            ) as mock_crud:
                mock_crud.get_by_client_id.return_value = None

                response = client.get(
                    "/mcp/authorize/consent",
                    params={
                        "client_id": "c1",
                        "redirect_uri": "http://localhost/cb",
                        "code_challenge": "ch123",
                    },
                )

        assert response.status_code == 200
        assert "OK" in response.text

    def test_passes_params_to_template(self, client):
        rendered_contexts = []

        def capture_render(template_name, context):
            rendered_contexts.append(context)
            return "<html>test</html>"

        with (
            patch(
                "preloop.api.endpoints.oauth_consent._render_template",
                side_effect=capture_render,
            ),
            patch("preloop.api.endpoints.oauth_consent.get_db_session") as mock_gen,
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])

            with patch(
                "preloop.api.endpoints.oauth_consent.crud_oauth_mcp_client",
                create=True,
            ) as mock_crud:
                mock_crud.get_by_client_id.return_value = None

                client.get(
                    "/mcp/authorize/consent",
                    params={
                        "client_id": "test_client",
                        "redirect_uri": "http://example.com/cb",
                        "code_challenge": "ch",
                        "state": "state_abc",
                        "scopes": "read write",
                    },
                )

        assert len(rendered_contexts) == 1
        ctx = rendered_contexts[0]
        assert ctx["client_id"] == "test_client"
        assert ctx["redirect_uri"] == "http://example.com/cb"
        assert ctx["state"] == "state_abc"
        assert ctx["scopes"] == "read write"
        assert ctx["error"] == ""

    def test_missing_required_params(self, client):
        response = client.get("/mcp/authorize/consent")
        assert response.status_code == 422  # Validation error


# ---------------------------------------------------------------------------
# POST /mcp/authorize/consent
# ---------------------------------------------------------------------------


class TestConsentPagePost:
    """Tests for the POST consent submission endpoint."""

    def test_successful_login_redirects(self, client):
        user = MagicMock()
        user.id = uuid4()
        user.account_id = uuid4()
        user.username = "testuser"
        user.hashed_password = "hashed"
        user.is_active = True

        mock_provider = MagicMock()
        mock_provider.create_authorization_code_for_user.return_value = "auth_code_xyz"

        with (
            patch("preloop.api.endpoints.oauth_consent.get_db_session") as mock_gen,
            patch("preloop.models.crud.crud_user") as mock_crud_user,
            patch("preloop.api.auth.jwt.verify_password", return_value=True),
            patch(
                "preloop.api.endpoints.oauth_consent._get_oauth_provider",
                return_value=mock_provider,
            ),
            patch(
                "preloop.api.endpoints.oauth_consent.construct_redirect_uri",
                return_value="http://localhost/cb?code=auth_code_xyz",
            ),
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])
            mock_crud_user.get_by_username.return_value = user

            response = client.post(
                "/mcp/authorize/consent",
                data={
                    "client_id": "c1",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": "ch",
                    "username": "testuser",
                    "password": "pass123",
                },
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "code=auth_code_xyz" in response.headers["location"]

    def test_invalid_credentials_renders_error(self, client):
        with (
            patch("preloop.api.endpoints.oauth_consent.get_db_session") as mock_gen,
            patch("preloop.models.crud.crud_user") as mock_crud_user,
            patch(
                "preloop.api.endpoints.oauth_consent._render_template",
                return_value="<html>error</html>",
            ),
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])
            mock_crud_user.get_by_username.return_value = None
            mock_crud_user.get_by_email.return_value = None

            response = client.post(
                "/mcp/authorize/consent",
                data={
                    "client_id": "c1",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": "ch",
                    "username": "nobody",
                    "password": "wrong",
                },
            )

        assert response.status_code == 200
        assert "error" in response.text

    def test_wrong_password_renders_error(self, client):
        user = MagicMock()
        user.hashed_password = "hashed"

        with (
            patch("preloop.api.endpoints.oauth_consent.get_db_session") as mock_gen,
            patch("preloop.models.crud.crud_user") as mock_crud_user,
            patch("preloop.api.auth.jwt.verify_password", return_value=False),
            patch(
                "preloop.api.endpoints.oauth_consent._render_template",
                return_value="<html>bad pass</html>",
            ),
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])
            mock_crud_user.get_by_username.return_value = user

            response = client.post(
                "/mcp/authorize/consent",
                data={
                    "client_id": "c1",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": "ch",
                    "username": "user",
                    "password": "wrong",
                },
            )

        assert response.status_code == 200

    def test_inactive_user_renders_error(self, client):
        user = MagicMock()
        user.hashed_password = "hashed"
        user.is_active = False

        with (
            patch("preloop.api.endpoints.oauth_consent.get_db_session") as mock_gen,
            patch("preloop.models.crud.crud_user") as mock_crud_user,
            patch("preloop.api.auth.jwt.verify_password", return_value=True),
            patch(
                "preloop.api.endpoints.oauth_consent._render_template",
                return_value="<html>deactivated</html>",
            ),
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])
            mock_crud_user.get_by_username.return_value = user

            response = client.post(
                "/mcp/authorize/consent",
                data={
                    "client_id": "c1",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": "ch",
                    "username": "user",
                    "password": "pass",
                },
            )

        assert response.status_code == 200

    def test_oauth_not_configured_renders_error(self, client):
        user = MagicMock()
        user.hashed_password = "hashed"
        user.is_active = True

        with (
            patch("preloop.api.endpoints.oauth_consent.get_db_session") as mock_gen,
            patch("preloop.models.crud.crud_user") as mock_crud_user,
            patch("preloop.api.auth.jwt.verify_password", return_value=True),
            patch(
                "preloop.api.endpoints.oauth_consent._get_oauth_provider",
                return_value=None,
            ),
            patch(
                "preloop.api.endpoints.oauth_consent._render_template",
                return_value="<html>not configured</html>",
            ),
        ):
            mock_db = MagicMock()
            mock_gen.return_value = iter([mock_db])
            mock_crud_user.get_by_username.return_value = user

            response = client.post(
                "/mcp/authorize/consent",
                data={
                    "client_id": "c1",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": "ch",
                    "username": "user",
                    "password": "pass",
                },
            )

        assert response.status_code == 200
