# tests/api/test_app.py
"""
Tests for the SpaceBridge FastAPI application.
"""

import os

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from spacebridge.api.app import create_app


@pytest.fixture
def client():
    """Fixture to create a test client for the FastAPI app."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_pyinstrument_middleware_disabled_by_default(client):
    """
    Tests that the Pyinstrument middleware is disabled by default.
    """
    with patch("spacebridge.api.app.Profiler") as mock_profiler:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        mock_profiler.assert_not_called()


@patch.dict(os.environ, {"PROFILING_ENABLED": "true"})
def test_pyinstrument_middleware_enabled(client):
    """
    Tests that the Pyinstrument middleware is enabled when PROFILING_ENABLED is true.
    """
    with (
        patch("spacebridge.api.app.Profiler") as mock_profiler_cls,
        patch("spacebridge.api.app.SpeedscopeRenderer") as mock_renderer_cls,
    ):
        mock_profiler_instance = MagicMock()
        mock_profiler_cls.return_value = mock_profiler_instance

        mock_renderer_instance = MagicMock()
        mock_renderer_instance.render.return_value = "{}"  # valid JSON
        mock_renderer_cls.return_value = mock_renderer_instance

        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            mock_profiler_instance.start.assert_called_once()
            mock_profiler_instance.stop.assert_called_once()
            mock_profiler_instance.output_html.assert_called_once()

            mock_renderer_cls.assert_called_once()
            mock_renderer_instance.render.assert_called_once_with(
                mock_profiler_instance.last_session
            )

            assert mock_open.call_count == 2  # For HTML and speedscope files


@patch.dict(os.environ, {"PROFILING_ENABLED": "true"})
def test_pyinstrument_middleware_non_api_route(client):
    """
    Tests that the Pyinstrument middleware does not profile non-API routes.
    """
    with patch("spacebridge.api.app.Profiler") as mock_profiler:
        # Assuming there's a non-API route, e.g., a static file or a UI route
        # If not, this test needs adjustment based on the actual app structure.
        # For now, let's simulate a non-existent route that would 404
        # but the middleware should still not trigger profiling.
        response = client.get("/some/non-api/route")
        # The UIRoutingMiddleware will serve the index page, so we expect a 200
        assert response.status_code == 200
        mock_profiler.assert_not_called()


def test_api_usage_middleware_excluded_route(client):
    """
    Tests that API usage is not tracked for excluded routes.
    """
    with patch("spacebridge.api.app.get_db_session") as mock_get_db_session:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        mock_get_db_session.assert_not_called()


@patch("spacebridge.api.auth.jwt.decode_token")
def test_api_usage_middleware_tracked_route(mock_decode_token, client):
    """
    Tests that API usage is tracked for included routes.
    """
    mock_decode_token.return_value = MagicMock(sub="testuser")
    mock_session = MagicMock()
    mock_db_gen = (
        i for i in [mock_session]
    )  # Generator that yields the mock_session once
    with patch(
        "spacebridge.api.app.get_db_session", return_value=mock_db_gen
    ) as mock_get_db_session:
        headers = {"Authorization": "Bearer faketoken"}
        # Using a 404 route is fine for testing the middleware logic itself
        client.post("/api/v1/issues", headers=headers)
        mock_get_db_session.assert_called_once()
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        usage_entry = mock_session.add.call_args[0][0]
        assert usage_entry.username == "testuser"
        assert usage_entry.endpoint == "/api/v1/issues"
        assert usage_entry.method == "POST"
        assert usage_entry.action_type == "create_issue"


@patch("spacebridge.api.auth.jwt.decode_token")
def test_api_usage_middleware_db_error(mock_decode_token, client):
    """
    Tests that the middleware handles database errors gracefully.
    """
    mock_decode_token.return_value = MagicMock(sub="testuser")
    mock_session = MagicMock()
    mock_session.commit.side_effect = Exception("DB error")
    mock_db_gen = (i for i in [mock_session])
    with patch("spacebridge.api.app.get_db_session", return_value=mock_db_gen):
        headers = {"Authorization": "Bearer faketoken"}
        # The request should still complete successfully even if logging fails
        response = client.post("/api/v1/issues", headers=headers)
        # The status code might be 404/422 if the endpoint isn't fully mocked,
        # but it shouldn't be 500.
        assert response.status_code < 500


@patch("spacebridge.api.app.init_sentry")
@patch("spacebridge.api.app.setup_database")
@patch("spacebridge.api.app.connect_nats", new_callable=AsyncMock)
@patch("spacebridge.api.app.close_nats", new_callable=AsyncMock)
@patch("spacebridge.services.websocket_manager.nats_consumer", new_callable=AsyncMock)
def test_lifespan_startup_and_shutdown(
    mock_nats_consumer,
    mock_close_nats,
    mock_connect_nats,
    mock_setup_database,
    mock_init_sentry,
):
    """
    Tests the lifespan manager for correct startup and shutdown procedures.
    """
    with patch.dict(os.environ, {"INIT_DB": "true"}):
        app = create_app()
        with TestClient(app) as client:
            # Startup assertions
            mock_init_sentry.assert_called_once()
            mock_setup_database.assert_called_once()
            mock_connect_nats.assert_called_once()
            mock_nats_consumer.assert_called_once()

        # Shutdown assertions
        mock_close_nats.assert_called_once()


@patch("spacebridge.api.app.setup_database", side_effect=Exception("DB setup failed"))
def test_lifespan_startup_db_error(mock_setup_database):
    """
    Tests that a database setup failure during startup raises a RuntimeError.
    """
    with patch.dict(os.environ, {"INIT_DB": "true"}):
        app = create_app()
        with pytest.raises(RuntimeError, match="Database setup failed"):
            with TestClient(app):
                pass  # The error should be raised on context entry


@patch(
    "spacebridge.api.app.connect_nats",
    new_callable=AsyncMock,
    side_effect=Exception("NATS connection failed"),
)
def test_lifespan_startup_nats_error(mock_connect_nats):
    """
    Tests that a NATS connection failure during startup raises a RuntimeError.
    """
    app = create_app()
    with pytest.raises(RuntimeError, match="NATS connection failed"):
        with TestClient(app):
            pass  # The error should be raised on context entry


def test_create_app_configuration():
    """
    Tests that the create_app function configures the FastAPI app correctly.
    """
    app = create_app()
    assert app.title == "SpaceBridge API"
    assert app.openapi_url == "/api/v1/openapi.json"
    assert len(app.user_middleware) > 0  # Check that middleware is configured

    # Check for CORS middleware
    cors_middleware = [
        m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    ]
    assert len(cors_middleware) == 1
    assert "http://localhost:5173" in cors_middleware[0].kwargs["allow_origins"]


def test_custom_openapi_schema(client):
    """
    Tests that the custom OpenAPI schema is generated correctly.
    """
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "bearerAuth" in schema["components"]["securitySchemes"]
    # Check that a protected route has the security requirement
    assert "security" in schema["paths"]["/api/v1/trackers"]["get"]
