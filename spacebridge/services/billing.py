"""
Service for handling billing, subscriptions, and usage tracking.
"""

import uuid
from datetime import date, datetime
from typing import Optional
import stripe
from sqlalchemy.orm import Session

from spacebridge.config import settings
from spacemodels.models import Account, Plan, Subscription, MonthlyUsage
from spacemodels.schemas.plan import PlanCreate, SubscriptionCreate, MonthlyUsageCreate


class BillingService:
    """
    Service for all billing and subscription related logic.
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        stripe.api_key = settings.stripe_secret_key

    def create_plan(self, plan_data: PlanCreate) -> Plan:
        """Creates a new subscription plan."""
        db_plan = Plan(**plan_data.dict())
        self.db.add(db_plan)
        self.db.commit()
        self.db.refresh(db_plan)
        return db_plan

    def create_subscription(
        self, subscription_data: SubscriptionCreate
    ) -> Subscription:
        """Creates a new subscription for an account."""
        db_subscription = Subscription(**subscription_data.dict())
        self.db.add(db_subscription)
        self.db.commit()
        self.db.refresh(db_subscription)
        return db_subscription

    def record_usage(
        self, account_id: uuid.UUID, metric: str, quantity: int = 1
    ) -> MonthlyUsage:
        """Records usage for a given metric and account."""
        # Find the active subscription for the account
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.account_id == account_id)
            .filter(Subscription.status == "active")
            .first()
        )
        if not subscription:
            # Or handle this case as an error, depending on business logic
            return None

        # Find or create the usage record for the current billing cycle
        today = date.today()
        usage_record = (
            self.db.query(MonthlyUsage)
            .filter(MonthlyUsage.subscription_id == subscription.id)
            .filter(MonthlyUsage.billing_cycle_start <= today)
            .filter(MonthlyUsage.billing_cycle_end >= today)
            .first()
        )

        if not usage_record:
            usage_data = MonthlyUsageCreate(
                subscription_id=subscription.id,
                billing_cycle_start=subscription.current_period_start.date(),
                billing_cycle_end=subscription.current_period_end.date(),
                usage_counts={metric: quantity},
            )
            usage_record = MonthlyUsage(**usage_data.dict())
            self.db.add(usage_record)
        else:
            # Atomically update the JSONB field
            current_count = usage_record.usage_counts.get(metric, 0)
            usage_record.usage_counts[metric] = current_count + quantity
            # Re-assign to trigger SQLAlchemy's change detection
            self.db.add(usage_record)

        self.db.commit()
        self.db.refresh(usage_record)
        return usage_record

    def check_limit(self, account_id: uuid.UUID, metric: str) -> bool:
        """Checks if an account is within its usage limit for a given metric."""
        subscription = (
            self.db.query(Subscription)
            .join(Plan)
            .filter(Subscription.account_id == account_id)
            .filter(Subscription.status == "active")
            .first()
        )
        if not subscription:
            # No active subscription, check against the 'free' plan
            free_plan = self.db.query(Plan).filter(Plan.id == "free").first()
            if not free_plan:
                return False  # No free plan configured
            limit = free_plan.features.get(f"{metric}_monthly")
        else:
            limit = subscription.plan.features.get(f"{metric}_monthly")
        if limit is None or limit == -1:  # -1 can represent unlimited
            return True

        today = date.today()
        usage_record = (
            self.db.query(MonthlyUsage)
            .filter(MonthlyUsage.subscription_id == subscription.id)
            .filter(MonthlyUsage.billing_cycle_start <= today)
            .filter(MonthlyUsage.billing_cycle_end >= today)
            .first()
        )

        if not usage_record:
            return True  # No usage yet

        current_usage = usage_record.usage_counts.get(metric, 0)
        return current_usage < limit

    def has_feature(self, account_id: uuid.UUID, feature: str) -> bool:
        """Checks if an account's plan has a specific feature enabled."""
        subscription = (
            self.db.query(Subscription)
            .join(Plan)
            .filter(Subscription.account_id == account_id)
            .filter(Subscription.status == "active")
            .first()
        )
        if not subscription:
            # No active subscription, check against the 'free' plan
            free_plan = self.db.query(Plan).filter(Plan.id == "free").first()
            if not free_plan:
                return False
            return free_plan.features.get(f"{feature}_enabled", False)

        return subscription.plan.features.get(f"{feature}_enabled", False)

    def create_checkout_session(
        self, plan_id: str, interval: str, account_id: uuid.UUID = None
    ) -> dict:
        """
        Creates a Stripe Checkout session for new subscriptions, or directly
        updates the subscription for existing customers.
        """
        # This logic is now unified for all upgrade/change paths
        if account_id:
            account = self.db.query(Account).filter(Account.id == account_id).first()
            if not account:
                raise ValueError("Account not found")
        else:
            account = None

        # Get the new price ID from Stripe
        price_lookup_key = f"{plan_id}_{interval}"
        prices = stripe.Price.list(lookup_keys=[price_lookup_key], active=True)
        if not prices.data:
            raise ValueError(f"Price not found for lookup key: {price_lookup_key}")
        new_price_id = prices.data[0].id

        if not account:
            # CASE 1: User is on a free plan (no active Stripe subscription)
            # We need to create a new subscription via Checkout.
            session_params = {
                "payment_method_types": ["card"],
                "line_items": [{"price": new_price_id, "quantity": 1}],
                "mode": "subscription",
                "success_url": f"{settings.spacebridge_url}/api/v1/billing/checkout-success?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": f"{settings.spacebridge_url}/console/settings/subscription",
            }

            checkout_session = stripe.checkout.Session.create(**session_params)
            return {"url": checkout_session.url, "action": "redirect"}

        active_subscription = (
            account.get_active_subscription(self.db) if account else None
        )

        if not active_subscription or not active_subscription.stripe_subscription_id:
            # CASE 2: User is on a free plan (no active Stripe subscription)
            # We need to create a new subscription via Checkout.
            session_params = {
                "payment_method_types": ["card"],
                "line_items": [{"price": new_price_id, "quantity": 1}],
                "mode": "subscription",
                "success_url": f"{settings.spacebridge_url}/api/v1/billing/checkout-success?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": f"{settings.spacebridge_url}/console/settings/subscription",
                "client_reference_id": str(account.id),
            }
            if account.stripe_customer_id:
                session_params["customer"] = account.stripe_customer_id
            else:
                session_params["customer_email"] = account.email

            checkout_session = stripe.checkout.Session.create(**session_params)
            return {"url": checkout_session.url, "action": "redirect"}
        else:
            # CASE 3: User has an existing paid plan
            # We need to update the subscription directly.
            try:
                stripe_sub = stripe.Subscription.retrieve(
                    active_subscription.stripe_subscription_id
                )
                current_item_id = stripe_sub["items"]["data"][0].id

                updated_stripe_sub = stripe.Subscription.modify(
                    active_subscription.stripe_subscription_id,
                    items=[{"id": current_item_id, "price": new_price_id}],
                    proration_behavior="create_prorations",
                )

                # Synchronously update our local database
                active_subscription.plan_id = updated_stripe_sub.plan.product
                active_subscription.status = updated_stripe_sub.status
                active_subscription.current_period_start = datetime.fromtimestamp(
                    updated_stripe_sub.items().mapping["items"]["data"][0][
                        "current_period_start"
                    ]
                )
                active_subscription.current_period_end = datetime.fromtimestamp(
                    updated_stripe_sub.items().mapping["items"]["data"][0][
                        "current_period_end"
                    ]
                )
                self.db.commit()

                return {"status": "success", "action": "refresh"}
            except Exception as e:
                self.db.rollback()
                print(f"Error updating subscription for account {account_id}: {e}")
                raise Exception("Could not update subscription.")

    def create_portal_session(self, account_id: str, return_url: str) -> str:
        """Creates a Stripe Customer Portal session."""
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account or not account.stripe_customer_id:
            raise ValueError("Stripe customer not found for this account.")

        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=account.stripe_customer_id,
                return_url=return_url,
            )
            return portal_session.url
        except Exception as e:
            print(f"Error creating portal session for account {account_id}: {e}")
            raise Exception("Could not create customer portal session.")

    def handle_webhook(self, payload: bytes, sig_header: str) -> None:
        """Handles incoming Stripe webhooks."""
        event = None
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=settings.stripe_webhook_secret,
            )
        except ValueError as e:
            # Invalid payload
            raise HTTPException(status_code=400, detail="Invalid payload") from e
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            raise HTTPException(status_code=400, detail="Invalid signature") from e

        # Handle the event
        if event.type == "checkout.session.completed":
            self._handle_checkout_session_completed(event.data.object.id)
        elif event.type == "invoice.paid":
            self._handle_invoice_paid(event.data.object)
        elif event.type == "customer.subscription.updated":
            self._handle_subscription_updated(event.data.object)
        elif event.type == "customer.subscription.deleted":
            self._handle_subscription_deleted(event.data.object)
        else:
            print(f"Unhandled event type {event.type}")

    def _handle_checkout_session_completed(self, session_id: str) -> Optional[Account]:
        """
        Handles the checkout.session.completed event idempotently.
        Returns the user account associated with the session.
        """
        session = stripe.checkout.Session.retrieve(
            session_id, expand=["customer", "subscription"]
        )
        if not session.subscription:
            print(f"ERROR: Checkout session {session.id} has no subscription.")
            return None

        stripe_subscription_id = session.subscription.id

        # Idempotency Check: If subscription already exists, just return the account
        existing_subscription = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
            .first()
        )
        if existing_subscription:
            return existing_subscription.account

        # 1. Identify the user account
        account = None
        if session.client_reference_id:
            account = (
                self.db.query(Account)
                .filter(Account.id == session.client_reference_id)
                .first()
            )
        elif session.customer and session.customer.email:
            account = (
                self.db.query(Account)
                .filter(Account.email == session.customer.email)
                .first()
            )

        # 2. Conflict Detection for existing users
        if account and account.get_active_subscription(self.db):
            print(f"CONFLICT: Account {account.id} already has an active subscription.")
            # TODO: Send admin alert
            return account  # Return account for context, but don't create new sub

        # 3. Create new account if necessary
        customer_email = session.customer.email
        if not account and customer_email:
            username = self._generate_unique_username(customer_email)
            account = Account(
                username=username,
                email=customer_email,
                full_name=session.customer.name,
                stripe_customer_id=session.customer.id,
                hashed_password="NEEDS_RESET",
            )
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
        elif account and not account.stripe_customer_id:
            account.stripe_customer_id = session.customer.id
            self.db.commit()

        if not account:
            print(
                f"ERROR: Could not find or create an account for session {session.id}"
            )
            return None

        # 4. Create the new subscription record
        stripe_sub = session.subscription
        subscription_data = SubscriptionCreate(
            account_id=account.id,
            plan_id=stripe_sub.plan.product,
            status=stripe_sub.status,
            current_period_start=datetime.fromtimestamp(
                stripe_sub.items().mapping["items"]["data"][0]["current_period_start"]
            ),
            current_period_end=datetime.fromtimestamp(
                stripe_sub.items().mapping["items"]["data"][0]["current_period_end"]
            ),
            stripe_subscription_id=stripe_sub.id,
        )
        self.create_subscription(subscription_data)
        print(f"Created new subscription {stripe_sub.id} for account {account.id}")
        return account

    def _handle_invoice_paid(self, invoice) -> None:
        """Handles the invoice.paid event."""
        stripe_subscription_id = invoice.subscription
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
            .first()
        )

        if subscription:
            # Retrieve the full subscription object from Stripe to get the latest period dates
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription.items().mapping["items"]["data"][0][
                    "current_period_start"
                ]
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription.items().mapping["items"]["data"][0][
                    "current_period_end"
                ]
            )
            subscription.status = "active"
            self.db.commit()
            print(f"Updated billing period for subscription {stripe_subscription_id}")

    def _handle_subscription_updated(self, sub) -> None:
        """Handles the customer.subscription.updated event."""
        stripe_subscription_id = sub.id
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
            .first()
        )

        if subscription:
            subscription.plan_id = sub.plan.product

            # Check if the subscription is scheduled for cancellation
            if sub.cancel_at_period_end:
                subscription.status = "pending_cancellation"
            else:
                subscription.status = sub.status

            subscription.current_period_start = datetime.fromtimestamp(
                sub.items().mapping["items"]["data"][0]["current_period_start"]
            )
            subscription.current_period_end = datetime.fromtimestamp(
                sub.items().mapping["items"]["data"][0]["current_period_end"]
            )
            self.db.commit()
            print(
                f"Updated subscription {stripe_subscription_id} to status {subscription.status}"
            )

    def _handle_subscription_deleted(self, sub) -> None:
        """Handles the customer.subscription.deleted event."""
        stripe_subscription_id = sub.id
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
            .first()
        )

        if subscription:
            subscription.status = "canceled"
            self.db.commit()
            print(f"Canceled subscription {stripe_subscription_id}")

    def get_user_details_from_session(self, session_id: str) -> Optional[dict]:
        """
        Retrieves user email and username from a completed Stripe checkout session.
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id, expand=["customer"])
            if session.status != "complete":
                return None

            email = session.customer.email
            if not email:
                return None

            account = self.db.query(Account).filter(Account.email == email).first()
            if not account:
                return None

            return {"email": account.email, "username": account.username}
        except Exception as e:
            print(f"Error retrieving session details: {e}")
            return None

    def _generate_unique_username(self, email: str) -> str:
        """Generates a unique username from an email address."""
        email_prefix = email.split("@")[0]
        sanitized_prefix = "".join(e for e in email_prefix if e.isalnum())
        if not sanitized_prefix:
            sanitized_prefix = "user"

        username = sanitized_prefix
        while self.db.query(Account).filter(Account.username == username).first():
            suffix = uuid.uuid4().hex[:4]
            username = f"{sanitized_prefix}_{suffix}"
        return username

    def sync_subscription_status(self, account_id: uuid.UUID) -> None:
        """
        Fetches the latest subscription status from Stripe and updates the local DB.
        """
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.account_id == account_id)
            .order_by(Subscription.created_at.desc())
            .first()
        )

        if not subscription or not subscription.stripe_subscription_id:
            # No subscription to sync
            return

        try:
            stripe_sub = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id
            )
            self._handle_subscription_updated(stripe_sub)
        except Exception as e:
            print(f"Error syncing subscription for account {account_id}: {e}")
            # Don't raise an exception, as this is a background sync
