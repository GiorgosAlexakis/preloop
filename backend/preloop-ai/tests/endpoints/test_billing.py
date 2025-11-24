"""Tests for billing API endpoints."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from preloop_models.crud import crud_account, crud_user
from preloop_models.crud.plan import (
    plan as crud_plan,
    subscription as crud_subscription,
)
from preloop_models.models.user import User


def _get_test_plan_features():
    """Get valid plan features for testing."""
    return {
        "api_calls_monthly": 10000,
        "ai_calls_monthly": 1000,
        "issues_ingested_monthly": 5000,
        "custom_ai_models_enabled": False,
        "custom_compliance_metrics_enabled": False,
    }


class TestCreatePlan:
    """Test POST /billing/plans endpoint."""

    def test_create_plan_success(
        self, client: TestClient, test_user: User, db_session: Session
    ):
        """Test creating a plan as superuser."""
        # Make the test user a superuser
        test_user.is_superuser = True
        db_session.commit()

        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.create_plan"
        ) as mock_create:
            mock_plan = MagicMock()
            mock_plan.id = str(uuid.uuid4())
            mock_plan.name = "Test Plan"
            mock_plan.price_monthly = 10.0
            mock_plan.features = _get_test_plan_features()
            mock_plan.created_at = datetime.now(timezone.utc)
            mock_plan.updated_at = datetime.now(timezone.utc)
            mock_create.return_value = mock_plan

            response = client.post(
                "/api/v1/billing/plans",
                json={
                    "name": "Test Plan",
                    "price_monthly": 10.0,
                    "features": _get_test_plan_features(),
                },
            )

            assert response.status_code == 201
            mock_create.assert_called_once()

    def test_create_plan_unauthorized(
        self, client: TestClient, test_user: User, db_session: Session
    ):
        """Test creating a plan as non-superuser fails."""
        # Ensure test user is not superuser
        test_user.is_superuser = False
        db_session.commit()

        response = client.post(
            "/api/v1/billing/plans",
            json={
                "name": "Test Plan",
                "price_monthly": 10.0,
                "features": _get_test_plan_features(),
            },
        )

        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]


class TestListPublicPlans:
    """Test GET /billing/plans endpoint."""

    def test_list_public_plans_success(self, client: TestClient, db_session: Session):
        """Test listing public plans."""
        # Create some test plans
        plan1 = crud_plan.create(
            db_session,
            obj_in={
                "id": str(uuid.uuid4()),
                "name": "Basic Plan",
                "price_monthly": 10.0,
                "features": _get_test_plan_features(),
                "is_active": True,
                "is_custom": False,
            },
        )
        plan2 = crud_plan.create(
            db_session,
            obj_in={
                "id": str(uuid.uuid4()),
                "name": "Pro Plan",
                "price_monthly": 20.0,
                "features": _get_test_plan_features(),
                "is_active": True,
                "is_custom": False,
            },
        )
        db_session.commit()

        response = client.get("/api/v1/billing/plans")

        assert response.status_code == 200
        plans = response.json()
        assert len(plans) >= 2
        plan_names = [p["name"] for p in plans]
        assert "Basic Plan" in plan_names
        assert "Pro Plan" in plan_names

    def test_list_public_plans_no_auth_required(self, client: TestClient):
        """Test listing public plans works without authentication."""
        response = client.get("/api/v1/billing/plans")
        assert response.status_code == 200


class TestListCustomPlans:
    """Test GET /billing/custom-plans endpoint."""

    def test_list_custom_plans_success(
        self, client: TestClient, test_user: User, db_session: Session
    ):
        """Test listing custom plans for an account."""
        # Create a custom plan for the user's account
        custom_plan = crud_plan.create(
            db_session,
            obj_in={
                "id": str(uuid.uuid4()),
                "name": "Custom Plan",
                "price_monthly": 50.0,
                "features": _get_test_plan_features(),
                "is_active": True,
                "is_custom": True,
                "account_id": test_user.account_id,
            },
        )
        db_session.commit()

        response = client.get("/api/v1/billing/custom-plans")

        assert response.status_code == 200
        plans = response.json()
        assert any(p["name"] == "Custom Plan" for p in plans)


class TestGetSubscription:
    """Test GET /billing/subscription endpoint."""

    def test_get_subscription_success(
        self, client: TestClient, test_user: User, db_session: Session
    ):
        """Test getting current subscription."""
        # Create a plan and subscription
        plan = crud_plan.create(
            db_session,
            obj_in={
                "id": str(uuid.uuid4()),
                "name": "Test Plan",
                "price_monthly": 10.0,
                "features": _get_test_plan_features(),
                "is_active": True,
                "is_custom": False,
            },
        )
        now = datetime.now(timezone.utc)
        subscription = crud_subscription.create(
            db_session,
            obj_in={
                "account_id": test_user.account_id,
                "plan_id": plan.id,
                "stripe_subscription_id": "sub_123",
                "status": "active",
                "current_period_start": now,
                "current_period_end": now + timedelta(days=30),
            },
        )
        db_session.commit()

        response = client.get("/api/v1/billing/subscription")

        assert response.status_code == 200
        sub_data = response.json()
        assert sub_data["status"] == "active"
        assert sub_data["plan_id"] == str(plan.id)

    def test_get_subscription_not_found(self, client: TestClient, test_user: User):
        """Test getting subscription when none exists."""
        response = client.get("/api/v1/billing/subscription")

        assert response.status_code == 404
        assert "Subscription not found" in response.json()["detail"]


class TestCheckoutSuccess:
    """Test GET /billing/checkout-success endpoint."""

    def test_checkout_success_new_user(self, client: TestClient, db_session: Session):
        """Test checkout success redirects appropriately."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService._handle_checkout_session_completed"
        ) as mock_handle:
            # Create a test account with a primary user that needs password reset
            account = crud_account.create(
                db_session,
                obj_in={
                    "organization_name": "Test Org",
                    "stripe_customer_id": "cus_123",
                    "is_active": True,
                },
            )
            user = crud_user.create(
                db_session,
                obj_in={
                    "account_id": account.id,
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "full_name": "New User",
                    "hashed_password": "NEEDS_RESET",
                    "is_active": True,
                    "email_verified": False,
                    "user_source": "local",
                },
            )
            account.primary_user_id = user.id
            db_session.commit()
            db_session.refresh(account)

            mock_handle.return_value = account

            response = client.get(
                "/api/v1/billing/checkout-success?session_id=sess_123",
                follow_redirects=False,
            )

            assert response.status_code == 307  # Redirect
            location = response.headers["location"]
            # Should redirect somewhere (either welcome for new users or console for existing)
            assert "/welcome" in location or "/console" in location

    def test_checkout_success_existing_user(
        self, client: TestClient, db_session: Session
    ):
        """Test checkout success redirects existing users to console."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService._handle_checkout_session_completed"
        ) as mock_handle:
            # Create a test account with existing user (has real password)
            account = crud_account.create(
                db_session,
                obj_in={
                    "organization_name": "Test Org",
                    "stripe_customer_id": "cus_123",
                    "is_active": True,
                },
            )
            user = crud_user.create(
                db_session,
                obj_in={
                    "account_id": account.id,
                    "username": "existinguser",
                    "email": "existing@example.com",
                    "hashed_password": "hashed_password_here",
                    "is_active": True,
                    "email_verified": True,
                    "user_source": "local",
                },
            )
            account.primary_user_id = user.id
            db_session.commit()

            mock_handle.return_value = account

            response = client.get(
                "/api/v1/billing/checkout-success?session_id=sess_123",
                follow_redirects=False,
            )

            assert response.status_code == 307  # Redirect
            assert "/console/settings/subscription" in response.headers["location"]

    def test_checkout_success_session_not_found(self, client: TestClient):
        """Test checkout success with invalid session."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService._handle_checkout_session_completed"
        ) as mock_handle:
            mock_handle.return_value = None

            response = client.get(
                "/api/v1/billing/checkout-success?session_id=invalid_session"
            )

            assert response.status_code == 404


class TestGetCheckoutSessionDetails:
    """Test GET /billing/checkout-session-details endpoint."""

    def test_get_checkout_session_details_success(self, client: TestClient):
        """Test getting checkout session details."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.get_user_details_from_session"
        ) as mock_get_details:
            mock_get_details.return_value = {
                "email": "test@example.com",
                "username": "testuser",
            }

            response = client.get(
                "/api/v1/billing/checkout-session-details?session_id=sess_123"
            )

            assert response.status_code == 200
            details = response.json()
            assert details["email"] == "test@example.com"
            assert details["username"] == "testuser"

    def test_get_checkout_session_details_not_found(self, client: TestClient):
        """Test getting details for non-existent session."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.get_user_details_from_session"
        ) as mock_get_details:
            mock_get_details.return_value = None

            response = client.get(
                "/api/v1/billing/checkout-session-details?session_id=invalid"
            )

            assert response.status_code == 404


class TestCreateCheckoutSession:
    """Test POST /billing/create-checkout-session endpoint."""

    @pytest.mark.asyncio
    async def test_create_checkout_session_authenticated(
        self, client: TestClient, test_user: User
    ):
        """Test creating checkout session as authenticated user."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.create_checkout_session"
        ) as mock_create:
            mock_create.return_value = {"url": "https://checkout.stripe.com/pay/123"}

            response = client.post(
                "/api/v1/billing/create-checkout-session",
                json={"plan_id": str(uuid.uuid4()), "interval": "month"},
            )

            assert response.status_code == 200
            assert "url" in response.json()
            mock_create.assert_called_once()

    def test_create_checkout_session_unauthenticated(self, client: TestClient):
        """Test creating checkout session without authentication."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.create_checkout_session"
        ) as mock_create:
            mock_create.return_value = {"url": "https://checkout.stripe.com/pay/123"}

            response = client.post(
                "/api/v1/billing/create-checkout-session",
                json={"plan_id": str(uuid.uuid4()), "interval": "month"},
            )

            # Should work - unauthenticated users can start checkout
            assert response.status_code == 200


class TestCreatePortalSession:
    """Test POST /billing/create-portal-session endpoint."""

    def test_create_portal_session_success(self, client: TestClient, test_user: User):
        """Test creating portal session."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.create_portal_session"
        ) as mock_create:
            mock_create.return_value = "https://billing.stripe.com/session/123"

            response = client.post(
                "/api/v1/billing/create-portal-session",
                json={"return_url": "https://example.com/return"},
            )

            assert response.status_code == 200
            assert response.json()["url"] == "https://billing.stripe.com/session/123"

    def test_create_portal_session_error(self, client: TestClient, test_user: User):
        """Test creating portal session with error."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.create_portal_session"
        ) as mock_create:
            mock_create.side_effect = Exception("Stripe error")

            response = client.post(
                "/api/v1/billing/create-portal-session",
                json={"return_url": "https://example.com/return"},
            )

            assert response.status_code == 500


class TestStripeWebhooks:
    """Test POST /billing/webhooks endpoint."""

    @pytest.mark.asyncio
    async def test_stripe_webhooks_success(self, client: TestClient):
        """Test handling stripe webhooks."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.handle_webhook"
        ) as mock_handle:
            mock_handle.return_value = None

            response = client.post(
                "/api/v1/billing/webhooks",
                json={"type": "checkout.session.completed", "data": {}},
                headers={"stripe-signature": "sig_123"},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "success"

    @pytest.mark.asyncio
    async def test_stripe_webhooks_error(self, client: TestClient):
        """Test handling stripe webhooks with error."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.handle_webhook"
        ) as mock_handle:
            mock_handle.side_effect = Exception("Invalid webhook")

            response = client.post(
                "/api/v1/billing/webhooks",
                json={"type": "unknown.event", "data": {}},
                headers={"stripe-signature": "sig_invalid"},
            )

            assert response.status_code == 500


class TestSyncSubscription:
    """Test POST /billing/sync-subscription endpoint."""

    def test_sync_subscription_success(self, client: TestClient, test_user: User):
        """Test syncing subscription status."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.sync_subscription_status"
        ) as mock_sync:
            mock_sync.return_value = None

            response = client.post(
                "/api/v1/billing/sync-subscription",
            )

            assert response.status_code == 200
            assert response.json()["status"] == "success"
            mock_sync.assert_called_once_with(account_id=test_user.account_id)

    def test_sync_subscription_not_found(self, client: TestClient, test_user: User):
        """Test syncing subscription when account not found."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.sync_subscription_status"
        ) as mock_sync:
            mock_sync.side_effect = ValueError("Account not found")

            response = client.post(
                "/api/v1/billing/sync-subscription",
            )

            assert response.status_code == 404

    def test_sync_subscription_error(self, client: TestClient, test_user: User):
        """Test syncing subscription with error."""
        with patch(
            "preloop_ai.plugins.proprietary.billing.service.BillingService.sync_subscription_status"
        ) as mock_sync:
            mock_sync.side_effect = Exception("Stripe API error")

            response = client.post(
                "/api/v1/billing/sync-subscription",
            )

            assert response.status_code == 500
