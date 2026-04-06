from datetime import datetime, UTC, timedelta

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from preloop.models.models.account import Account
from preloop.models.models.managed_agent import ManagedAgent
from preloop.models.crud import crud_managed_agent


def test_account_agents_filtering(
    client: TestClient,
    db: Session,
    account: Account,
    db_scoped_user_headers: dict[str, str],
):
    crud_managed_agent.enroll_cli_agent(
        db,
        account_id=str(account.id),
        agent_kind="claude_code",
        display_name="claude_desktop",
        session_source_type="claude_code",
        session_source_id="source1",
        session_reference="ref1",
    )
    # Update last_seen_at directly
    agent = (
        db.query(ManagedAgent)
        .filter(ManagedAgent.session_source_id == "source1")
        .first()
    )
    agent.last_seen_at = datetime.now(UTC) - timedelta(minutes=5)
    agent.last_seen_at = agent.last_seen_at.replace(tzinfo=None)  # NAIVE (db format)
    db.commit()

    time_10_min_ago = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    response = client.get(
        f"/api/v1/agents?last_seen_after={time_10_min_ago}",
        headers=db_scoped_user_headers,
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1

    time_1_min_ago = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    response = client.get(
        f"/api/v1/agents?last_seen_after={time_1_min_ago}",
        headers=db_scoped_user_headers,
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0
