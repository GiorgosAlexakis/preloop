"""
Service for handling billing, subscriptions, and usage tracking.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from spacemodels.models import Plan, Subscription, MonthlyUsage
from spacemodels.schemas.plan import PlanCreate, SubscriptionCreate, MonthlyUsageCreate


class BillingService:
    """
    Service for all billing and subscription related logic.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

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
            return False  # No active subscription

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
            return False

        return subscription.plan.features.get(f"{feature}_enabled", False)
