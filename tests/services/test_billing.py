from unittest.mock import MagicMock
from spacebridge.services.billing import BillingService
from spacemodels.schemas.plan import PlanCreate, SubscriptionCreate


def test_create_plan():
    """
    Tests the create_plan method.
    """
    db_session = MagicMock()
    billing_service = BillingService(db_session)
    plan_data = PlanCreate(
        id="test",
        name="Test Plan",
        features={
            "api_calls_monthly": 100,
            "ai_calls_monthly": 100,
            "issues_ingested_monthly": 100,
            "custom_ai_models_enabled": False,
            "custom_compliance_metrics_enabled": False,
        },
    )

    result = billing_service.create_plan(plan_data)
    assert result.name == "Test Plan"


def test_create_subscription():
    """
    Tests the create_subscription method.
    """
    db_session = MagicMock()
    billing_service = BillingService(db_session)
    subscription_data = SubscriptionCreate(
        account_id="a" * 32,
        plan_id="test",
        status="active",
        current_period_start="2025-09-22T00:27:41.777Z",
        current_period_end="2025-10-22T00:27:41.777Z",
    )

    result = billing_service.create_subscription(subscription_data)
    assert str(result.account_id).replace("-", "") == "a" * 32
