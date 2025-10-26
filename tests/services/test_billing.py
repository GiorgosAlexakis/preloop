"""Tests for billing service."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from spacemodels.models import Account, MonthlyUsage, Plan, Subscription
from spacemodels.schemas.plan import PlanCreate, SubscriptionCreate

from spacebridge.services.billing import BillingService


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MagicMock()


@pytest.fixture
def billing_service(mock_db):
    """Create BillingService instance with mocked database."""
    with patch("spacebridge.services.billing.stripe"):
        service = BillingService(mock_db)
        return service


class TestCreatePlan:
    """Test create_plan method."""

    def test_create_plan_success(self, billing_service, mock_db):
        """Test creating a new plan."""
        plan_data = PlanCreate(
            id="premium",
            name="Premium Plan",
            description="Premium features",
            price_monthly=29.99,
            price_yearly=299.99,
            features={
                "api_calls_monthly": 1000,
                "ai_calls_monthly": 500,
                "issues_ingested_monthly": 2000,
                "custom_ai_models_enabled": True,
                "custom_compliance_metrics_enabled": True,
            },
        )

        # Mock db.refresh to set database-generated fields
        def mock_refresh(obj):
            obj.created_at = datetime.now()
            obj.updated_at = datetime.now()

        mock_db.refresh.side_effect = mock_refresh

        result = billing_service.create_plan(plan_data)

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

    def test_create_plan_with_all_features(self, billing_service, mock_db):
        """Test creating a plan with complete feature set."""
        plan_data = PlanCreate(
            id="enterprise",
            name="Enterprise Plan",
            description="Enterprise features",
            price_monthly=99.99,
            price_yearly=999.99,
            features={
                "api_calls_monthly": -1,  # Unlimited
                "ai_calls_monthly": -1,
                "issues_ingested_monthly": -1,
                "custom_ai_models_enabled": True,
                "custom_compliance_metrics_enabled": True,
            },
        )

        result = billing_service.create_plan(plan_data)

        assert mock_db.add.called
        assert mock_db.commit.called


class TestCreateSubscription:
    """Test create_subscription method."""

    def test_create_subscription_success(self, billing_service, mock_db):
        """Test creating a new subscription."""
        account_id = uuid.uuid4()
        subscription_data = SubscriptionCreate(
            account_id=account_id,
            plan_id="premium",
            status="active",
            current_period_start=datetime.now(),
            current_period_end=datetime.now() + timedelta(days=30),
            stripe_subscription_id="sub_123",
        )

        # Mock db.refresh
        def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now()
            obj.updated_at = datetime.now()

        mock_db.refresh.side_effect = mock_refresh

        result = billing_service.create_subscription(subscription_data)

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called


class TestRecordUsage:
    """Test record_usage method."""

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.monthly_usage")
    def test_record_usage_creates_new_record(
        self, mock_monthly_usage, mock_subscription, billing_service, mock_db
    ):
        """Test recording usage creates new monthly usage record."""
        account_id = uuid.uuid4()
        subscription_id = uuid.uuid4()

        # Mock active subscription
        mock_subscription_obj = MagicMock(spec=Subscription)
        mock_subscription_obj.id = subscription_id
        mock_subscription_obj.current_period_start = datetime.now()
        mock_subscription_obj.current_period_end = datetime.now() + timedelta(days=30)

        mock_subscription.get_active_for_account.return_value = mock_subscription_obj

        # No existing usage record
        mock_monthly_usage.get_for_current_cycle.return_value = None

        # Mock db.refresh
        def mock_refresh(obj):
            if hasattr(obj, "id") and isinstance(obj, MonthlyUsage):
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now()
                obj.updated_at = datetime.now()

        mock_db.refresh.side_effect = mock_refresh

        result = billing_service.record_usage(account_id, "executions", 1)

        assert mock_db.add.called
        assert mock_db.commit.called
        mock_subscription.get_active_for_account.assert_called_once_with(
            mock_db, account_id=str(account_id)
        )
        mock_monthly_usage.get_for_current_cycle.assert_called_once()

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.monthly_usage")
    def test_record_usage_updates_existing_record(
        self, mock_monthly_usage, mock_subscription, billing_service, mock_db
    ):
        """Test recording usage updates existing monthly usage record."""
        account_id = uuid.uuid4()
        subscription_id = uuid.uuid4()

        # Mock active subscription
        mock_subscription_obj = MagicMock(spec=Subscription)
        mock_subscription_obj.id = subscription_id

        mock_subscription.get_active_for_account.return_value = mock_subscription_obj

        # Mock existing usage record
        mock_usage = MagicMock(spec=MonthlyUsage)
        mock_usage.usage_counts = {"executions": 10}

        mock_monthly_usage.get_for_current_cycle.return_value = mock_usage

        result = billing_service.record_usage(account_id, "executions", 5)

        # Verify usage was updated
        assert mock_usage.usage_counts["executions"] == 15
        assert mock_db.add.called
        assert mock_db.commit.called

    @patch("spacebridge.services.billing.subscription")
    def test_record_usage_no_active_subscription(
        self, mock_subscription, billing_service, mock_db
    ):
        """Test recording usage when no active subscription exists."""
        account_id = uuid.uuid4()

        # Mock no active subscription
        mock_subscription.get_active_for_account.return_value = None

        result = billing_service.record_usage(account_id, "executions", 1)

        assert result is None
        assert not mock_db.commit.called

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.monthly_usage")
    def test_record_usage_new_metric(
        self, mock_monthly_usage, mock_subscription, billing_service, mock_db
    ):
        """Test recording usage for a new metric type."""
        account_id = uuid.uuid4()
        subscription_id = uuid.uuid4()

        mock_subscription_obj = MagicMock(spec=Subscription)
        mock_subscription_obj.id = subscription_id

        mock_subscription.get_active_for_account.return_value = mock_subscription_obj

        mock_usage = MagicMock(spec=MonthlyUsage)
        mock_usage.usage_counts = {"executions": 10}

        mock_monthly_usage.get_for_current_cycle.return_value = mock_usage

        result = billing_service.record_usage(account_id, "api_calls", 100)

        assert mock_usage.usage_counts["api_calls"] == 100
        assert mock_usage.usage_counts["executions"] == 10  # Original metric unchanged


class TestCheckLimit:
    """Test check_limit method."""

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.monthly_usage")
    def test_check_limit_within_limit(
        self, mock_monthly_usage, mock_subscription, billing_service, mock_db
    ):
        """Test check_limit returns True when within limit."""
        account_id = uuid.uuid4()

        # Mock subscription with plan
        mock_plan = MagicMock(spec=Plan)
        mock_plan.features = {"executions_monthly": 1000}

        mock_subscription_obj = MagicMock(spec=Subscription)
        mock_subscription_obj.id = uuid.uuid4()
        mock_subscription_obj.plan = mock_plan

        mock_subscription.get_active_for_account.return_value = mock_subscription_obj

        # Mock usage record
        mock_usage = MagicMock(spec=MonthlyUsage)
        mock_usage.usage_counts = {"executions": 500}

        mock_monthly_usage.get_for_current_cycle.return_value = mock_usage

        result = billing_service.check_limit(account_id, "executions")

        assert result is True

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.monthly_usage")
    def test_check_limit_exceeds_limit(
        self, mock_monthly_usage, mock_subscription, billing_service, mock_db
    ):
        """Test check_limit returns False when exceeds limit."""
        account_id = uuid.uuid4()

        mock_plan = MagicMock(spec=Plan)
        mock_plan.features = {"executions_monthly": 1000}

        mock_subscription_obj = MagicMock(spec=Subscription)
        mock_subscription_obj.id = uuid.uuid4()
        mock_subscription_obj.plan = mock_plan

        mock_subscription.get_active_for_account.return_value = mock_subscription_obj

        mock_usage = MagicMock(spec=MonthlyUsage)
        mock_usage.usage_counts = {"executions": 1000}

        mock_monthly_usage.get_for_current_cycle.return_value = mock_usage

        result = billing_service.check_limit(account_id, "executions")

        assert result is False

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.monthly_usage")
    def test_check_limit_unlimited(
        self, mock_monthly_usage, mock_subscription, billing_service, mock_db
    ):
        """Test check_limit returns True for unlimited (-1) limit."""
        account_id = uuid.uuid4()

        mock_plan = MagicMock(spec=Plan)
        mock_plan.features = {"executions_monthly": -1}  # Unlimited

        mock_subscription_obj = MagicMock(spec=Subscription)
        mock_subscription_obj.id = uuid.uuid4()
        mock_subscription_obj.plan = mock_plan

        mock_subscription.get_active_for_account.return_value = mock_subscription_obj

        mock_usage = MagicMock(spec=MonthlyUsage)
        mock_usage.usage_counts = {"executions": 999999}

        mock_monthly_usage.get_for_current_cycle.return_value = mock_usage

        result = billing_service.check_limit(account_id, "executions")

        assert result is True

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.monthly_usage")
    def test_check_limit_no_usage_record(
        self, mock_monthly_usage, mock_subscription, billing_service, mock_db
    ):
        """Test check_limit returns True when no usage record exists."""
        account_id = uuid.uuid4()

        mock_plan = MagicMock(spec=Plan)
        mock_plan.features = {"executions_monthly": 1000}

        mock_subscription_obj = MagicMock(spec=Subscription)
        mock_subscription_obj.id = uuid.uuid4()
        mock_subscription_obj.plan = mock_plan

        mock_subscription.get_active_for_account.return_value = mock_subscription_obj

        # No usage record
        mock_monthly_usage.get_for_current_cycle.return_value = None

        result = billing_service.check_limit(account_id, "executions")

        assert result is True


class TestHasFeature:
    """Test has_feature method."""

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.plan")
    def test_has_feature_enabled(
        self, mock_plan_crud, mock_subscription_crud, billing_service, mock_db
    ):
        """Test has_feature returns True when feature is enabled."""
        account_id = uuid.uuid4()

        mock_plan = MagicMock(spec=Plan)
        mock_plan.features = {"mcp_servers_enabled": True}

        mock_subscription = MagicMock(spec=Subscription)
        mock_subscription.plan = mock_plan

        mock_subscription_crud.get_active_for_account.return_value = mock_subscription

        result = billing_service.has_feature(account_id, "mcp_servers")

        assert result is True
        mock_subscription_crud.get_active_for_account.assert_called_once_with(
            mock_db, account_id=str(account_id)
        )

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.plan")
    def test_has_feature_disabled(
        self, mock_plan_crud, mock_subscription_crud, billing_service, mock_db
    ):
        """Test has_feature returns False when feature is disabled."""
        account_id = uuid.uuid4()

        mock_plan = MagicMock(spec=Plan)
        mock_plan.features = {"mcp_servers_enabled": False}

        mock_subscription = MagicMock(spec=Subscription)
        mock_subscription.plan = mock_plan

        mock_subscription_crud.get_active_for_account.return_value = mock_subscription

        result = billing_service.has_feature(account_id, "mcp_servers")

        assert result is False

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.plan")
    def test_has_feature_not_in_plan(
        self, mock_plan_crud, mock_subscription_crud, billing_service, mock_db
    ):
        """Test has_feature returns False when feature not in plan."""
        account_id = uuid.uuid4()

        mock_plan = MagicMock(spec=Plan)
        mock_plan.features = {}

        mock_subscription = MagicMock(spec=Subscription)
        mock_subscription.plan = mock_plan

        mock_subscription_crud.get_active_for_account.return_value = mock_subscription

        result = billing_service.has_feature(account_id, "advanced_analytics")

        assert result is False

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.plan")
    def test_has_feature_no_subscription_uses_free_plan(
        self, mock_plan_crud, mock_subscription_crud, billing_service, mock_db
    ):
        """Test has_feature uses free plan when no subscription exists."""
        account_id = uuid.uuid4()

        mock_free_plan = MagicMock(spec=Plan)
        mock_free_plan.features = {"basic_features_enabled": True}

        # No active subscription
        mock_subscription_crud.get_active_for_account.return_value = None

        # Free plan is found
        mock_plan_crud.get.return_value = mock_free_plan

        result = billing_service.has_feature(account_id, "basic_features")

        assert result is True
        mock_subscription_crud.get_active_for_account.assert_called_once_with(
            mock_db, account_id=str(account_id)
        )
        mock_plan_crud.get.assert_called_once_with(mock_db, id="free")

    @patch("spacebridge.services.billing.subscription")
    @patch("spacebridge.services.billing.plan")
    def test_has_feature_no_subscription_no_free_plan(
        self, mock_plan_crud, mock_subscription_crud, billing_service, mock_db
    ):
        """Test has_feature returns False when no subscription and no free plan."""
        account_id = uuid.uuid4()

        # No active subscription
        mock_subscription_crud.get_active_for_account.return_value = None

        # No free plan found
        mock_plan_crud.get.return_value = None

        result = billing_service.has_feature(account_id, "any_feature")

        assert result is False
        mock_subscription_crud.get_active_for_account.assert_called_once_with(
            mock_db, account_id=str(account_id)
        )
        mock_plan_crud.get.assert_called_once_with(mock_db, id="free")


class TestGenerateUniqueUsername:
    """Test _generate_unique_username method."""

    def test_generate_username_from_email(self, billing_service, mock_db):
        """Test generating username from email."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = billing_service._generate_unique_username("john.doe@example.com")

        assert result == "johndoe"

    def test_generate_username_with_conflict(self, billing_service, mock_db):
        """Test generating username when conflict exists."""
        # First query returns existing user, second returns None
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(spec=Account),  # Username exists
            None,  # New username available
        ]

        result = billing_service._generate_unique_username("john.doe@example.com")

        assert result.startswith("johndoe_")
        assert len(result) > len("johndoe_")

    def test_generate_username_with_special_characters(self, billing_service, mock_db):
        """Test generating username with special characters in email."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = billing_service._generate_unique_username("test+user@example.com")

        assert result == "testuser"

    def test_generate_username_empty_prefix(self, billing_service, mock_db):
        """Test generating username with empty prefix."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = billing_service._generate_unique_username("@example.com")

        assert result == "user"

    def test_generate_username_numbers_allowed(self, billing_service, mock_db):
        """Test that numbers are allowed in username."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = billing_service._generate_unique_username("user123@example.com")

        assert result == "user123"
