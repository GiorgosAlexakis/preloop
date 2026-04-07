from datetime import datetime, UTC, timedelta

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from preloop.models.models.managed_agent import ManagedAgent


def test_account_agents_filtering(
    client: TestClient,
    db_session: Session,
    test_user,
):
    # Create the agent via a token login
    token_response = client.post(
        "/api/v1/auth/runtime-sessions/token",
        json={
            "session_source_type": "claude_code",
            "session_source_id": "source1",
            "session_reference": "ref1",
            "runtime_principal_name": "claude_desktop",
        },
    )
    assert token_response.status_code == 201
    # Update last_seen_at directly
    agent = (
        db_session.query(ManagedAgent)
        .filter(ManagedAgent.session_source_id == "source1")
        .first()
    )
    agent.last_seen_at = datetime.now(UTC) - timedelta(minutes=5)
    agent.last_seen_at = agent.last_seen_at.replace(tzinfo=None)  # NAIVE (db format)
    db_session.commit()

    time_10_min_ago = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    response = client.get("/api/v1/agents", params={"last_seen_after": time_10_min_ago})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1

    time_1_min_ago = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    response = client.get("/api/v1/agents", params={"last_seen_after": time_1_min_ago})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0
