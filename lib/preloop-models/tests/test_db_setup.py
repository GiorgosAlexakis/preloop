"""Tests for database setup utilities."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from spacemodels.db.setup import reset_database, setup_database
from spacemodels.models.base import Base


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy engine."""
    mock = MagicMock()
    mock.connect.return_value.__enter__.return_value = MagicMock()
    return mock


@pytest.fixture
def mock_base_metadata(monkeypatch):
    """Mock Base.metadata."""
    metadata_mock = MagicMock()
    monkeypatch.setattr(Base, "metadata", metadata_mock)
    return metadata_mock


def test_setup_database_success(mock_engine, mock_base_metadata):
    """Test successful database setup."""
    with patch("spacemodels.db.setup.get_engine", return_value=mock_engine):
        setup_database()

        # Verify that create_all was called
        mock_base_metadata.create_all.assert_called_once_with(mock_engine)


def test_setup_database_with_pgvector(mock_engine, mock_base_metadata):
    """Test database setup with pgvector extension."""
    with patch("spacemodels.db.setup.get_engine", return_value=mock_engine):
        setup_database(database_url="postgresql://localhost/test")

        # Verify that create_all was called
        mock_base_metadata.create_all.assert_called_once_with(mock_engine)

        # Verify that the pgvector extension command was executed
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


def test_setup_database_error(mock_engine, mock_base_metadata):
    """Test database setup error handling."""
    mock_base_metadata.create_all.side_effect = SQLAlchemyError("Test error")

    with patch("spacemodels.db.setup.get_engine", return_value=mock_engine):
        with pytest.raises(SQLAlchemyError):
            setup_database()


def test_reset_database_success(mock_engine, mock_base_metadata):
    """Test successful database reset."""
    with (
        patch("spacemodels.db.setup.get_engine", return_value=mock_engine),
        patch("spacemodels.db.setup.setup_database") as mock_setup,
    ):
        reset_database()

        # Verify that drop_all was called
        mock_base_metadata.drop_all.assert_called_once_with(mock_engine)

        # Verify that setup_database was called
        mock_setup.assert_called_once_with(None)


def test_reset_database_error(mock_engine, mock_base_metadata):
    """Test database reset error handling."""
    mock_base_metadata.drop_all.side_effect = SQLAlchemyError("Test error")

    with patch("spacemodels.db.setup.get_engine", return_value=mock_engine):
        with pytest.raises(SQLAlchemyError):
            reset_database()
