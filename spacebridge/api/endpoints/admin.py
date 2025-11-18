"""Admin API endpoints for platform management and observability."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from spacebridge.api.auth import get_current_active_user
from spacebridge.plugins.proprietary.rbac.permissions import require_permission
from spacemodels.crud import (
    crud_tracker,
)
from spacemodels.db.session import get_db_session
from spacemodels.models import (
    Account,
    Flow,
    FlowExecution,
    Team,
    Tracker,
    User,
    Event,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/admin/activity/sessions")
@require_permission("view_admin_dashboard")
async def get_active_sessions(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """Get all active WebSocket sessions with current activity.

    Uses in-memory session_manager for efficient access without N+1 queries.

    Returns:
        List of active sessions with user info and latest activity
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    from spacebridge.services.session_manager import session_manager

    # Get active sessions directly from in-memory session manager
    active_sessions = []

    for session in session_manager.sessions.values():
        # Get latest page_view activity for current path
        latest_page_view = (
            db.query(Event)
            .filter(
                Event.session_id == uuid.UUID(session.id),
                Event.event_type == "page_view",
            )
            .order_by(Event.timestamp.desc())
            .first()
        )

        session_data = {
            "session_id": session.id,
            "user_id": str(session.user_id) if session.user_id else None,
            "account_id": str(session.account_id) if session.account_id else None,
            "fingerprint": session.fingerprint,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "connected_at": session.connected_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "current_path": latest_page_view.path if latest_page_view else None,
            "is_authenticated": session.is_authenticated,
        }

        # Add user info if authenticated
        if session.user_id:
            user = db.query(User).filter(User.id == session.user_id).first()
            if user:
                session_data["user"] = {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                }

        active_sessions.append(session_data)

    return {"sessions": active_sessions, "total": len(active_sessions)}


@router.get("/admin/accounts")
@require_permission("view_admin_dashboard")
async def get_accounts(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
    search: Optional[str] = None,
    subscription_status: Optional[str] = None,
    activity_level: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Get all accounts with filtering and search.

    Args:
        search: Search by organization name or user email/username
        subscription_status: Filter by subscription status
        activity_level: Filter by activity (active_today, active_week, inactive_30d)
        limit: Maximum results to return
        offset: Pagination offset

    Returns:
        List of accounts with stats and subscription info
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(Account)

    # Search filter
    if search:
        query = query.filter(
            or_(
                Account.organization_name.ilike(f"%{search}%"),
                Account.id.in_(
                    db.query(User.account_id).filter(
                        or_(
                            User.username.ilike(f"%{search}%"),
                            User.email.ilike(f"%{search}%"),
                        )
                    )
                ),
            )
        )

    # Activity level filter
    if activity_level:
        now = datetime.now(timezone.utc)
        if activity_level == "active_today":
            query = query.filter(
                Account.id.in_(
                    db.query(Event.account_id)
                    .filter(Event.timestamp >= now - timedelta(days=1))
                    .distinct()
                )
            )
        elif activity_level == "active_week":
            query = query.filter(
                Account.id.in_(
                    db.query(Event.account_id)
                    .filter(Event.timestamp >= now - timedelta(days=7))
                    .distinct()
                )
            )
        elif activity_level == "inactive_30d":
            query = query.filter(
                ~Account.id.in_(
                    db.query(Event.account_id)
                    .filter(Event.timestamp >= now - timedelta(days=30))
                    .distinct()
                )
            )

    total_count = query.count()
    accounts = query.offset(offset).limit(limit).all()

    # Enrich accounts with stats
    enriched_accounts = []
    for account in accounts:
        account_stats = get_account_stats(account.id, db)
        # Cache last_activity_time to avoid calling it twice
        last_activity = get_last_activity_time(account.id, db)

        enriched_accounts.append(
            {
                "id": str(account.id),
                "organization_name": account.organization_name,
                "created_at": account.created_at.isoformat()
                if account.created_at
                else None,
                "primary_user": (
                    {
                        "id": str(account.primary_user_id),
                        "username": db.query(User.username)
                        .filter(User.id == account.primary_user_id)
                        .scalar(),
                        "email": db.query(User.email)
                        .filter(User.id == account.primary_user_id)
                        .scalar(),
                    }
                    if account.primary_user_id
                    else None
                ),
                "stats": account_stats,
                "active_sessions_count": get_active_sessions_count(account.id, db),
                "last_activity_at": (
                    last_activity.isoformat() if last_activity else None
                ),
            }
        )

    return {
        "accounts": enriched_accounts,
        "total": total_count,
        "offset": offset,
        "limit": limit,
    }


@router.get("/admin/accounts/{account_id}")
@require_permission("view_admin_dashboard")
async def get_account_details(
    account_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """Get detailed account information with users, teams, trackers, flows.

    Args:
        account_id: Account UUID

    Returns:
        Complete account details with related resources
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Get account resources
    users = db.query(User).filter(User.account_id == account_id).all()
    teams = db.query(Team).filter(Team.account_id == account_id).all()
    trackers = db.query(Tracker).filter(Tracker.account_id == account_id).all()
    flows = db.query(Flow).filter(Flow.account_id == account_id).all()

    # Enrich users
    users_enriched = []
    for user in users:
        user_stats = get_user_stats(user.id, db)
        users_enriched.append(
            {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "email_verified": user.email_verified,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "stats": user_stats,
            }
        )

    # Enrich trackers
    trackers_enriched = []
    for tracker in trackers:
        tracker_stats = get_tracker_stats(tracker.id, db)
        trackers_enriched.append(
            {
                "id": str(tracker.id),
                "name": tracker.name,
                "tracker_type": tracker.tracker_type.value
                if hasattr(tracker.tracker_type, "value")
                else str(tracker.tracker_type),
                "url": tracker.url,
                "is_active": tracker.is_active,
                "created_at": tracker.created_at.isoformat(),
                "stats": tracker_stats,
            }
        )

    # Enrich flows
    flows_enriched = []
    for flow in flows:
        flow_stats = get_flow_stats(flow.id, db)
        flows_enriched.append(
            {
                "id": str(flow.id),
                "name": flow.name,
                "description": flow.description,
                "is_active": flow.is_active,
                "created_at": flow.created_at.isoformat(),
                "stats": flow_stats,
            }
        )

    return {
        "account": {
            "id": str(account.id),
            "organization_name": account.organization_name,
            "created_at": account.created_at.isoformat()
            if account.created_at
            else None,
            "is_active": account.is_active,
        },
        "users": users_enriched,
        "teams": [
            {
                "id": str(team.id),
                "name": team.name,
                "description": team.description,
                "created_at": team.created_at.isoformat(),
            }
            for team in teams
        ],
        "trackers": trackers_enriched,
        "flows": flows_enriched,
        "active_sessions_count": get_active_sessions_count(account_id, db),
    }


@router.get("/admin/accounts/{account_id}/activity")
@require_permission("view_admin_dashboard")
async def get_account_activity(
    account_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
    event_types: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Get combined activity timeline for an account.

    Args:
        account_id: Account UUID
        event_types: Filter by event types
        limit: Maximum results
        offset: Pagination offset

    Returns:
        Activity timeline with user sessions and system events
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(Event).filter(Event.account_id == account_id)

    # Filter by event types
    if event_types:
        query = query.filter(Event.event_type.in_(event_types))

    total_count = query.count()
    activities = (
        query.order_by(Event.timestamp.desc()).offset(offset).limit(limit).all()
    )

    # Format activities
    formatted_activities = []
    for activity in activities:
        formatted_activities.append(
            {
                "id": str(activity.id),
                "session_id": str(activity.session_id) if activity.session_id else None,
                "user_id": str(activity.user_id) if activity.user_id else None,
                "event_type": activity.event_type,
                "timestamp": activity.timestamp.isoformat(),
                "path": activity.path,
                "action": activity.action,
                "conversion_event": activity.conversion_event,
                "event_data": activity.event_data,
            }
        )

    return {
        "activities": formatted_activities,
        "total": total_count,
        "offset": offset,
        "limit": limit,
    }


# Helper functions


def get_account_stats(account_id: UUID, db: Session) -> dict:
    """Calculate account statistics."""
    users_count = db.query(User).filter(User.account_id == account_id).count()
    teams_count = db.query(Team).filter(Team.account_id == account_id).count()
    trackers_count = db.query(Tracker).filter(Tracker.account_id == account_id).count()
    flows_count = db.query(Flow).filter(Flow.account_id == account_id).count()

    return {
        "users_count": users_count,
        "teams_count": teams_count,
        "trackers_count": trackers_count,
        "flows_count": flows_count,
    }


def get_user_stats(user_id: UUID, db: Session) -> dict:
    """Calculate user statistics."""
    # Get user's account to filter resources
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {}

    account_id = user.account_id

    # Count sessions using .count() for efficiency
    total_sessions = (
        db.query(Event)
        .filter(
            Event.user_id == user_id,
            Event.event_type == "session_start",
        )
        .count()
    )

    return {
        "total_sessions": total_sessions,
    }


def get_tracker_stats(tracker_id: UUID, db: Session) -> dict:
    """Calculate tracker statistics."""
    tracker = crud_tracker.get(db, id=tracker_id)
    if not tracker:
        return {}

    # Get projects count - projects belong to organizations, not trackers
    # Count projects in organizations that use this tracker
    from spacemodels.models import Project, Organization

    # Get organizations using this tracker
    orgs_with_tracker = (
        db.query(Organization.id).filter(Organization.tracker_id == tracker_id).all()
    )
    org_ids = [org.id for org in orgs_with_tracker]

    # Count projects in those organizations
    projects_count = (
        db.query(Project).filter(Project.organization_id.in_(org_ids)).count()
        if org_ids
        else 0
    )

    return {
        "projects_count": projects_count,
    }


def get_flow_stats(flow_id: UUID, db: Session) -> dict:
    """Calculate flow statistics."""

    # Use database aggregations for efficiency
    total_executions = (
        db.query(FlowExecution).filter(FlowExecution.flow_id == flow_id).count()
    )

    successful = (
        db.query(FlowExecution)
        .filter(FlowExecution.flow_id == flow_id, FlowExecution.status == "success")
        .count()
    )

    success_rate = (successful / total_executions * 100) if total_executions > 0 else 0

    return {
        "total_executions": total_executions,
        "successful_executions": successful,
        "success_rate": round(success_rate, 2),
    }


def get_active_sessions_count(account_id: UUID, db: Session) -> int:
    """Get count of active WebSocket sessions for an account."""
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=1)

    # Find sessions that started recently
    started_sessions = (
        db.query(Event.session_id)
        .filter(
            Event.account_id == account_id,
            Event.event_type == "session_start",
            Event.timestamp >= cutoff_time,
        )
        .distinct()
        .all()
    )

    started_session_ids = [s.session_id for s in started_sessions]

    # Find sessions that ended
    ended_sessions = (
        db.query(Event.session_id)
        .filter(
            Event.account_id == account_id,
            Event.event_type == "session_end",
            Event.session_id.in_(started_session_ids),
        )
        .distinct()
        .all()
    )

    ended_session_ids = {s.session_id for s in ended_sessions}

    # Active = started but not ended
    active_count = len([s for s in started_session_ids if s not in ended_session_ids])

    return active_count


def get_last_activity_time(account_id: UUID, db: Session) -> Optional[datetime]:
    """Get the most recent activity timestamp for an account."""
    latest_activity = (
        db.query(func.max(Event.timestamp))
        .filter(Event.account_id == account_id)
        .scalar()
    )

    return latest_activity
