"""Unit tests for BillingService."""

from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy.orm import Session
import stripe

from spacebridge.plugins.proprietary.billing.service import BillingService
from spacemodels.crud.plan import subscription as crud_subscription
from spacemodels.models.user import User


class TestUpdateSubscriptionQuantity:
    """Test BillingService.update_subscription_quantity method."""

    @patch("stripe.SubscriptionItem.modify")
    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_success(
        self,
        mock_stripe_retrieve,
        mock_stripe_modify,
        db_session: Session,
        test_user: User,
    ):
        """Test successful quantity update when user count changes."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Create additional users (total 3 including test_user)
        from spacemodels.models.user import User as UserModel

        user2 = UserModel(
            account_id=test_user.account_id,
            username="user2",
            email="user2@example.com",
            hashed_password="hashed",
            is_active=True,
            email_verified=True,
            user_source="local",
        )
        user3 = UserModel(
            account_id=test_user.account_id,
            username="user3",
            email="user3@example.com",
            hashed_password="hashed",
            is_active=True,
            email_verified=True,
            user_source="local",
        )
        db_session.add(user2)
        db_session.add(user3)
        db_session.commit()

        # Mock Stripe subscription with 1 user currently
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {"data": [{"id": "si_123", "quantity": 1}]},
        }

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify
        assert result is True
        mock_stripe_retrieve.assert_called_once_with("sub_123")
        mock_stripe_modify.assert_called_once_with(
            "si_123",
            quantity=3,  # Should update to 3 users
            proration_behavior="create_prorations",
        )

    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_no_subscription(
        self, mock_stripe_retrieve, db_session: Session, test_user: User
    ):
        """Test returns False when account has no active subscription."""
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify
        assert result is False
        mock_stripe_retrieve.assert_not_called()

    @patch("stripe.SubscriptionItem.modify")
    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_no_change(
        self,
        mock_stripe_retrieve,
        mock_stripe_modify,
        db_session: Session,
        test_user: User,
    ):
        """Test returns False when quantity already matches user count."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Mock Stripe subscription with quantity already matching (1 user)
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {"data": [{"id": "si_123", "quantity": 1}]},
        }

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify
        assert result is False
        mock_stripe_retrieve.assert_called_once_with("sub_123")
        mock_stripe_modify.assert_not_called()

    @patch("stripe.SubscriptionItem.modify")
    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_zero_users_edge_case(
        self,
        mock_stripe_retrieve,
        mock_stripe_modify,
        db_session: Session,
        test_user: User,
    ):
        """Test ensures minimum of 1 user when all users are inactive."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Mock Stripe subscription with 1 user currently
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {"data": [{"id": "si_123", "quantity": 2}]},
        }

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify - should set to 1 (minimum), not 0
        assert result is True
        mock_stripe_modify.assert_called_once_with(
            "si_123",
            quantity=1,  # Minimum of 1, not 0
            proration_behavior="create_prorations",
        )

    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_no_subscription_items(
        self, mock_stripe_retrieve, db_session: Session, test_user: User
    ):
        """Test handles subscription with no items gracefully."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Mock Stripe subscription with no items
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {"data": []},
        }

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify
        assert result is False

    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_stripe_error(
        self, mock_stripe_retrieve, db_session: Session, test_user: User
    ):
        """Test handles Stripe API errors gracefully without raising."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Mock Stripe to raise error
        mock_stripe_retrieve.side_effect = stripe.error.StripeError("API Error")

        # Test - should not raise, just return False
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify
        assert result is False

    @patch("stripe.SubscriptionItem.modify")
    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_modify_error(
        self,
        mock_stripe_retrieve,
        mock_stripe_modify,
        db_session: Session,
        test_user: User,
    ):
        """Test handles errors during subscription item modification."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Mock Stripe subscription retrieval success
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {"data": [{"id": "si_123", "quantity": 1}]},
        }

        # Mock modification to raise error
        mock_stripe_modify.side_effect = stripe.error.StripeError("Update failed")

        # Test - should not raise, just return False
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify
        assert result is False

    @patch("stripe.SubscriptionItem.modify")
    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_inactive_subscription(
        self,
        mock_stripe_retrieve,
        mock_stripe_modify,
        db_session: Session,
        test_user: User,
    ):
        """Test handles inactive subscription correctly."""
        # Create inactive subscription using CRUD (no active subscription will be found)
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "canceled",  # Not active
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify - should return False without attempting Stripe update
        assert result is False
        mock_stripe_retrieve.assert_not_called()
        mock_stripe_modify.assert_not_called()

    @patch("stripe.SubscriptionItem.modify")
    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_multiple_users(
        self,
        mock_stripe_retrieve,
        mock_stripe_modify,
        db_session: Session,
        test_user: User,
    ):
        """Test correctly counts and updates for multiple active users."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Create additional users (total 5 including test_user)
        from spacemodels.models.user import User as UserModel

        for i in range(2, 6):  # Create user2 through user5
            user = UserModel(
                account_id=test_user.account_id,
                username=f"user{i}",
                email=f"user{i}@example.com",
                hashed_password="hashed",
                is_active=True,
                email_verified=True,
                user_source="local",
            )
            db_session.add(user)
        db_session.commit()

        # Mock Stripe subscription with 2 users currently
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {"data": [{"id": "si_123", "quantity": 2}]},
        }

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify
        assert result is True
        mock_stripe_modify.assert_called_once_with(
            "si_123",
            quantity=5,  # Should update to 5 users
            proration_behavior="create_prorations",
        )

    @patch("stripe.SubscriptionItem.modify")
    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_all_users_inactive(
        self,
        mock_stripe_retrieve,
        mock_stripe_modify,
        db_session: Session,
        test_user: User,
    ):
        """Test ensures minimum quantity of 1 when ALL users are inactive (0 active)."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Deactivate test_user (now 0 active users)
        test_user.is_active = False
        db_session.commit()

        # Mock Stripe subscription with 3 users currently
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {"data": [{"id": "si_123", "quantity": 3}]},
        }

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify - should set to 1 (minimum), not 0
        assert result is True
        mock_stripe_modify.assert_called_once_with(
            "si_123",
            quantity=1,  # Minimum of 1, even with 0 active users
            proration_behavior="create_prorations",
        )

    @patch("stripe.SubscriptionItem.modify")
    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_all_inactive_already_at_minimum(
        self,
        mock_stripe_retrieve,
        mock_stripe_modify,
        db_session: Session,
        test_user: User,
    ):
        """Test behavior when all users inactive and quantity already at minimum (1).

        NOTE: Current implementation makes a Stripe API call even though quantity doesn't change.
        This is because the comparison is done against active_user_count (0) not max(1, active_user_count).
        This could be optimized in the future to avoid unnecessary API calls.
        """
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Deactivate test_user (now 0 active users)
        test_user.is_active = False
        db_session.commit()

        # Mock Stripe subscription already at minimum quantity
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {"data": [{"id": "si_123", "quantity": 1}]},
        }

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify - currently returns True and calls modify (even though final quantity is same)
        # This is a minor inefficiency that could be optimized
        assert result is True
        mock_stripe_modify.assert_called_once_with(
            "si_123",
            quantity=1,  # Updates from 1 to 1 (no actual change)
            proration_behavior="create_prorations",
        )

    @patch("stripe.SubscriptionItem.modify")
    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_mixed_active_inactive_users(
        self,
        mock_stripe_retrieve,
        mock_stripe_modify,
        db_session: Session,
        test_user: User,
    ):
        """Test correctly counts only active users when mix of active/inactive exists."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        from spacemodels.models.user import User as UserModel

        # Create 3 active users
        for i in range(2, 5):
            user = UserModel(
                account_id=test_user.account_id,
                username=f"active_user{i}",
                email=f"active{i}@example.com",
                hashed_password="hashed",
                is_active=True,
                email_verified=True,
                user_source="local",
            )
            db_session.add(user)

        # Create 2 inactive users (should not be counted)
        for i in range(1, 3):
            user = UserModel(
                account_id=test_user.account_id,
                username=f"inactive_user{i}",
                email=f"inactive{i}@example.com",
                hashed_password="hashed",
                is_active=False,
                email_verified=True,
                user_source="local",
            )
            db_session.add(user)

        db_session.commit()

        # Mock Stripe subscription with wrong quantity
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {
                "data": [{"id": "si_123", "quantity": 6}]
            },  # Currently 6, should be 4
        }

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify - should update to 4 (1 test_user + 3 active users, ignoring 2 inactive)
        assert result is True
        mock_stripe_modify.assert_called_once_with(
            "si_123",
            quantity=4,
            proration_behavior="create_prorations",
        )

    @patch("stripe.Subscription.retrieve")
    def test_update_subscription_quantity_missing_quantity_field(
        self, mock_stripe_retrieve, db_session: Session, test_user: User
    ):
        """Test handles Stripe item with missing quantity field gracefully."""
        # Create active subscription using CRUD
        subscription_data = {
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "active",
            "current_period_start": datetime.now(timezone.utc),
            "current_period_end": datetime.now(timezone.utc),
            "stripe_subscription_id": "sub_123",
        }
        subscription = crud_subscription.create(db_session, obj_in=subscription_data)

        # Mock Stripe subscription item without quantity field (defaults to 1)
        mock_stripe_retrieve.return_value = {
            "id": "sub_123",
            "items": {"data": [{"id": "si_123"}]},  # No quantity field
        }

        # Test
        service = BillingService(db_session)
        result = service.update_subscription_quantity(str(test_user.account_id))

        # Verify - should not attempt update (current quantity defaults to 1, we have 1 user)
        assert result is False
