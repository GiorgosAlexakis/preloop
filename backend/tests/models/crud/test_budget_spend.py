from datetime import datetime, timezone
from preloop.models.models.budget import BudgetPeriod
from preloop.models.crud.budget import crud_budget_spend


def test_get_spend_multi(db_session, create_account):
    """Test batch fetching of spend records using get_spend_multi."""
    # Create account using the test fixture
    account = create_account()

    # Assign an arbitrary date as the period_start in UTC
    dt = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Establish a "user" level spend limit tracking block
    crud_budget_spend.upsert_spend(
        db_session,
        account_id=account.id,
        subject_type="user",
        subject_id=None,
        model_alias="gpt-5.4",
        period=BudgetPeriod.daily,
        period_start=dt,
        spend_increment_usd=1.5,
    )

    # Establish an overall "account" level spend block
    crud_budget_spend.upsert_spend(
        db_session,
        account_id=account.id,
        subject_type="account",
        subject_id=None,
        model_alias=None,
        period=BudgetPeriod.monthly,
        period_start=dt,
        spend_increment_usd=10.0,
    )

    # Validate that returning empty buckets yields an empty dict
    assert crud_budget_spend.get_spend_multi(db_session, account.id, []) == {}

    # Define buckets to query - including one that does not exist in DB
    buckets = [
        ("user", None, "gpt-5.4", BudgetPeriod.daily, dt),
        ("account", None, None, BudgetPeriod.monthly, dt),
        ("nonexistent", None, None, BudgetPeriod.daily, dt),
    ]

    result = crud_budget_spend.get_spend_multi(db_session, account.id, buckets)

    # We expect 2 successful results to be returned
    assert len(result) == 2
    assert result[("user", None, "gpt-5.4", BudgetPeriod.daily, dt)] == 1.5
    assert result[("account", None, None, BudgetPeriod.monthly, dt)] == 10.0

    # The nonexistent entry shouldn't be mapped
    assert ("nonexistent", None, None, BudgetPeriod.daily, dt) not in result
