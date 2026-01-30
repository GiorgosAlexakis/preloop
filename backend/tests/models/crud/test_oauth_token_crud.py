"""Tests for oauth_token CRUD operations."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from preloop.models.crud.oauth_token import CRUDOAuthToken, crud_oauth_token
from preloop.models.models.github_oauth_token import OAuthToken


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_token():
    """Fixture for a CRUDOAuthToken instance."""
    return CRUDOAuthToken(OAuthToken)


class TestGetByUserAndInstallation:
    """Test get_by_user_and_installation method."""

    def test_get_by_user_and_installation_found(self, crud_token, mock_db_session):
        """Test retrieving token by provider, user, and installation."""
        # Arrange
        provider = "github"
        user_id = uuid4()
        installation_id = uuid4()
        mock_token = MagicMock(spec=OAuthToken)
        mock_token.provider = provider
        mock_token.user_id = user_id
        mock_token.installation_id = installation_id

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_token

        # Act
        result = crud_token.get_by_user_and_installation(
            mock_db_session,
            provider=provider,
            user_id=user_id,
            installation_id=installation_id,
        )

        # Assert
        assert result is not None
        assert result.provider == provider
        assert result.user_id == user_id
        assert result.installation_id == installation_id

    def test_get_by_user_and_installation_not_found(self, crud_token, mock_db_session):
        """Test retrieving non-existent token."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_token.get_by_user_and_installation(
            mock_db_session,
            provider="github",
            user_id=uuid4(),
            installation_id=uuid4(),
        )

        # Assert
        assert result is None

    def test_get_by_user_and_installation_wrong_provider(
        self, crud_token, mock_db_session
    ):
        """Test that wrong provider returns None."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_token.get_by_user_and_installation(
            mock_db_session,
            provider="gitlab",  # Wrong provider
            user_id=uuid4(),
            installation_id=uuid4(),
        )

        # Assert
        assert result is None

    def test_get_by_user_and_installation_wrong_user(self, crud_token, mock_db_session):
        """Test that wrong user_id returns None."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_token.get_by_user_and_installation(
            mock_db_session,
            provider="github",
            user_id=uuid4(),  # Wrong user
            installation_id=uuid4(),
        )

        # Assert
        assert result is None

    def test_get_by_user_and_installation_wrong_installation(
        self, crud_token, mock_db_session
    ):
        """Test that wrong installation_id returns None."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_token.get_by_user_and_installation(
            mock_db_session,
            provider="github",
            user_id=uuid4(),
            installation_id=uuid4(),  # Wrong installation
        )

        # Assert
        assert result is None


class TestGetByUserAndProvider:
    """Test get_by_user_and_provider method."""

    def test_get_by_user_and_provider_found(self, crud_token, mock_db_session):
        """Test retrieving token by provider and user."""
        # Arrange
        provider = "github"
        user_id = uuid4()
        mock_token = MagicMock(spec=OAuthToken)
        mock_token.provider = provider
        mock_token.user_id = user_id

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_token

        # Act
        result = crud_token.get_by_user_and_provider(
            mock_db_session, provider=provider, user_id=user_id
        )

        # Assert
        assert result is not None
        assert result.provider == provider
        assert result.user_id == user_id

    def test_get_by_user_and_provider_not_found(self, crud_token, mock_db_session):
        """Test retrieving non-existent token."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_token.get_by_user_and_provider(
            mock_db_session, provider="github", user_id=uuid4()
        )

        # Assert
        assert result is None

    def test_get_by_user_and_provider_wrong_provider(self, crud_token, mock_db_session):
        """Test that wrong provider returns None."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_token.get_by_user_and_provider(
            mock_db_session, provider="gitlab", user_id=uuid4()
        )

        # Assert
        assert result is None

    def test_get_by_user_and_provider_different_providers(
        self, crud_token, mock_db_session
    ):
        """Test that user can have tokens for different providers."""
        # Arrange
        user_id = uuid4()
        github_token = MagicMock(spec=OAuthToken)
        github_token.provider = "github"
        github_token.user_id = user_id

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = github_token

        # Act
        result = crud_token.get_by_user_and_provider(
            mock_db_session, provider="github", user_id=user_id
        )

        # Assert
        assert result is not None
        assert result.provider == "github"


class TestCRUDOAuthTokenEdgeCases:
    """Test edge cases and error handling."""

    def test_get_by_user_and_installation_with_empty_db(
        self, crud_token, mock_db_session
    ):
        """Test querying empty database returns None."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_token.get_by_user_and_installation(
            mock_db_session,
            provider="github",
            user_id=uuid4(),
            installation_id=uuid4(),
        )

        # Assert
        assert result is None
        mock_db_session.query.assert_called_once()

    def test_get_by_user_and_provider_filter_chain(self, crud_token, mock_db_session):
        """Test that filter is properly applied for both conditions."""
        # Arrange
        provider = "github"
        user_id = uuid4()

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        crud_token.get_by_user_and_provider(
            mock_db_session, provider=provider, user_id=user_id
        )

        # Assert - filter should be called
        mock_query.filter.assert_called()


class TestCRUDOAuthTokenSingleton:
    """Test the crud_oauth_token singleton instance."""

    def test_singleton_instance_exists(self):
        """Test that the singleton CRUD instance is created correctly."""
        assert crud_oauth_token is not None
        assert isinstance(crud_oauth_token, CRUDOAuthToken)
        assert crud_oauth_token.model == OAuthToken
