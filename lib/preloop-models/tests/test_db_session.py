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
    # Also mock the connection and execute methods for detailed checks
    with patch("spacemodels.db.session.create_engine") as mock_create_engine:
        engine_mock = MagicMock()
        conn_mock = MagicMock()
        engine_mock.connect.return_value.__enter__.return_value = conn_mock
        mock_create_engine.return_value = engine_mock
        yield mock_create_engine, engine_mock, conn_mock  # Yield all mocks


# Mock check_pgvector_extension as well
@patch("spacemodels.db.session.check_pgvector_extension", return_value=True)
def test_get_engine_default(
    mock_check_pgvector, mock_create_engine
):  # Add mock_check_pgvector
    """Test get_engine with default URL."""
    mock_creator, mock_engine_instance, mock_conn = mock_create_engine  # Unpack mocks

    engine = get_engine()

    # Verify create_engine was called with default URL (or None, letting get_engine use env/default)
    # Check create_engine call with the resolved default URL
    mock_creator.assert_called_once_with(
        "postgresql+psycopg://postgres:postgres@localhost/spacemodels"
    )

    # Verify connection was tested via execute on the mocked connection
    mock_conn.execute.assert_called_once()
    assert "SELECT 1" in str(mock_conn.execute.call_args[0][0])  # Check the query

    # Verify check_pgvector_extension was called
    mock_check_pgvector.assert_called_once_with(mock_engine_instance)

    # Verify the engine was returned
    assert engine == mock_engine_instance


# Mock check_pgvector_extension as well
@patch("spacemodels.db.session.check_pgvector_extension", return_value=True)
def test_get_engine_custom_url(
    mock_check_pgvector, mock_create_engine
):  # Add mock_check_pgvector
    """Test get_engine with a custom URL."""
    mock_creator, mock_engine_instance, mock_conn = mock_create_engine  # Unpack mocks
    custom_url = "postgresql://user:pass@custom-host/db"

    engine = get_engine(custom_url)

    # Verify create_engine was called with the custom URL
    mock_creator.assert_called_once_with(custom_url)  # Check create_engine call

    # Verify connection was tested via execute on the mocked connection
    mock_conn.execute.assert_called_once()
    assert "SELECT 1" in str(mock_conn.execute.call_args[0][0])  # Check the query

    # Verify check_pgvector_extension was called
    mock_check_pgvector.assert_called_once_with(mock_engine_instance)

    # Verify the engine was returned
    assert engine == mock_engine_instance


# Mock check_pgvector_extension as well
@patch("spacemodels.db.session.check_pgvector_extension", return_value=True)
def test_get_engine_from_env(
    mock_check_pgvector, mock_create_engine
):  # Add mock_check_pgvector
    """Test get_engine uses DATABASE_URL environment variable."""
    mock_creator, mock_engine_instance, mock_conn = mock_create_engine  # Unpack mocks
    env_url = "postgresql://user:pass@env-host/db"

    with patch.dict(os.environ, {"DATABASE_URL": env_url}):
        engine = get_engine()

        # Verify create_engine was called with the URL from environment
        mock_creator.assert_called_once_with(env_url)  # Check create_engine call

        # Verify connection was tested via execute
        mock_conn.execute.assert_called_once()
        assert "SELECT 1" in str(mock_conn.execute.call_args[0][0])

        # Verify check_pgvector_extension was called
        mock_check_pgvector.assert_called_once_with(mock_engine_instance)

        # Verify the engine was returned
        assert engine == mock_engine_instance


# No check_pgvector mock needed here as the first connection fails
def test_get_engine_error_fallback(mock_create_engine):
    """Test get_engine falls back to SQLite on error."""
    mock_creator, mock_engine_instance, mock_conn = mock_create_engine  # Unpack mocks
    # Make the first engine connection attempt raise an error
    mock_engine_instance.connect.side_effect = SQLAlchemyError("Test error")

    # Second engine (SQLite fallback) should work
    sqlite_engine_mock = MagicMock()
    # Set the side_effect on the creator mock
    mock_creator.side_effect = [mock_engine_instance, sqlite_engine_mock]

    engine = get_engine()

    # Verify create_engine was called twice
    assert mock_creator.call_count == 2

    # First call should be the resolved default postgresql URL
    assert (
        mock_creator.call_args_list[0][0][0]
        == "postgresql+psycopg://postgres:postgres@localhost/spacemodels"
    )

    # Second call should be to SQLite
    assert "sqlite:///" in mock_creator.call_args_list[1][0][0]

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
