"""Admin API endpoints for platform management and observability."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from preloop_ai.api.auth import get_current_active_user
from preloop_ai.utils.permissions import require_permission
from preloop_models.crud import (
    crud_tracker,
)
from preloop_models.db.session import get_db_session
from preloop_models.models import (
    Account,
    Flow,
    FlowExecution,
    Team,
    Tracker,
    User,
    Event,
    Subscription,
)
from preloop_ai.agents.base import AgentStatus

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

    **Multi-Pod Limitation**: This endpoint only returns sessions from the current
    pod's in-memory session_manager. In multi-pod deployments, each pod maintains
    its own session registry, so this view will not show sessions connected to
    other pods. For comprehensive session monitoring across all pods, consider:
    - Querying the Event table for session_start events
    - Using a centralized session store (e.g., Redis)
    - Aggregating results from multiple pod endpoints

    Returns:
        List of active sessions with user info and latest activity
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    from preloop_ai.services.session_manager import session_manager

    # Get active sessions directly from in-memory session manager
    sessions_list = list(session_manager.sessions.values())

    if not sessions_list:
        return {"sessions": [], "total": 0}

    # Log reminder about multi-pod limitation
    logger.info(
        f"Returning {len(sessions_list)} sessions from local pod only. "
        f"In multi-pod deployments, this does not include sessions on other pods."
    )

    # Batch query: collect all session_ids and user_ids
    session_ids = [UUID(s.id) for s in sessions_list]
    user_ids = [s.user_id for s in sessions_list if s.user_id]

    # Batch query: get latest page_view for each session in one query
    # Use window function to get the latest page_view per session
    from sqlalchemy.sql import func

    subquery = (
        db.query(
            Event.session_id,
            Event.path,
            func.row_number()
            .over(partition_by=Event.session_id, order_by=Event.timestamp.desc())
            .label("row_num"),
        )
        .filter(Event.session_id.in_(session_ids), Event.event_type == "page_view")
        .subquery()
    )

    page_views_query = (
        db.query(subquery.c.session_id, subquery.c.path)
        .filter(subquery.c.row_num == 1)
        .all()
    )

    # Build lookup dict for page views
    page_view_map = {str(row.session_id): row.path for row in page_views_query}

    # Batch query: get all users in one query
    users_query = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []

    # Build lookup dict for users
    user_map = {str(user.id): user for user in users_query}

    # Build response using batched data
    active_sessions = []
    for session in sessions_list:
        session_data = {
            "session_id": session.id,
            "user_id": str(session.user_id) if session.user_id else None,
            "account_id": str(session.account_id) if session.account_id else None,
            "fingerprint": session.fingerprint,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "connected_at": session.connected_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "current_path": page_view_map.get(session.id),
            "is_authenticated": session.is_authenticated,
        }

        # Add user info if authenticated
        if session.user_id:
            user = user_map.get(str(session.user_id))
            if user:
                session_data["user"] = {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                }

        active_sessions.append(session_data)

    return {"sessions": active_sessions, "total": len(active_sessions)}


@router.get("/admin/activity/stats")
@require_permission("view_admin_dashboard")
async def get_activity_stats(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """Get system-wide activity statistics.

    Returns:
        Aggregated activity statistics across all accounts including:
        - Total accounts, users, and active sessions
        - Activity breakdown by time period
        - Most active accounts
        - Event type distribution
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")

    now = datetime.now(timezone.utc)

    # Calculate time boundaries
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    # Total accounts and users
    total_accounts = db.query(func.count(Account.id)).scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active).scalar() or 0

    # Activity by time period
    events_today = (
        db.query(func.count(Event.id)).filter(Event.timestamp >= today_start).scalar()
        or 0
    )
    events_this_week = (
        db.query(func.count(Event.id)).filter(Event.timestamp >= week_start).scalar()
        or 0
    )
    events_this_month = (
        db.query(func.count(Event.id)).filter(Event.timestamp >= month_start).scalar()
        or 0
    )

    # Unique active accounts by period
    active_accounts_today = (
        db.query(func.count(func.distinct(Event.account_id)))
        .filter(Event.timestamp >= today_start)
        .scalar()
        or 0
    )
    active_accounts_week = (
        db.query(func.count(func.distinct(Event.account_id)))
        .filter(Event.timestamp >= week_start)
        .scalar()
        or 0
    )
    active_accounts_month = (
        db.query(func.count(func.distinct(Event.account_id)))
        .filter(Event.timestamp >= month_start)
        .scalar()
        or 0
    )

    # Event type distribution (last 30 days)
    event_types = (
        db.query(Event.event_type, func.count(Event.id).label("count"))
        .filter(Event.timestamp >= month_start)
        .group_by(Event.event_type)
        .order_by(func.count(Event.id).desc())
        .limit(10)
        .all()
    )
    event_type_distribution = {event_type: count for event_type, count in event_types}

    # Most active accounts (last 30 days)
    most_active_accounts = (
        db.query(
            Event.account_id,
            Account.organization_name,
            func.count(Event.id).label("event_count"),
        )
        .join(Account, Event.account_id == Account.id)
        .filter(Event.timestamp >= month_start)
        .group_by(Event.account_id, Account.organization_name)
        .order_by(func.count(Event.id).desc())
        .limit(10)
        .all()
    )

    top_accounts = [
        {
            "account_id": str(account_id),
            "organization_name": org_name,
            "event_count": count,
        }
        for account_id, org_name, count in most_active_accounts
    ]

    # Flow execution stats (last 30 days)
    from preloop_models.models import FlowExecution

    flow_executions_total = (
        db.query(func.count(FlowExecution.id))
        .filter(FlowExecution.start_time >= month_start)
        .scalar()
        or 0
    )
    flow_executions_success = (
        db.query(func.count(FlowExecution.id))
        .filter(
            FlowExecution.start_time >= month_start,
            FlowExecution.status == AgentStatus.SUCCEEDED,
        )
        .scalar()
        or 0
    )
    flow_executions_failed = (
        db.query(func.count(FlowExecution.id))
        .filter(
            FlowExecution.start_time >= month_start,
            FlowExecution.status == AgentStatus.FAILED,
        )
        .scalar()
        or 0
    )

    return {
        "overview": {
            "total_accounts": total_accounts,
            "total_users": total_users,
            "active_users": active_users,
        },
        "activity": {
            "events_today": events_today,
            "events_this_week": events_this_week,
            "events_this_month": events_this_month,
            "active_accounts_today": active_accounts_today,
            "active_accounts_week": active_accounts_week,
            "active_accounts_month": active_accounts_month,
        },
        "event_type_distribution": event_type_distribution,
        "top_accounts": top_accounts,
        "flow_executions": {
            "total": flow_executions_total,
            "success": flow_executions_success,
            "failed": flow_executions_failed,
            "success_rate": (
                (flow_executions_success / flow_executions_total * 100)
                if flow_executions_total > 0
                else 0
            ),
        },
    }


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

    # Subscription status filter
    if subscription_status:
        query = query.join(Subscription, Account.id == Subscription.account_id).filter(
            Subscription.status == subscription_status
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

    # Batch load primary user data for all accounts at once
    account_ids = [acc.id for acc in accounts]
    primary_user_ids = [acc.primary_user_id for acc in accounts if acc.primary_user_id]

    primary_users_map = {}
    if primary_user_ids:
        primary_users = (
            db.query(User.id, User.username, User.email)
            .filter(User.id.in_(primary_user_ids))
            .all()
        )
        primary_users_map = {user.id: user for user in primary_users}

    # Batch load stats for all accounts
    from preloop_models.models import Team, Tracker, Flow

    stats_query = (
        db.query(
            Account.id.label("account_id"),
            func.count(func.distinct(User.id)).label("users_count"),
            func.count(func.distinct(Team.id)).label("teams_count"),
            func.count(func.distinct(Tracker.id)).label("trackers_count"),
            func.count(func.distinct(Flow.id)).label("flows_count"),
        )
        .select_from(Account)
        .outerjoin(User, User.account_id == Account.id)
        .outerjoin(Team, Team.account_id == Account.id)
        .outerjoin(Tracker, Tracker.account_id == Account.id)
        .outerjoin(Flow, Flow.account_id == Account.id)
        .filter(Account.id.in_(account_ids))
        .group_by(Account.id)
    )
    stats_results = stats_query.all()
    stats_map = {row.account_id: row for row in stats_results}

    # Batch load last activity times
    last_activity_query = (
        db.query(Event.account_id, func.max(Event.timestamp).label("last_activity"))
        .filter(Event.account_id.in_(account_ids))
        .group_by(Event.account_id)
    )
    last_activity_results = last_activity_query.all()
    last_activity_map = {
        row.account_id: row.last_activity for row in last_activity_results
    }

    # Batch load active session counts
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=1)

    # Get all started sessions
    started_sessions = (
        db.query(Event.account_id, Event.session_id)
        .filter(
            Event.account_id.in_(account_ids),
            Event.event_type == "session_start",
            Event.timestamp >= cutoff_time,
        )
        .distinct()
        .all()
    )

    started_by_account = {}
    session_ids_per_account = {}
    for acc_id, sess_id in started_sessions:
        started_by_account.setdefault(acc_id, []).append(sess_id)
        session_ids_per_account.setdefault(acc_id, set()).add(sess_id)

    # Get all ended sessions
    all_session_ids = {
        sess_id for sessions in session_ids_per_account.values() for sess_id in sessions
    }
    if all_session_ids:
        ended_sessions = (
            db.query(Event.account_id, Event.session_id)
            .filter(
                Event.account_id.in_(account_ids),
                Event.event_type == "session_end",
                Event.session_id.in_(all_session_ids),
            )
            .distinct()
            .all()
        )

        ended_by_account = {}
        for acc_id, sess_id in ended_sessions:
            ended_by_account.setdefault(acc_id, set()).add(sess_id)
    else:
        ended_by_account = {}

    active_sessions_map = {}
    for acc_id in account_ids:
        started = started_by_account.get(acc_id, [])
        ended = ended_by_account.get(acc_id, set())
        active_sessions_map[acc_id] = len([s for s in started if s not in ended])

    # Enrich accounts with stats
    enriched_accounts = []
    for account in accounts:
        stats_row = stats_map.get(account.id)
        account_stats = {
            "users_count": stats_row.users_count if stats_row else 0,
            "teams_count": stats_row.teams_count if stats_row else 0,
            "trackers_count": stats_row.trackers_count if stats_row else 0,
            "flows_count": stats_row.flows_count if stats_row else 0,
        }

        primary_user = None
        if account.primary_user_id and account.primary_user_id in primary_users_map:
            user_data = primary_users_map[account.primary_user_id]
            primary_user = {
                "id": str(account.primary_user_id),
                "username": user_data.username,
                "email": user_data.email,
            }

        last_activity = last_activity_map.get(account.id)
        active_sessions = active_sessions_map.get(account.id, 0)

        enriched_accounts.append(
            {
                "id": str(account.id),
                "organization_name": account.organization_name,
                "created_at": account.created_at.isoformat()
                if account.created_at
                else None,
                "primary_user": primary_user,
                "stats": account_stats,
                "active_sessions_count": active_sessions,
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
    from preloop_models.models import Project, Organization

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
        .filter(
            FlowExecution.flow_id == flow_id,
            FlowExecution.status == AgentStatus.SUCCEEDED,
        )
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
