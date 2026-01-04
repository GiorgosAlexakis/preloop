"""Tests for the database session module."""

import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from preloop.models.db.session import get_db_session, get_engine, get_session_factory
import preloop.models.db.session as session_module


@pytest.fixture(autouse=True)  # Apply mock engine automatically to relevant tests
def mock_engine_dependencies(monkeypatch):
    """Mock dependencies used by get_engine."""
    # Reset global engine cache before each test
    session_module._engine = None
    session_module._session_factory = None

    mock_create = MagicMock()
    mock_engine_instance = MagicMock()
    mock_conn = MagicMock()
    # Simulate the context manager for connect()
    mock_engine_instance.connect.return_value.__enter__.return_value = mock_conn
    mock_create.return_value = mock_engine_instance

    mock_check_pgvector = MagicMock(return_value=True)

    monkeypatch.setattr("preloop.models.db.session.create_engine", mock_create)
    monkeypatch.setattr(
        "preloop.models.db.session.check_pgvector_extension", mock_check_pgvector
    )
    # Prevent actual installation attempt if check returns False
    monkeypatch.setattr(
        "preloop.models.db.session.install_pgvector_extension", MagicMock()
    )

    # Return the mocks for potential use in tests
    return {
        "create_engine": mock_create,
        "engine_instance": mock_engine_instance,
        "connection": mock_conn,
        "check_pgvector": mock_check_pgvector,
    }


# Test cases now implicitly use the mocked dependencies via autouse fixture
def test_get_engine_custom_url(mock_engine_dependencies):
    """Test get_engine with a custom URL."""
    custom_url = "postgresql://user:pass@custom-host/db"
    engine = get_engine(custom_url)

    # Verify create_engine was called with the custom URL and connection pool parameters
    mock_engine_dependencies["create_engine"].assert_called_once_with(
        custom_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )

    # Verify connection test happened (execute called on connection mock)
    mock_conn = mock_engine_dependencies["connection"]
    assert mock_conn.execute.call_count >= 1  # Ensure execute was called
    # Check the arguments of the first call specifically
    first_call_args = mock_conn.execute.call_args_list[0].args
    assert "SELECT 1" in str(first_call_args[0])

    # Verify check_pgvector_extension was called (implies a second execute call)
    mock_engine_dependencies["check_pgvector"].assert_called_once_with(
        mock_engine_dependencies["engine_instance"]
    )

    # Verify the engine instance was returned
    assert engine == mock_engine_dependencies["engine_instance"]


def test_get_engine_from_env(mock_engine_dependencies):
    """Test get_engine uses DATABASE_URL environment variable."""
    env_url = "postgresql://user:pass@env-host/db"

    with patch.dict(os.environ, {"DATABASE_URL": env_url}):
        engine = get_engine()

        # Verify create_engine was called with the URL from environment and pool parameters
        mock_engine_dependencies["create_engine"].assert_called_once_with(
            env_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )

        # Verify connection test happened
        mock_conn = mock_engine_dependencies["connection"]
        assert mock_conn.execute.call_count >= 1  # Ensure execute was called
        first_call_args = mock_conn.execute.call_args_list[0].args
        assert "SELECT 1" in str(first_call_args[0])

        # Verify check_pgvector_extension was called (implies a second execute call)
        mock_engine_dependencies["check_pgvector"].assert_called_once_with(
            mock_engine_dependencies["engine_instance"]
        )

        # Verify the engine instance was returned
        assert engine == mock_engine_dependencies["engine_instance"]


# Add test for default URL case (was missing)
def test_get_engine_default(mock_engine_dependencies):
    """Test get_engine with default URL from env."""
    # Assume DATABASE_URL is set in the environment for default case
    default_url = "postgresql://default:pass@default-host/db"
    with patch.dict(os.environ, {"DATABASE_URL": default_url}):
        engine = get_engine()  # Call without args

        # Verify create_engine was called with the default URL and pool parameters
        mock_engine_dependencies["create_engine"].assert_called_once_with(
            default_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )

        # Verify connection test happened
        mock_conn = mock_engine_dependencies["connection"]
        assert mock_conn.execute.call_count >= 1  # Ensure execute was called
        first_call_args = mock_conn.execute.call_args_list[0].args
        assert "SELECT 1" in str(first_call_args[0])

        # Verify check_pgvector_extension was called (implies a second execute call)
        mock_engine_dependencies["check_pgvector"].assert_called_once_with(
            mock_engine_dependencies["engine_instance"]
        )
        assert engine == mock_engine_dependencies["engine_instance"]


# Add test for error case (missing URL)
def test_get_engine_error_fallback():
    """Test get_engine raises exception if DATABASE_URL is not set."""
    # Reset global engine cache to ensure test starts fresh
    session_module._engine = None
    session_module._session_factory = None

    # Ensure DATABASE_URL is not set
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(Exception, match="DATABASE_URL not in env"):
            get_engine()


def test_get_session_factory(mock_engine_dependencies):
    """Test get_session_factory function."""
    # get_engine is mocked by mock_engine_dependencies fixture via autouse
    factory = get_session_factory()

    # Verify the factory has the correct bind (the mocked engine instance)
    assert factory.kw["bind"] == mock_engine_dependencies["engine_instance"]


def test_get_db_session():
    """Test get_db_session generator function."""
    mock_session = MagicMock(spec=Session)
    mock_factory = MagicMock(return_value=mock_session)

    with patch(
        "preloop.models.db.session.get_session_factory", return_value=mock_factory
    ):
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
