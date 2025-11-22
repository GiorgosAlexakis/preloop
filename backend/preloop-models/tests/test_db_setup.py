"""Tests for database setup utilities."""

from unittest.mock import MagicMock, patch

import pytest

from spacemodels.db.setup import reset_database, setup_database


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy engine."""
    mock = MagicMock()
    mock.connect.return_value.__enter__.return_value = MagicMock()
    return mock


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for Alembic commands."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


def test_setup_database_success(mock_engine, mock_subprocess_run):
    """Test successful database setup using Alembic."""
    with patch("spacemodels.db.setup.get_engine", return_value=mock_engine):
        setup_database()

        # Verify that Alembic upgrade was called
        assert mock_subprocess_run.called
        call_args = mock_subprocess_run.call_args
        assert call_args[0][0] == ["alembic", "upgrade", "head"]


def test_setup_database_with_pgvector(mock_engine, mock_subprocess_run):
    """Test database setup with pgvector extension."""
    with patch("spacemodels.db.setup.get_engine", return_value=mock_engine):
        setup_database(database_url="postgresql://localhost/test")

        # Verify that Alembic upgrade was called
        assert mock_subprocess_run.called

        # Verify that the pgvector extension command was executed
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


def test_setup_database_error(mock_engine, mock_subprocess_run):
    """Test database setup error handling when Alembic fails."""
    mock_subprocess_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="Alembic error"
    )

    with patch("spacemodels.db.setup.get_engine", return_value=mock_engine):
        with pytest.raises(RuntimeError, match="Alembic migration failed"):
            setup_database()


def test_reset_database_success(mock_engine, mock_subprocess_run):
    """Test successful database reset using Alembic."""
    with (
        patch("spacemodels.db.setup.get_engine", return_value=mock_engine),
        patch("spacemodels.db.setup.setup_database") as mock_setup,
    ):
        reset_database()

        # Verify that Alembic downgrade was called
        assert mock_subprocess_run.called
        call_args = mock_subprocess_run.call_args
        assert call_args[0][0] == ["alembic", "downgrade", "base"]

        # Verify that setup_database was called
        mock_setup.assert_called_once_with(None)


def test_reset_database_error(mock_engine, mock_subprocess_run):
    """Test database reset error handling when Alembic downgrade fails."""
    mock_subprocess_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="Alembic error"
    )

    with patch("spacemodels.db.setup.get_engine", return_value=mock_engine):
        with pytest.raises(RuntimeError, match="Alembic downgrade failed"):
            reset_database()
