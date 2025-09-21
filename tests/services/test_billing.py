import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from spacebridge.services.billing import BillingService
from spacemodels.models import Subscription, MonthlyUsage
from spacemodels.schemas.plan import PlanCreate, SubscriptionCreate


@pytest.fixture
def db_session():
    """Creates a mock database session."""
    session = MagicMock(spec=Session)
    session.query.return_value.filter.return_value.first.return_value = None
    return session


@pytest.fixture
def billing_service(db_session):
    """Creates a BillingService instance with a mock database session."""
    with patch("spacebridge.services.billing.stripe.api_key", "test_key"):
        return BillingService(db_session)


def test_create_plan(billing_service, db_session):
    """Test creating a new subscription plan."""
    plan_data = PlanCreate(
        id="test_plan",
        name="Test Plan",
        description="A plan for testing",
        prices={"month": 1000, "year": 10000},
        features={
            "api_calls_monthly": 1000,
            "ai_calls_monthly": 100,
            "issues_ingested_monthly": 500,
            "custom_ai_models_enabled": True,
            "custom_compliance_metrics_enabled": False,
        },
    )
    billing_service.create_plan(plan_data)
    db_session.add.assert_called_once()
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once()


def test_create_subscription(billing_service, db_session):
    """Test creating a new subscription."""
    subscription_data = SubscriptionCreate(
        account_id=uuid.uuid4(),
        plan_id="test_plan",
        status="active",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        stripe_subscription_id="sub_123",
    )
    billing_service.create_subscription(subscription_data)
    db_session.add.assert_called_once()
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once()


def test_record_usage(billing_service, db_session):
    """Test recording usage for a metric."""
    account_id = uuid.uuid4()
    subscription = Subscription(
        id=1,
        account_id=account_id,
        status="active",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
    )
    db_session.query.return_value.filter.return_value.first.return_value = subscription

    billing_service.record_usage(account_id, "ai_calls")

    db_session.add.assert_called()
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called()


def test_check_limit_within_limit(billing_service, db_session):
    """Test checking usage when within the limit."""
    account_id = uuid.uuid4()
    plan_mock = MagicMock()
    plan_mock.features = {"ai_calls_monthly": 100}
    subscription_mock = MagicMock()
    subscription_mock.plan = plan_mock
    subscription_mock.id = 1
    usage_mock = MagicMock()
    usage_mock.usage_counts = {"ai_calls": 50}

    def query_side_effect(model):
        if model == Subscription:
            q = MagicMock()
            q.join.return_value.filter.return_value.filter.return_value.first.return_value = subscription_mock
            return q
        elif model == MonthlyUsage:
            q = MagicMock()
            q.filter.return_value.filter.return_value.filter.return_value.first.return_value = usage_mock
            return q
        return MagicMock()

    db_session.query.side_effect = query_side_effect

    assert billing_service.check_limit(account_id, "ai_calls") is True


def test_check_limit_over_limit(billing_service, db_session):
    """Test checking usage when over the limit."""
    account_id = uuid.uuid4()
    plan_mock = MagicMock()
    plan_mock.features = {"ai_calls_monthly": 100}
    subscription_mock = MagicMock()
    subscription_mock.plan = plan_mock
    subscription_mock.id = 1
    usage_mock = MagicMock()
    usage_mock.usage_counts = {"ai_calls": 100}

    def query_side_effect(model):
        if model == Subscription:
            q = MagicMock()
            q.join.return_value.filter.return_value.filter.return_value.first.return_value = subscription_mock
            return q
        elif model == MonthlyUsage:
            q = MagicMock()
            q.filter.return_value.filter.return_value.filter.return_value.first.return_value = usage_mock
            return q
        return MagicMock()

    db_session.query.side_effect = query_side_effect

    assert billing_service.check_limit(account_id, "ai_calls") is False


def test_has_feature_enabled(billing_service, db_session):
    """Test checking for an enabled feature."""
    account_id = uuid.uuid4()
    plan_mock = MagicMock()
    plan_mock.features = {"custom_ai_models_enabled": True}
    subscription_mock = MagicMock()
    subscription_mock.plan = plan_mock
    db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = subscription_mock

    assert billing_service.has_feature(account_id, "custom_ai_models") is True


def test_has_feature_disabled(billing_service, db_session):
    """Test checking for a disabled feature."""
    account_id = uuid.uuid4()
    plan_mock = MagicMock()
    plan_mock.features = {"custom_ai_models_enabled": False}
    subscription_mock = MagicMock()
    subscription_mock.plan = plan_mock
    db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = subscription_mock

    assert billing_service.has_feature(account_id, "custom_ai_models") is False
