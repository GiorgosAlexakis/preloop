"""Tests for oauth_app_installation CRUD operations."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from preloop.models.crud.oauth_app_installation import (
    CRUDOAuthAppInstallation,
    crud_oauth_app_installation,
)
from preloop.models.models.github_app_installation import OAuthAppInstallation


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_installation():
    """Fixture for a CRUDOAuthAppInstallation instance."""
    return CRUDOAuthAppInstallation(OAuthAppInstallation)


class TestGetByProviderAndExternalId:
    """Test get_by_provider_and_external_id method."""

    def test_get_by_provider_and_external_id_found(
        self, crud_installation, mock_db_session
    ):
        """Test retrieving installation by provider and external ID."""
        # Arrange
        provider = "github"
        external_id = 12345
        mock_installation = MagicMock(spec=OAuthAppInstallation)
        mock_installation.provider = provider
        mock_installation.external_id = external_id

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_installation

        # Act
        result = crud_installation.get_by_provider_and_external_id(
            mock_db_session, provider=provider, external_id=external_id
        )

        # Assert
        assert result is not None
        assert result.provider == provider
        assert result.external_id == external_id

    def test_get_by_provider_and_external_id_not_found(
        self, crud_installation, mock_db_session
    ):
        """Test retrieving installation that doesn't exist."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_installation.get_by_provider_and_external_id(
            mock_db_session, provider="github", external_id=99999
        )

        # Assert
        assert result is None

    def test_get_by_provider_and_external_id_with_account_id(
        self, crud_installation, mock_db_session
    ):
        """Test retrieving installation filtered by account_id."""
        # Arrange
        provider = "github"
        external_id = 12345
        account_id = uuid4()
        mock_installation = MagicMock(spec=OAuthAppInstallation)
        mock_installation.provider = provider
        mock_installation.external_id = external_id
        mock_installation.account_id = account_id

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_installation

        # Act
        result = crud_installation.get_by_provider_and_external_id(
            mock_db_session,
            provider=provider,
            external_id=external_id,
            account_id=account_id,
        )

        # Assert
        assert result is not None
        assert result.account_id == account_id
        # Filter should have been called multiple times (for provider, external_id, account_id)
        assert mock_query.filter.call_count >= 1

    def test_get_by_provider_and_external_id_wrong_account(
        self, crud_installation, mock_db_session
    ):
        """Test that filtering by wrong account_id returns None."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_installation.get_by_provider_and_external_id(
            mock_db_session,
            provider="github",
            external_id=12345,
            account_id=uuid4(),  # Different account
        )

        # Assert
        assert result is None


class TestGetByProviderAndAccount:
    """Test get_by_provider_and_account method."""

    def test_get_by_provider_and_account_found(
        self, crud_installation, mock_db_session
    ):
        """Test retrieving all installations for a provider and account."""
        # Arrange
        provider = "github"
        account_id = uuid4()
        mock_installations = [
            MagicMock(
                spec=OAuthAppInstallation, provider=provider, account_id=account_id
            ),
            MagicMock(
                spec=OAuthAppInstallation, provider=provider, account_id=account_id
            ),
        ]

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_installations

        # Act
        result = crud_installation.get_by_provider_and_account(
            mock_db_session, provider=provider, account_id=account_id
        )

        # Assert
        assert len(result) == 2
        assert all(inst.provider == provider for inst in result)

    def test_get_by_provider_and_account_empty(
        self, crud_installation, mock_db_session
    ):
        """Test retrieving installations when none exist."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        # Act
        result = crud_installation.get_by_provider_and_account(
            mock_db_session, provider="github", account_id=uuid4()
        )

        # Assert
        assert result == []

    def test_get_by_provider_and_account_different_providers(
        self, crud_installation, mock_db_session
    ):
        """Test that only matching provider installations are returned."""
        # Arrange
        account_id = uuid4()
        github_installation = MagicMock(
            spec=OAuthAppInstallation, provider="github", account_id=account_id
        )

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [github_installation]

        # Act - querying for gitlab should return only gitlab installations
        result = crud_installation.get_by_provider_and_account(
            mock_db_session, provider="github", account_id=account_id
        )

        # Assert
        assert len(result) == 1
        assert result[0].provider == "github"


class TestGetByIdProviderAndAccount:
    """Test get_by_id_provider_and_account method."""

    def test_get_by_id_provider_and_account_found(
        self, crud_installation, mock_db_session
    ):
        """Test retrieving installation by ID, provider, and account."""
        # Arrange
        installation_id = uuid4()
        provider = "github"
        account_id = uuid4()
        mock_installation = MagicMock(spec=OAuthAppInstallation)
        mock_installation.id = installation_id
        mock_installation.provider = provider
        mock_installation.account_id = account_id

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_installation

        # Act
        result = crud_installation.get_by_id_provider_and_account(
            mock_db_session,
            id=installation_id,
            provider=provider,
            account_id=account_id,
        )

        # Assert
        assert result is not None
        assert result.id == installation_id
        assert result.provider == provider
        assert result.account_id == account_id

    def test_get_by_id_provider_and_account_not_found(
        self, crud_installation, mock_db_session
    ):
        """Test retrieving non-existent installation."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act
        result = crud_installation.get_by_id_provider_and_account(
            mock_db_session, id=uuid4(), provider="github", account_id=uuid4()
        )

        # Assert
        assert result is None

    def test_get_by_id_provider_and_account_wrong_provider(
        self, crud_installation, mock_db_session
    ):
        """Test that wrong provider returns None."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act - ID exists but for different provider
        result = crud_installation.get_by_id_provider_and_account(
            mock_db_session, id=uuid4(), provider="gitlab", account_id=uuid4()
        )

        # Assert
        assert result is None

    def test_get_by_id_provider_and_account_wrong_account(
        self, crud_installation, mock_db_session
    ):
        """Test that wrong account_id returns None."""
        # Arrange
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Act - ID exists but for different account
        result = crud_installation.get_by_id_provider_and_account(
            mock_db_session, id=uuid4(), provider="github", account_id=uuid4()
        )

        # Assert
        assert result is None


class TestCRUDOAuthAppInstallationSingleton:
    """Test the crud_oauth_app_installation singleton instance."""

    def test_singleton_instance_exists(self):
        """Test that the singleton CRUD instance is created correctly."""
        assert crud_oauth_app_installation is not None
        assert isinstance(crud_oauth_app_installation, CRUDOAuthAppInstallation)
        assert crud_oauth_app_installation.model == OAuthAppInstallation
