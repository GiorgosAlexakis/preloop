"""Tests for the database session module."""

import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from spacemodels.db.session import get_db_session, get_engine, get_session_factory


@pytest.fixture
def mock_create_engine():
    """Mock SQLAlchemy create_engine function."""
    with patch("spacemodels.db.session.create_engine") as mock:
        engine_mock = MagicMock()
        mock.return_value = engine_mock
        yield mock


def test_get_engine_default(mock_create_engine):
    """Test get_engine with default URL."""
    engine = get_engine()

    # Verify create_engine was called with default URL
    mock_create_engine.assert_called_once()
    assert "postgresql" in mock_create_engine.call_args[0][0]

    # Verify connection was tested
    engine.connect.return_value.__enter__.return_value.execute.assert_called_once()

    # Verify the engine was returned
    assert engine == mock_create_engine.return_value


def test_get_engine_custom_url(mock_create_engine):
    """Test get_engine with a custom URL."""
    custom_url = "postgresql://user:pass@custom-host/db"
    engine = get_engine(custom_url)

    # Verify create_engine was called with the custom URL
    mock_create_engine.assert_called_once_with(custom_url)

    # Verify connection was tested
    engine.connect.return_value.__enter__.return_value.execute.assert_called_once()


def test_get_engine_from_env(mock_create_engine):
    """Test get_engine uses DATABASE_URL environment variable."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@env-host/db"}):
        # Call get_engine but we don't need to use the result
        _ = get_engine()

        # Verify create_engine was called with the URL from environment
        mock_create_engine.assert_called_once()
        assert "env-host" in mock_create_engine.call_args[0][0]


def test_get_engine_error_fallback(mock_create_engine):
    """Test get_engine falls back to SQLite on error."""
    # Make the first engine connection raise an error
    engine_mock = mock_create_engine.return_value
    engine_mock.connect.side_effect = SQLAlchemyError("Test error")

    # Second engine (SQLite fallback) should work
    sqlite_engine_mock = MagicMock()
    mock_create_engine.side_effect = [engine_mock, sqlite_engine_mock]

    engine = get_engine()

    # Verify create_engine was called twice
    assert mock_create_engine.call_count == 2

    # First call should be to PostgreSQL
    assert "postgresql" in mock_create_engine.call_args_list[0][0][0]

    # Second call should be to SQLite
    assert "sqlite" in mock_create_engine.call_args_list[1][0][0]

    # Verify the sqlite engine was returned
    assert engine == sqlite_engine_mock


def test_get_session_factory():
    """Test get_session_factory function."""
    mock_engine = MagicMock()

    with patch(
        "spacemodels.db.session.get_engine", return_value=mock_engine
    ) as mock_get_engine:
        factory = get_session_factory()

        # Verify get_engine was called
        mock_get_engine.assert_called_once_with()

        # Verify the factory has the correct bind
        assert factory.kw["bind"] == mock_engine


def test_get_db_session():
    """Test get_db_session generator function."""
    mock_session = MagicMock(spec=Session)
    mock_factory = MagicMock(return_value=mock_session)

    with patch("spacemodels.db.session.get_session_factory", return_value=mock_factory):
        # Get the generator
        session_gen = get_db_session()

        # Get the session from the generator
        session = next(session_gen)

        # Verify the session is the one from our mock
        assert session == mock_session

        # Verify calling close on the generator causes session.close()
        try:
            next(session_gen)
        except StopIteration:
            pass

        mock_session.close.assert_called_once()
