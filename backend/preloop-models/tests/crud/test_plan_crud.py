"""Tests for plan CRUD operations."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import date

from sqlalchemy.orm import Session

from preloop_models.crud.plan import CRUDPlan, CRUDSubscription, CRUDMonthlyUsage
from preloop_models.models.plan import Plan, Subscription, MonthlyUsage


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_plan():
    """Fixture for a CRUDPlan instance."""
    return CRUDPlan(Plan)


@pytest.fixture
def crud_subscription():
    """Fixture for a CRUDSubscription instance."""
    return CRUDSubscription(Subscription)


@pytest.fixture
def crud_monthly_usage():
    """Fixture for a CRUDMonthlyUsage instance."""
    return CRUDMonthlyUsage(MonthlyUsage)


def test_get_active_public_plans(crud_plan, mock_db_session):
    """Test retrieving active public plans."""
    # Arrange
    mock_plans = [MagicMock(), MagicMock()]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = mock_plans

    # Act
    result = crud_plan.get_active_public_plans(mock_db_session)

    # Assert
    assert len(result) == 2


def test_get_active_custom_plans_for_account(crud_plan, mock_db_session):
    """Test retrieving active custom plans for an account."""
    # Arrange
    account_id = str(uuid4())
    mock_plans = [MagicMock()]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_plans

    # Act
    result = crud_plan.get_active_custom_plans_for_account(
        mock_db_session, account_id=account_id
    )

    # Assert
    assert len(result) == 1


def test_get_latest_for_account(crud_subscription, mock_db_session):
    """Test retrieving the latest subscription for an account."""
    # Arrange
    account_id = str(uuid4())
    mock_subscription = MagicMock()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.return_value = mock_subscription

    # Act
    result = crud_subscription.get_latest_for_account(
        mock_db_session, account_id=account_id
    )

    # Assert
    assert result == mock_subscription


def test_get_active_for_account(crud_subscription, mock_db_session):
    """Test retrieving the active subscription for an account."""
    # Arrange
    account_id = str(uuid4())
    mock_subscription = MagicMock()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_subscription

    # Act
    result = crud_subscription.get_active_for_account(
        mock_db_session, account_id=account_id
    )

    # Assert
    assert result == mock_subscription


def test_get_by_stripe_subscription_id(crud_subscription, mock_db_session):
    """Test retrieving a subscription by Stripe subscription ID."""
    # Arrange
    stripe_id = "sub_12345"
    mock_subscription = MagicMock()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_subscription

    # Act
    result = crud_subscription.get_by_stripe_subscription_id(
        mock_db_session, stripe_subscription_id=stripe_id
    )

    # Assert
    assert result == mock_subscription


def test_get_for_current_cycle(crud_monthly_usage, mock_db_session):
    """Test retrieving usage for the current billing cycle."""
    # Arrange
    subscription_id = str(uuid4())
    today = date.today()
    mock_usage = MagicMock()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_usage

    # Act
    result = crud_monthly_usage.get_for_current_cycle(
        mock_db_session, subscription_id=subscription_id, today=today
    )

    # Assert
    assert result == mock_usage
