"""Tests for billing service."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
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


class TestCreateCheckoutSession:
    """Test create_checkout_session method."""

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.crud_account")
    def test_create_checkout_session_no_account(
        self, mock_crud_account, mock_stripe, billing_service, mock_db
    ):
        """Test creating checkout session without account (new customer)."""
        # Mock price lookup
        mock_price = MagicMock()
        mock_price.id = "price_123"
        mock_price.recurring = {"interval": "month"}
        mock_stripe.Price.list.return_value.data = [mock_price]

        # Mock checkout session creation
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/session_123"
        mock_stripe.checkout.Session.create.return_value = mock_session

        result = billing_service.create_checkout_session(
            plan_id="premium", interval="month", account_id=None
        )

        assert result["url"] == "https://checkout.stripe.com/session_123"
        assert result["action"] == "redirect"
        mock_stripe.checkout.Session.create.assert_called_once()

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.crud_account")
    @patch("spacebridge.services.billing.crud_user")
    def test_create_checkout_session_existing_account_no_subscription(
        self, mock_crud_user, mock_crud_account, mock_stripe, billing_service, mock_db
    ):
        """Test creating checkout session for existing account without subscription."""
        account_id = uuid.uuid4()
        user_email = "test@example.com"

        # Mock account
        mock_account = MagicMock(spec=Account)
        mock_account.id = account_id
        mock_account.stripe_customer_id = None
        mock_account.primary_user_id = uuid.uuid4()
        mock_account.get_active_subscription.return_value = None

        mock_crud_account.get.return_value = mock_account

        # Mock user
        mock_user = MagicMock()
        mock_user.email = user_email
        mock_crud_user.get.return_value = mock_user

        # Mock price lookup
        mock_price = MagicMock()
        mock_price.id = "price_123"
        mock_price.recurring = {"interval": "month"}
        mock_stripe.Price.list.return_value.data = [mock_price]

        # Mock checkout session creation
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/session_456"
        mock_stripe.checkout.Session.create.return_value = mock_session

        result = billing_service.create_checkout_session(
            plan_id="premium", interval="month", account_id=account_id
        )

        assert result["url"] == "https://checkout.stripe.com/session_456"
        assert result["action"] == "redirect"

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.crud_account")
    def test_create_checkout_session_with_existing_subscription(
        self, mock_crud_account, mock_stripe, billing_service, mock_db
    ):
        """Test updating subscription for account with existing paid plan."""
        account_id = uuid.uuid4()

        # Mock account with active subscription
        mock_subscription = MagicMock(spec=Subscription)
        mock_subscription.stripe_subscription_id = "sub_existing"

        mock_account = MagicMock(spec=Account)
        mock_account.id = account_id
        mock_account.stripe_customer_id = "cus_123"
        mock_account.get_active_subscription.return_value = mock_subscription

        mock_crud_account.get.return_value = mock_account

        # Mock price lookup
        mock_price = MagicMock()
        mock_price.id = "price_new"
        mock_price.recurring = {"interval": "year"}
        mock_stripe.Price.list.return_value.data = [mock_price]

        # Mock Stripe subscription retrieval and update
        mock_item = MagicMock()
        mock_item.id = "si_old"

        mock_stripe_sub = MagicMock()
        mock_stripe_sub.__getitem__.side_effect = (
            lambda k: {"data": [mock_item]} if k == "items" else None
        )
        mock_stripe.Subscription.retrieve.return_value = mock_stripe_sub

        mock_updated_sub = MagicMock()
        mock_updated_sub.plan.product = "new_plan"
        mock_updated_sub.status = "active"
        mock_updated_sub.items.return_value.mapping = {
            "items": {
                "data": [
                    {
                        "current_period_start": 1234567890,
                        "current_period_end": 1237159890,
                    }
                ]
            }
        }
        mock_stripe.Subscription.modify.return_value = mock_updated_sub

        result = billing_service.create_checkout_session(
            plan_id="enterprise", interval="year", account_id=account_id
        )

        assert result["status"] == "success"
        assert result["action"] == "refresh"
        mock_stripe.Subscription.modify.assert_called_once()

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.crud_account")
    def test_create_checkout_session_price_not_found(
        self, mock_crud_account, mock_stripe, billing_service, mock_db
    ):
        """Test error when price not found in Stripe."""
        # Mock empty price list
        mock_stripe.Price.list.return_value.data = []

        with pytest.raises(ValueError, match="No active price found"):
            billing_service.create_checkout_session(
                plan_id="nonexistent", interval="month"
            )

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.crud_account")
    def test_create_checkout_session_account_not_found(
        self, mock_crud_account, mock_stripe, billing_service, mock_db
    ):
        """Test error when account not found."""
        account_id = uuid.uuid4()
        mock_crud_account.get.return_value = None

        with pytest.raises(ValueError, match="Account not found"):
            billing_service.create_checkout_session(
                plan_id="premium", interval="month", account_id=account_id
            )


class TestCreatePortalSession:
    """Test create_portal_session method."""

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.crud_account")
    def test_create_portal_session_success(
        self, mock_crud_account, mock_stripe, billing_service, mock_db
    ):
        """Test creating portal session successfully."""
        account_id = str(uuid.uuid4())
        return_url = "https://example.com/settings"

        # Mock account with Stripe customer
        mock_account = MagicMock(spec=Account)
        mock_account.stripe_customer_id = "cus_123"
        mock_crud_account.get.return_value = mock_account

        # Mock portal session creation
        mock_portal_session = MagicMock()
        mock_portal_session.url = "https://billing.stripe.com/portal_123"
        mock_stripe.billing_portal.Session.create.return_value = mock_portal_session

        result = billing_service.create_portal_session(account_id, return_url)

        assert result == "https://billing.stripe.com/portal_123"
        mock_stripe.billing_portal.Session.create.assert_called_once_with(
            customer="cus_123", return_url=return_url
        )

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.crud_account")
    def test_create_portal_session_no_account(
        self, mock_crud_account, mock_stripe, billing_service, mock_db
    ):
        """Test error when account not found."""
        account_id = str(uuid.uuid4())
        mock_crud_account.get.return_value = None

        with pytest.raises(ValueError, match="Account not found"):
            billing_service.create_portal_session(account_id, "https://example.com")

    @patch("spacebridge.services.billing.crud_user")
    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.crud_account")
    def test_create_portal_session_no_stripe_customer(
        self, mock_crud_account, mock_stripe, mock_crud_user, billing_service, mock_db
    ):
        """Test lazy creation of Stripe customer when account has no Stripe customer ID."""
        account_id = str(uuid.uuid4())
        primary_user_id = uuid.uuid4()
        return_url = "https://example.com"

        # Mock account without Stripe customer
        mock_account = MagicMock(spec=Account)
        mock_account.id = uuid.UUID(account_id)
        mock_account.stripe_customer_id = None
        mock_account.primary_user_id = primary_user_id
        mock_crud_account.get.return_value = mock_account

        # Mock primary user
        mock_user = MagicMock()
        mock_user.email = "user@example.com"
        mock_user.username = "testuser"
        mock_user.full_name = "Test User"
        mock_user.id = primary_user_id
        mock_crud_user.get.return_value = mock_user

        # Mock Stripe customer creation
        mock_stripe_customer = MagicMock()
        mock_stripe_customer.id = "cus_new123"
        mock_stripe.Customer.create.return_value = mock_stripe_customer

        # Mock portal session creation
        mock_portal_session = MagicMock()
        mock_portal_session.url = "https://billing.stripe.com/portal_456"
        mock_stripe.billing_portal.Session.create.return_value = mock_portal_session

        result = billing_service.create_portal_session(account_id, return_url)

        # Verify Stripe customer was created
        mock_stripe.Customer.create.assert_called_once()
        # Verify portal session was created
        assert result == "https://billing.stripe.com/portal_456"
        mock_stripe.billing_portal.Session.create.assert_called_once_with(
            customer="cus_new123", return_url=return_url
        )


class TestHandleWebhook:
    """Test handle_webhook method."""

    @patch("spacebridge.services.billing.stripe")
    def test_handle_webhook_checkout_completed(
        self, mock_stripe, billing_service, mock_db
    ):
        """Test handling checkout.session.completed webhook."""
        payload = b'{"type": "checkout.session.completed"}'
        sig_header = "test_signature"

        # Mock event construction
        mock_event = MagicMock()
        mock_event.type = "checkout.session.completed"
        mock_event.data.object.id = "cs_test_123"
        mock_stripe.Webhook.construct_event.return_value = mock_event

        # Mock the handler
        with patch.object(
            billing_service, "_handle_checkout_session_completed"
        ) as mock_handler:
            billing_service.handle_webhook(payload, sig_header)
            mock_handler.assert_called_once_with("cs_test_123")

    @patch("spacebridge.services.billing.stripe")
    def test_handle_webhook_invoice_paid(self, mock_stripe, billing_service, mock_db):
        """Test handling invoice.paid webhook."""
        payload = b'{"type": "invoice.paid"}'
        sig_header = "test_signature"

        mock_invoice = MagicMock()
        mock_event = MagicMock()
        mock_event.type = "invoice.paid"
        mock_event.data.object = mock_invoice
        mock_stripe.Webhook.construct_event.return_value = mock_event

        with patch.object(billing_service, "_handle_invoice_paid") as mock_handler:
            billing_service.handle_webhook(payload, sig_header)
            mock_handler.assert_called_once_with(mock_invoice)

    @patch("spacebridge.services.billing.stripe")
    def test_handle_webhook_subscription_updated(
        self, mock_stripe, billing_service, mock_db
    ):
        """Test handling customer.subscription.updated webhook."""
        payload = b'{"type": "customer.subscription.updated"}'
        sig_header = "test_signature"

        mock_sub = MagicMock()
        mock_event = MagicMock()
        mock_event.type = "customer.subscription.updated"
        mock_event.data.object = mock_sub
        mock_stripe.Webhook.construct_event.return_value = mock_event

        with patch.object(
            billing_service, "_handle_subscription_updated"
        ) as mock_handler:
            billing_service.handle_webhook(payload, sig_header)
            mock_handler.assert_called_once_with(mock_sub)

    @patch("spacebridge.services.billing.stripe")
    def test_handle_webhook_subscription_deleted(
        self, mock_stripe, billing_service, mock_db
    ):
        """Test handling customer.subscription.deleted webhook."""
        payload = b'{"type": "customer.subscription.deleted"}'
        sig_header = "test_signature"

        mock_sub = MagicMock()
        mock_event = MagicMock()
        mock_event.type = "customer.subscription.deleted"
        mock_event.data.object = mock_sub
        mock_stripe.Webhook.construct_event.return_value = mock_event

        with patch.object(
            billing_service, "_handle_subscription_deleted"
        ) as mock_handler:
            billing_service.handle_webhook(payload, sig_header)
            mock_handler.assert_called_once_with(mock_sub)

    @patch("spacebridge.services.billing.stripe")
    def test_handle_webhook_invalid_payload(
        self, mock_stripe, billing_service, mock_db
    ):
        """Test handling webhook with invalid payload."""
        payload = b"invalid"
        sig_header = "test_signature"

        mock_stripe.Webhook.construct_event.side_effect = ValueError("Invalid payload")

        with pytest.raises(HTTPException) as exc_info:
            billing_service.handle_webhook(payload, sig_header)

        assert exc_info.value.status_code == 400
        assert "Invalid payload" in str(exc_info.value.detail)

    @patch("spacebridge.services.billing.stripe")
    def test_handle_webhook_unhandled_event_type(
        self, mock_stripe, billing_service, mock_db
    ):
        """Test handling webhook with unhandled event type."""
        payload = b'{"type": "test"}'
        sig_header = "test_signature"

        mock_event = MagicMock()
        mock_event.type = "unhandled.event.type"
        mock_stripe.Webhook.construct_event.return_value = mock_event

        # Should not raise an exception, just log
        billing_service.handle_webhook(payload, sig_header)


class TestHandleInvoicePaid:
    """Test _handle_invoice_paid method."""

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.subscription")
    def test_handle_invoice_paid_success(
        self, mock_subscription_crud, mock_stripe, billing_service, mock_db
    ):
        """Test handling invoice paid successfully."""
        # Mock invoice
        mock_invoice = MagicMock()
        mock_invoice.subscription = "sub_123"

        # Mock subscription from DB
        mock_subscription = MagicMock(spec=Subscription)
        mock_subscription_crud.get_by_stripe_subscription_id.return_value = (
            mock_subscription
        )

        # Mock Stripe subscription
        mock_stripe_sub = MagicMock()
        mock_stripe_sub.items.return_value.mapping = {
            "items": {
                "data": [
                    {
                        "current_period_start": 1234567890,
                        "current_period_end": 1237159890,
                    }
                ]
            }
        }
        mock_stripe.Subscription.retrieve.return_value = mock_stripe_sub

        billing_service._handle_invoice_paid(mock_invoice)

        assert mock_subscription.status == "active"
        assert mock_db.commit.called


class TestHandleSubscriptionUpdated:
    """Test _handle_subscription_updated method."""

    @patch("spacebridge.services.billing.subscription")
    def test_handle_subscription_updated_success(
        self, mock_subscription_crud, billing_service, mock_db
    ):
        """Test handling subscription update successfully."""
        # Mock Stripe subscription
        mock_stripe_sub = MagicMock()
        mock_stripe_sub.id = "sub_123"
        mock_stripe_sub.plan.product = "new_plan"
        mock_stripe_sub.status = "active"
        mock_stripe_sub.cancel_at_period_end = False
        mock_stripe_sub.items.return_value.mapping = {
            "items": {
                "data": [
                    {
                        "current_period_start": 1234567890,
                        "current_period_end": 1237159890,
                    }
                ]
            }
        }

        # Mock subscription from DB
        mock_subscription = MagicMock(spec=Subscription)
        mock_subscription_crud.get_by_stripe_subscription_id.return_value = (
            mock_subscription
        )

        billing_service._handle_subscription_updated(mock_stripe_sub)

        assert mock_subscription.plan_id == "new_plan"
        assert mock_subscription.status == "active"
        assert mock_db.commit.called

    @patch("spacebridge.services.billing.subscription")
    def test_handle_subscription_updated_pending_cancellation(
        self, mock_subscription_crud, billing_service, mock_db
    ):
        """Test handling subscription update with pending cancellation."""
        # Mock Stripe subscription with cancellation scheduled
        mock_stripe_sub = MagicMock()
        mock_stripe_sub.id = "sub_123"
        mock_stripe_sub.plan.product = "plan"
        mock_stripe_sub.cancel_at_period_end = True
        mock_stripe_sub.items.return_value.mapping = {
            "items": {
                "data": [
                    {
                        "current_period_start": 1234567890,
                        "current_period_end": 1237159890,
                    }
                ]
            }
        }

        mock_subscription = MagicMock(spec=Subscription)
        mock_subscription_crud.get_by_stripe_subscription_id.return_value = (
            mock_subscription
        )

        billing_service._handle_subscription_updated(mock_stripe_sub)

        assert mock_subscription.status == "pending_cancellation"
        assert mock_db.commit.called


class TestHandleSubscriptionDeleted:
    """Test _handle_subscription_deleted method."""

    @patch("spacebridge.services.billing.subscription")
    def test_handle_subscription_deleted_success(
        self, mock_subscription_crud, billing_service, mock_db
    ):
        """Test handling subscription deletion successfully."""
        # Mock Stripe subscription
        mock_stripe_sub = MagicMock()
        mock_stripe_sub.id = "sub_123"

        # Mock subscription from DB
        mock_subscription = MagicMock(spec=Subscription)
        mock_subscription_crud.get_by_stripe_subscription_id.return_value = (
            mock_subscription
        )

        billing_service._handle_subscription_deleted(mock_stripe_sub)

        assert mock_subscription.status == "canceled"
        assert mock_db.commit.called


class TestGetUserDetailsFromSession:
    """Test get_user_details_from_session method."""

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.crud_user")
    def test_get_user_details_success(
        self, mock_crud_user, mock_stripe, billing_service, mock_db
    ):
        """Test retrieving user details from session successfully."""
        session_id = "cs_test_123"

        # Mock Stripe session
        mock_session = MagicMock()
        mock_session.status = "complete"
        mock_session.customer.email = "test@example.com"
        mock_stripe.checkout.Session.retrieve.return_value = mock_session

        # Mock user from DB
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_crud_user.get_by_email.return_value = mock_user

        result = billing_service.get_user_details_from_session(session_id)

        assert result["email"] == "test@example.com"
        assert result["username"] == "testuser"

    @patch("spacebridge.services.billing.stripe")
    def test_get_user_details_incomplete_session(
        self, mock_stripe, billing_service, mock_db
    ):
        """Test retrieving details from incomplete session."""
        session_id = "cs_test_123"

        mock_session = MagicMock()
        mock_session.status = "pending"
        mock_stripe.checkout.Session.retrieve.return_value = mock_session

        result = billing_service.get_user_details_from_session(session_id)

        assert result is None

    @patch("spacebridge.services.billing.stripe")
    def test_get_user_details_no_email(self, mock_stripe, billing_service, mock_db):
        """Test retrieving details when session has no email."""
        session_id = "cs_test_123"

        mock_session = MagicMock()
        mock_session.status = "complete"
        mock_session.customer.email = None
        mock_stripe.checkout.Session.retrieve.return_value = mock_session

        result = billing_service.get_user_details_from_session(session_id)

        assert result is None


class TestSyncSubscriptionStatus:
    """Test sync_subscription_status method."""

    @patch("spacebridge.services.billing.stripe")
    @patch("spacebridge.services.billing.subscription")
    def test_sync_subscription_status_success(
        self, mock_subscription_crud, mock_stripe, billing_service, mock_db
    ):
        """Test syncing subscription status successfully."""
        account_id = uuid.uuid4()

        # Mock subscription from DB
        mock_subscription = MagicMock(spec=Subscription)
        mock_subscription.stripe_subscription_id = "sub_123"
        mock_subscription_crud.get_latest_for_account.return_value = mock_subscription

        # Mock Stripe subscription
        mock_stripe_sub = MagicMock()
        mock_stripe.Subscription.retrieve.return_value = mock_stripe_sub

        # Mock the update handler
        with patch.object(
            billing_service, "_handle_subscription_updated"
        ) as mock_handler:
            billing_service.sync_subscription_status(account_id)
            mock_handler.assert_called_once_with(mock_stripe_sub)

    @patch("spacebridge.services.billing.subscription")
    def test_sync_subscription_status_no_subscription(
        self, mock_subscription_crud, billing_service, mock_db
    ):
        """Test syncing when no subscription exists."""
        account_id = uuid.uuid4()
        mock_subscription_crud.get_latest_for_account.return_value = None

        # Should not raise an exception
        billing_service.sync_subscription_status(account_id)

        # Verify no Stripe API calls were made
        assert not mock_db.commit.called
