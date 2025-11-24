"""Tests for webhook CRUD operations."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from preloop_models.crud.webhook import CRUDWebhook
from preloop_models.models.webhook import Webhook


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_webhook():
    """Fixture for a CRUDWebhook instance."""
    return CRUDWebhook(Webhook)


def test_get_by_project_id(crud_webhook, mock_db_session):
    """Test retrieving a webhook by project ID."""
    # Arrange
    project_id = str(uuid4())
    mock_webhook = MagicMock()
    mock_webhook.project_id = project_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_webhook

    # Act
    result = crud_webhook.get_by_project_id(mock_db_session, project_id=project_id)

    # Assert
    assert result.project_id == project_id
    mock_db_session.query.assert_called_once()


def test_get_by_project_id_with_account(crud_webhook, mock_db_session):
    """Test retrieving a webhook by project ID with account filter."""
    # Arrange
    project_id = str(uuid4())
    account_id = str(uuid4())
    mock_webhook = MagicMock()
    mock_webhook.project_id = project_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.first.return_value = mock_webhook

    # Act
    result = crud_webhook.get_by_project_id(
        mock_db_session, project_id=project_id, account_id=account_id
    )

    # Assert
    assert result.project_id == project_id


def test_get_all_by_project(crud_webhook, mock_db_session):
    """Test retrieving all webhooks for a project."""
    # Arrange
    project_id = str(uuid4())
    mock_webhook1 = MagicMock()
    mock_webhook1.project_id = project_id
    mock_webhook2 = MagicMock()
    mock_webhook2.project_id = project_id
    mock_webhooks = [mock_webhook1, mock_webhook2]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_webhooks

    # Act
    result = crud_webhook.get_all_by_project(
        mock_db_session, project_id=project_id, skip=0, limit=100
    )

    # Assert
    assert len(result) == 2
    assert all(w.project_id == project_id for w in result)


def test_get_all_by_project_with_account(crud_webhook, mock_db_session):
    """Test retrieving all webhooks for a project with account filter."""
    # Arrange
    project_id = str(uuid4())
    account_id = str(uuid4())
    mock_webhooks = [MagicMock(), MagicMock()]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_webhooks

    # Act
    result = crud_webhook.get_all_by_project(
        mock_db_session, project_id=project_id, account_id=account_id
    )

    # Assert
    assert len(result) == 2


def test_get_all_by_organization(crud_webhook, mock_db_session):
    """Test retrieving all webhooks for an organization."""
    # Arrange
    organization_id = str(uuid4())
    mock_webhooks = [MagicMock(), MagicMock()]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_webhooks

    # Act
    result = crud_webhook.get_all_by_organization(
        mock_db_session, organization_id=organization_id, skip=0, limit=100
    )

    # Assert
    assert len(result) == 2


def test_get_all_by_organization_with_account(crud_webhook, mock_db_session):
    """Test retrieving all webhooks for an organization with account filter."""
    # Arrange
    organization_id = str(uuid4())
    account_id = str(uuid4())
    mock_webhooks = [MagicMock()]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_webhooks

    # Act
    result = crud_webhook.get_all_by_organization(
        mock_db_session, organization_id=organization_id, account_id=account_id
    )

    # Assert
    assert len(result) == 1


def test_get_by_external_id(crud_webhook, mock_db_session):
    """Test retrieving a webhook by external ID and tracker ID."""
    # Arrange
    external_id = "ext-123"
    tracker_id = str(uuid4())
    mock_webhook = MagicMock()
    mock_webhook.external_id = external_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.outerjoin.return_value = mock_query
    mock_query.first.return_value = mock_webhook

    # Act
    result = crud_webhook.get_by_external_id(
        mock_db_session, external_id=external_id, tracker_id=tracker_id
    )

    # Assert
    assert result.external_id == external_id


def test_get_by_external_id_with_account(crud_webhook, mock_db_session):
    """Test retrieving a webhook by external ID with account filter."""
    # Arrange
    external_id = "ext-123"
    tracker_id = str(uuid4())
    account_id = str(uuid4())
    mock_webhook = MagicMock()
    mock_webhook.external_id = external_id

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.outerjoin.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.first.return_value = mock_webhook

    # Act
    result = crud_webhook.get_by_external_id(
        mock_db_session,
        external_id=external_id,
        tracker_id=tracker_id,
        account_id=account_id,
    )

    # Assert
    assert result.external_id == external_id


def test_remove(crud_webhook, mock_db_session):
    """Test removing a webhook by ID."""
    # Arrange
    webhook_id = str(uuid4())
    expected_delete_count = 1

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.delete.return_value = expected_delete_count

    # Act
    result = crud_webhook.remove(mock_db_session, id=webhook_id)

    # Assert
    assert result == expected_delete_count
    mock_query.delete.assert_called_once()
