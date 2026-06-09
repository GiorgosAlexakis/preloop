"""Tests for runtime session activity CRUD helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from preloop.models.crud.runtime_session_activity import (
    MAX_AGENT_CONTROL_MESSAGE_SUMMARY_LEN,
    crud_runtime_session_activity,
)
from preloop.models.models.managed_agent import ManagedAgent
from preloop.models.models.runtime_session import RuntimeSession


def test_log_agent_control_message_touches_managed_agent(
    db_session,
    create_account,
) -> None:
    """Operator control messages should refresh managed-agent presence."""
    account = create_account()
    principal_type = "openclaw"
    principal_id = "octavia-control"
    now = datetime.now(UTC)
    stale_seen_at = now - timedelta(hours=2)

    runtime_session = RuntimeSession(
        id=uuid4(),
        account_id=account.id,
        session_source_type=principal_type,
        session_source_id="workspace-1",
        session_reference="workspace-1",
        runtime_principal_type=principal_type,
        runtime_principal_id=principal_id,
        started_at=now,
        last_activity_at=stale_seen_at,
    )
    managed_agent = ManagedAgent(
        id=uuid4(),
        account_id=account.id,
        runtime_session_id=None,
        agent_kind=principal_type,
        session_source_type=principal_type,
        session_source_id=principal_id,
        display_name="Octavia",
        enrolled_via="runtime_session_token",
        lifecycle_state="active",
        lifecycle_updated_at=now,
        last_seen_at=stale_seen_at,
    )
    db_session.add_all([runtime_session, managed_agent])
    db_session.commit()

    activity_timestamp = now + timedelta(minutes=5)
    crud_runtime_session_activity.log_agent_control_message(
        db_session,
        account_id=account.id,
        runtime_session_id=runtime_session.id,
        message="pause current task",
        status="sent",
        timestamp=activity_timestamp,
    )

    db_session.refresh(runtime_session)
    db_session.refresh(managed_agent)

    assert runtime_session.last_activity_at.replace(tzinfo=UTC) == activity_timestamp
    assert managed_agent.runtime_session_id == runtime_session.id
    assert managed_agent.last_seen_at.replace(tzinfo=UTC) == activity_timestamp


def test_log_agent_control_message_truncates_long_summary() -> None:
    """Audit summaries should cap oversized operator message text."""
    long_message = "x" * (MAX_AGENT_CONTROL_MESSAGE_SUMMARY_LEN + 50)
    truncated = long_message[:MAX_AGENT_CONTROL_MESSAGE_SUMMARY_LEN]
    assert len(truncated) == MAX_AGENT_CONTROL_MESSAGE_SUMMARY_LEN
