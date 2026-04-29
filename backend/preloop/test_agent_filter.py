from preloop.models.db import SessionLocal
from preloop.models.crud.managed_agent import crud_managed_agent
from preloop.models.models.account import Account
from datetime import datetime, UTC, timedelta

db = SessionLocal()
account = db.query(Account).first()

if account:
    now = datetime.now(UTC)
    last_seen_after = now - timedelta(hours=1)

    print("Filter by last_seen_after =", last_seen_after)

    res = crud_managed_agent.list_for_account(
        db, account_id=str(account.id), last_seen_after=last_seen_after, limit=100
    )
    for row in res["items"]:
        print(
            f"Agent: {row['display_name']} - Last seen at: {row['last_seen_at']} - Type: {type(row['last_seen_at'])}"
        )
else:
    print("No account found")
