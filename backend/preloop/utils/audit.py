"""Lightweight audit helper for configuration-change logging.

This module provides a single ``log_config_change`` helper that endpoints
can call after any configuration mutation (create, update, delete, toggle).

The helper gracefully degrades to a no-op when the EE audit plugin is not
installed, so OSS callers never need to guard the import.
"""

import logging
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from preloop.models.models.user import User

logger = logging.getLogger(__name__)


def _get_audit_service():
    """Lazy-import the EE audit service singleton (returns None in OSS)."""
    try:
        from plugins.audit.service import get_audit_service

        return get_audit_service()
    except ImportError:
        return None


def log_config_change(
    db: Session,
    *,
    user: User,
    config_type: str,
    action: str,
    old_value: Optional[Any] = None,
    new_value: Optional[Any] = None,
    request: Optional[Request] = None,
) -> None:
    """Log a configuration change to the audit trail.

    This is a thin wrapper around ``AuditService.log_configuration_change``
    that silently skips logging when the audit plugin is absent.

    Args:
        db: Active database session.
        user: The user performing the change.
        config_type: Entity type, e.g. ``"mcp_server"``, ``"tool_rule"``.
        action: Verb, e.g. ``"created"``, ``"updated"``, ``"deleted"``.
        old_value: Serialisable previous state (optional).
        new_value: Serialisable new state (optional).
        request: FastAPI request for IP / user-agent extraction (optional).
    """
    audit_service = _get_audit_service()
    if audit_service is None:
        return

    try:
        from preloop.utils.redaction import redact_dict

        audit_service.log_configuration_change(
            db,
            account_id=user.account_id,
            user=user,
            config_type=config_type,
            action=action,
            old_value=redact_dict(old_value) if old_value is not None else None,
            new_value=redact_dict(new_value) if new_value is not None else None,
            request=request,
        )
    except Exception:
        logger.debug("Audit log_configuration_change failed", exc_info=True)
