"""Service for managing approval requests and webhook posting."""

import asyncio
import concurrent.futures
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set
from urllib.parse import urljoin

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from preloop.models.models import ApprovalRequest, ApprovalPolicy
from preloop.models.schemas.approval_request import (
    ApprovalRequestUpdate,
)
from preloop.models.crud.approval_request import (
    get_approval_request_async,
    get_approval_request_for_update_async,
)
from preloop.sync.services.event_bus import get_task_publisher
from preloop.services.ai_approval_service import get_ai_approval_service

logger = logging.getLogger(__name__)


def _get_audit_service():
    """Get the audit service instance (lazy import to avoid circular deps)."""
    try:
        from plugins.audit.service import get_audit_service

        return get_audit_service()
    except ImportError:
        logger.debug("Audit service not available")
        return None


def _get_db_factory():
    """Get a database session factory for async audit logging."""
    try:
        from preloop.models.db.session import get_db_session

        return lambda: next(get_db_session())
    except ImportError:
        return None


def _log_approval_lifecycle_async(
    account_id: str,
    approval_id: uuid.UUID,
    event: str,
    tool_name: Optional[str] = None,
    approver_id: Optional[uuid.UUID] = None,
    reason: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> None:
    """Log an approval lifecycle event asynchronously (fire-and-forget).

    This helper function wraps the audit service call to log approval lifecycle
    events without blocking the main execution flow.

    Args:
        account_id: Account ID
        approval_id: Approval request ID
        event: Lifecycle event ('created', 'approved', 'denied', 'expired', 'escalated')
        tool_name: Name of the tool (if available)
        approver_id: ID of the user who approved/denied
        reason: Reason or comment for the decision
        execution_id: Flow execution ID (if applicable)
    """
    try:
        audit_service = _get_audit_service()
        if not audit_service:
            return

        db_factory = _get_db_factory()
        if not db_factory:
            return

        # Convert execution_id to UUID if it's a string
        exec_id = None
        if execution_id:
            try:
                exec_id = uuid.UUID(execution_id)
            except (ValueError, TypeError):
                pass

        audit_service.log_approval_lifecycle_async(
            db_factory=db_factory,
            account_id=account_id,
            approval_id=approval_id,
            event=event,
            tool_name=tool_name,
            approver_id=approver_id,
            reason=reason,
            execution_id=exec_id,
        )
    except Exception as e:
        logger.debug(f"Failed to log approval lifecycle to audit: {e}")


# Thread pool for running sync database operations
_sync_db_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


class ApprovalService:
    """Service for handling approval requests."""

    def __init__(self, db: AsyncSession, base_url: str):
        """Initialize approval service.

        Args:
            db: Database session
            base_url: Base URL for generating approval links
        """
        self.db = db
        self.base_url = base_url

    async def _broadcast_approval_update(
        self,
        approval_request: ApprovalRequest,
        event_type: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ):
        """Broadcast approval request update via NATS/WebSocket.

        Args:
            approval_request: The approval request
            event_type: Type of event (created, approved, declined, expired, vote_received)
            extra_data: Optional additional data to include in the broadcast
        """
        try:
            task_publisher = await get_task_publisher()
            if not task_publisher or not task_publisher.nc:
                logger.warning("NATS not available for broadcasting approval update")
                return

            # Prepare update message
            update_data = {
                "type": f"approval_{event_type}",
                "approval_request_id": str(approval_request.id),
                "account_id": str(approval_request.account_id),
                "execution_id": approval_request.execution_id,
                "tool_name": approval_request.tool_name,
                "status": approval_request.status,
                "requested_at": approval_request.requested_at.isoformat(),
                "resolved_at": (
                    approval_request.resolved_at.isoformat()
                    if approval_request.resolved_at
                    else None
                ),
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Include extra data if provided (for quorum progress, etc.)
            if extra_data:
                update_data.update(extra_data)

            # Publish to NATS subject for approval updates
            subject = "approval-updates"
            await task_publisher.nc.publish(subject, json.dumps(update_data).encode())

            logger.info(
                f"Broadcasted approval {event_type} for request {approval_request.id}"
            )

        except Exception as e:
            logger.error(f"Failed to broadcast approval update: {e}", exc_info=True)

    async def create_approval_request(
        self,
        account_id: str,
        tool_configuration_id: uuid.UUID,
        approval_policy_id: uuid.UUID,
        tool_name: str,
        tool_args: Dict[str, Any],
        agent_reasoning: Optional[str] = None,
        execution_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> ApprovalRequest:
        """Create a new approval request.

        Args:
            account_id: The account creating the request
            tool_configuration_id: Tool configuration ID
            approval_policy_id: Approval policy ID
            tool_name: Name of the tool being executed
            tool_args: Arguments passed to the tool
            agent_reasoning: Agent's reasoning for the tool call
            execution_id: Flow execution ID (if applicable)
            timeout_seconds: How long to wait for approval (default: 5 minutes)

        Returns:
            Created approval request
        """
        # Calculate expiration time
        timeout = timeout_seconds or 300  # Default: 5 minutes
        expires_at = datetime.utcnow() + timedelta(seconds=timeout)

        # Create approval request
        approval_request = ApprovalRequest(
            id=uuid.uuid4(),
            account_id=account_id,
            tool_configuration_id=tool_configuration_id,
            approval_policy_id=approval_policy_id,
            execution_id=execution_id,
            tool_name=tool_name,
            tool_args=tool_args,
            agent_reasoning=agent_reasoning,
            status="pending",
            requested_at=datetime.utcnow(),
            expires_at=expires_at,
        )

        self.db.add(approval_request)
        await self.db.commit()
        await self.db.refresh(approval_request)

        # Broadcast creation event
        await self._broadcast_approval_update(approval_request, "created")

        # Log to audit trail (fire-and-forget)
        _log_approval_lifecycle_async(
            account_id=account_id,
            approval_id=approval_request.id,
            event="created",
            tool_name=tool_name,
            execution_id=execution_id,
        )

        # Note: Notifications are sent via send_notifications() which is called
        # by create_and_notify(). Do NOT send notifications here to avoid duplicates.

        return approval_request

    async def get_approval_request(
        self, request_id: uuid.UUID
    ) -> Optional[ApprovalRequest]:
        """Get an approval request by ID.

        Args:
            request_id: Approval request ID

        Returns:
            Approval request or None if not found
        """
        return await get_approval_request_async(self.db, request_id=request_id)

    async def get_approval_request_for_update(
        self, request_id: uuid.UUID
    ) -> Optional[ApprovalRequest]:
        """Get an approval request by ID with row-level locking.

        Uses SELECT ... FOR UPDATE to prevent concurrent modifications.
        This should be used when updating the responses field for voting
        to avoid lost updates from concurrent votes.

        Args:
            request_id: Approval request ID

        Returns:
            Approval request or None if not found
        """
        return await get_approval_request_for_update_async(
            self.db, request_id=request_id
        )

    async def update_approval_request(
        self, request_id: uuid.UUID, update: ApprovalRequestUpdate
    ) -> Optional[ApprovalRequest]:
        """Update an approval request.

        Args:
            request_id: Approval request ID
            update: Update data

        Returns:
            Updated approval request or None if not found
        """
        approval_request = await self.get_approval_request(request_id)
        if not approval_request:
            return None

        # Update fields
        for field, value in update.model_dump(exclude_unset=True).items():
            setattr(approval_request, field, value)

        await self.db.commit()
        await self.db.refresh(approval_request)

        return approval_request

    async def approve_request(
        self,
        request_id: uuid.UUID,
        comment: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[ApprovalRequest]:
        """Approve an approval request.

        If quorum (approvals_required > 1) is configured, this records an approval vote
        and only resolves the request when quorum is met.

        Uses row-level locking (SELECT ... FOR UPDATE) to prevent concurrent
        vote updates from overwriting each other.

        Args:
            request_id: Approval request ID
            comment: Optional comment from approver
            user_id: ID of the user approving (for quorum tracking)

        Returns:
            Updated approval request or None if not found
        """
        # Get approval request with row-level lock to prevent concurrent vote updates
        approval_request = await self.get_approval_request_for_update(request_id)
        if not approval_request:
            return None

        # Get the approval policy to check quorum requirements
        approval_policy = approval_request.approval_policy
        approvals_required = (
            approval_policy.approvals_required if approval_policy else 1
        )

        # Record this vote
        responses = list(approval_request.responses or [])

        # Handle the vote based on whether we have user_id
        if user_id:
            user_id_str = str(user_id)
            already_voted = any(r.get("user_id") == user_id_str for r in responses)
            if already_voted:
                logger.warning(f"User {user_id} already voted on request {request_id}")
                return approval_request

            # Add the vote with user tracking
            responses.append(
                {
                    "user_id": user_id_str,
                    "decision": "approved",
                    "comment": comment,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        else:
            # No user_id (e.g., public token-based approval)
            # For quorum=1, resolve immediately.
            if approvals_required == 1:
                # Immediate resolution for single-approval policies
                update = ApprovalRequestUpdate(
                    status="approved",
                    approver_comment=comment,
                    resolved_at=datetime.utcnow(),
                )
                updated_request = await self.update_approval_request(request_id, update)
                if updated_request:
                    await self._broadcast_approval_update(updated_request, "approved")
                return updated_request
            else:
                # For quorum > 1 without user_id, only allow ONE anonymous vote per request
                # to prevent a single actor from satisfying quorum by voting multiple times.
                # Check for ANY anonymous vote (approve OR decline) to prevent double-voting.
                anonymous_already_voted = any(
                    r.get("user_id") == "anonymous" for r in responses
                )
                if anonymous_already_voted:
                    logger.warning(
                        f"Duplicate anonymous vote attempt for request {request_id}. "
                        "Anonymous user already voted. Use authenticated endpoints for additional votes."
                    )
                    return approval_request

                # Add the single allowed anonymous vote
                responses.append(
                    {
                        "user_id": "anonymous",
                        "decision": "approved",
                        "comment": comment,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                logger.warning(
                    f"Anonymous approval for request {request_id} with quorum={approvals_required}. "
                    "Additional votes require authenticated endpoints."
                )

        # Count approvals
        approval_count = sum(1 for r in responses if r.get("decision") == "approved")

        # Check if quorum is met
        if approval_count >= approvals_required:
            # Quorum met - resolve as approved
            update = ApprovalRequestUpdate(
                status="approved",
                approver_comment=comment,
                resolved_at=datetime.utcnow(),
            )
            # Update responses in the database
            approval_request.responses = responses
            await self.db.commit()

            updated_request = await self.update_approval_request(request_id, update)
            if updated_request:
                await self._broadcast_approval_update(updated_request, "approved")
            return updated_request
        else:
            # Quorum not met yet - just record the vote and broadcast progress
            approval_request.responses = responses
            await self.db.commit()
            await self.db.refresh(approval_request)

            # Broadcast vote received event (not full approval yet)
            await self._broadcast_approval_update(
                approval_request,
                "vote_received",
                extra_data={
                    "approval_count": approval_count,
                    "approvals_required": approvals_required,
                },
            )

            logger.info(
                f"Approval vote recorded for {request_id}: {approval_count}/{approvals_required}"
            )
            return approval_request

    async def decline_request(
        self,
        request_id: uuid.UUID,
        comment: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[ApprovalRequest]:
        """Decline an approval request.

        With quorum, a decline is recorded as a vote. The request is declined when:
        - All potential approvers have voted and quorum cannot be reached, OR
        - The number of declines makes it impossible to reach quorum

        Uses row-level locking (SELECT ... FOR UPDATE) to prevent concurrent
        vote updates from overwriting each other.

        Args:
            request_id: Approval request ID
            comment: Optional comment from approver
            user_id: ID of the user declining (for quorum tracking)

        Returns:
            Updated approval request or None if not found
        """
        # Get approval request with row-level lock to prevent concurrent vote updates
        approval_request = await self.get_approval_request_for_update(request_id)
        if not approval_request:
            return None

        # Get the approval policy to check quorum requirements
        approval_policy = approval_request.approval_policy
        approvals_required = (
            approval_policy.approvals_required if approval_policy else 1
        )

        # Record this vote
        responses = list(approval_request.responses or [])

        # Handle the vote based on whether we have user_id
        if user_id:
            user_id_str = str(user_id)
            already_voted = any(r.get("user_id") == user_id_str for r in responses)
            if already_voted:
                logger.warning(f"User {user_id} already voted on request {request_id}")
                return approval_request

            # Add the vote with user tracking
            responses.append(
                {
                    "user_id": user_id_str,
                    "decision": "declined",
                    "comment": comment,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        else:
            # No user_id (e.g., public token-based decline)
            # For quorum=1, resolve immediately.
            if approvals_required == 1:
                # Immediate resolution for single-approval policies
                update = ApprovalRequestUpdate(
                    status="declined",
                    approver_comment=comment,
                    resolved_at=datetime.utcnow(),
                )
                updated_request = await self.update_approval_request(request_id, update)
                if updated_request:
                    await self._broadcast_approval_update(updated_request, "declined")
                return updated_request
            else:
                # For quorum > 1 without user_id, only allow ONE anonymous vote per request
                # to prevent a single actor from forcing a decline by voting multiple times.
                # Check for ANY anonymous vote (approve OR decline) to prevent double-voting.
                anonymous_already_voted = any(
                    r.get("user_id") == "anonymous" for r in responses
                )
                if anonymous_already_voted:
                    logger.warning(
                        f"Duplicate anonymous vote attempt for request {request_id}. "
                        "Anonymous user already voted. Use authenticated endpoints for additional votes."
                    )
                    return approval_request

                # Add the single allowed anonymous vote
                responses.append(
                    {
                        "user_id": "anonymous",
                        "decision": "declined",
                        "comment": comment,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                logger.warning(
                    f"Anonymous decline for request {request_id} with quorum={approvals_required}. "
                    "Additional votes require authenticated endpoints."
                )

        # Count votes
        approval_count = sum(1 for r in responses if r.get("decision") == "approved")
        decline_count = sum(1 for r in responses if r.get("decision") == "declined")

        # Get actual total approvers count (only reliable for direct user approvers)
        total_approvers, is_exact = self._count_total_approvers(approval_policy)

        # Determine if we should resolve as declined
        should_decline = False
        remaining_voters = 0

        if is_exact:
            remaining_voters = total_approvers - len(responses)
            # Check if quorum is still possible
            can_reach_quorum = (approval_count + remaining_voters) >= approvals_required
            all_voted = len(responses) >= total_approvers
            should_decline = not can_reach_quorum or (
                all_voted and approval_count < approvals_required
            )
        else:
            # When we can't get an exact count (teams involved), use simpler rules:
            # 1. If approvals_required == 1, any decline resolves immediately
            # 2. For higher quorum, decline if decline_count >= approvals_required
            #    (meaning enough people have explicitly declined to block approval)
            if approvals_required == 1:
                should_decline = decline_count >= 1
            else:
                # If as many people have declined as required for approval,
                # it's a clear signal the request should be declined
                should_decline = decline_count >= approvals_required

        if should_decline:
            # Cannot reach quorum - resolve as declined
            update = ApprovalRequestUpdate(
                status="declined",
                approver_comment=comment,
                resolved_at=datetime.utcnow(),
            )
            # Update responses in the database
            approval_request.responses = responses
            await self.db.commit()

            updated_request = await self.update_approval_request(request_id, update)
            if updated_request:
                await self._broadcast_approval_update(updated_request, "declined")
            return updated_request
        else:
            # Still possible to reach quorum - just record the vote
            approval_request.responses = responses
            await self.db.commit()
            await self.db.refresh(approval_request)

            # Broadcast vote received event
            extra_data = {"decline_count": decline_count}
            if is_exact:
                extra_data["remaining_voters"] = remaining_voters

            await self._broadcast_approval_update(
                approval_request,
                "vote_received",
                extra_data=extra_data,
            )

            if is_exact:
                logger.info(
                    f"Decline vote recorded for {request_id}: {decline_count} declines, "
                    f"{remaining_voters} remaining voters"
                )
            else:
                logger.info(
                    f"Decline vote recorded for {request_id}: {decline_count} declines "
                    "(team approvers involved, exact count unknown)"
                )
            return approval_request

    def _count_total_approvers(
        self, approval_policy: ApprovalPolicy
    ) -> tuple[int, bool]:
        """Count total potential approvers for a policy.

        Args:
            approval_policy: The approval policy

        Returns:
            Tuple of (count, is_exact):
            - count: Total number of potential approvers
            - is_exact: True if count is exact (only direct user approvers),
                       False if teams are involved (count is unreliable)
        """
        if not approval_policy:
            return (1, True)

        total = 0
        is_exact = True

        # Count direct user approvers (exact count)
        if approval_policy.approver_user_ids:
            total += len(approval_policy.approver_user_ids)

        # Team approvers make the count inexact
        # We can't reliably count team members without querying the database
        if (
            approval_policy.approver_team_ids
            and len(approval_policy.approver_team_ids) > 0
        ):
            is_exact = False
            # Don't add an estimate - the count is unreliable for decision-making

        return (max(total, 1), is_exact)

    async def _auto_approve_request(
        self,
        request_id: uuid.UUID,
        reason: str,
        decided_by_ai: bool = True,
        ai_model: Optional[str] = None,
        ai_confidence: Optional[float] = None,
    ) -> Optional[ApprovalRequest]:
        """Auto-approve an approval request (typically by AI).

        Args:
            request_id: Approval request ID
            reason: Reason for the approval
            decided_by_ai: Whether this was decided by AI
            ai_model: The AI model that made the decision
            ai_confidence: The confidence score of the AI decision

        Returns:
            Updated approval request or None if not found
        """
        update = ApprovalRequestUpdate(
            status="approved",
            approver_comment=reason,
            resolved_at=datetime.utcnow(),
            decided_by_ai=decided_by_ai,
            ai_model=ai_model,
            ai_confidence=ai_confidence,
            ai_reasoning=reason,
        )
        updated_request = await self.update_approval_request(request_id, update)

        if updated_request:
            await self._broadcast_approval_update(updated_request, "approved")

            # Log to audit trail (fire-and-forget)
            _log_approval_lifecycle_async(
                account_id=str(updated_request.account_id),
                approval_id=updated_request.id,
                event="approved",
                tool_name=updated_request.tool_name,
                approver_id=None,  # AI decision, no human approver
                reason=f"[AI] {reason}" if decided_by_ai else reason,
                execution_id=updated_request.execution_id,
            )

        return updated_request

    async def _auto_deny_request(
        self,
        request_id: uuid.UUID,
        reason: str,
        decided_by_ai: bool = True,
        ai_model: Optional[str] = None,
        ai_confidence: Optional[float] = None,
    ) -> Optional[ApprovalRequest]:
        """Auto-deny an approval request (typically by AI).

        Args:
            request_id: Approval request ID
            reason: Reason for the denial
            decided_by_ai: Whether this was decided by AI
            ai_model: The AI model that made the decision
            ai_confidence: The confidence score of the AI decision

        Returns:
            Updated approval request or None if not found
        """
        update = ApprovalRequestUpdate(
            status="declined",
            approver_comment=reason,
            resolved_at=datetime.utcnow(),
            decided_by_ai=decided_by_ai,
            ai_model=ai_model,
            ai_confidence=ai_confidence,
            ai_reasoning=reason,
        )
        updated_request = await self.update_approval_request(request_id, update)

        if updated_request:
            await self._broadcast_approval_update(updated_request, "declined")

            # Log to audit trail (fire-and-forget)
            _log_approval_lifecycle_async(
                account_id=str(updated_request.account_id),
                approval_id=updated_request.id,
                event="denied",
                tool_name=updated_request.tool_name,
                approver_id=None,  # AI decision, no human approver
                reason=f"[AI] {reason}" if decided_by_ai else reason,
                execution_id=updated_request.execution_id,
            )

        return updated_request

    async def post_webhook_notification(
        self, approval_request: ApprovalRequest, approval_policy: ApprovalPolicy
    ) -> bool:
        """Post webhook notification for approval request.

        Args:
            approval_request: The approval request
            approval_policy: The approval policy with webhook config

        Returns:
            True if successful, False otherwise
        """
        # Get webhook URL from policy
        webhook_url = None
        if approval_policy.approval_config:
            webhook_url = approval_policy.approval_config.get("webhook_url")

        if not webhook_url:
            error_msg = "No webhook URL configured in approval policy"
            await self.update_approval_request(
                approval_request.id,
                ApprovalRequestUpdate(webhook_error=error_msg),
            )
            return False

        # Generate public approval links with token (no authentication required)
        token = approval_request.approval_token
        # All links go to the same approval page - user decides there
        approve_url = urljoin(
            self.base_url, f"/approval/{approval_request.id}?token={token}"
        )
        decline_url = urljoin(
            self.base_url, f"/approval/{approval_request.id}?token={token}"
        )
        view_url = urljoin(
            self.base_url, f"/approval/{approval_request.id}?token={token}"
        )

        # Format tool arguments for display
        tool_args_formatted = json.dumps(approval_request.tool_args, indent=2)

        # Create message based on approval type
        if approval_policy.approval_type in ["slack", "mattermost"]:
            # Build message text with all details
            message_text = f"⚠️ **Approval Required: {approval_request.tool_name}**\n\n"
            message_text += f"**Tool:** `{approval_request.tool_name}`\n"
            message_text += f"**Status:** {approval_request.status.upper()}\n\n"

            if approval_request.agent_reasoning:
                message_text += (
                    f"**Agent Reasoning:**\n{approval_request.agent_reasoning}\n\n"
                )

            message_text += f"**Arguments:**\n```json\n{tool_args_formatted}\n```\n\n"
            message_text += "**Actions:**\n"
            message_text += f"• [✅ Approve]({approve_url})\n"
            message_text += f"• [❌ Decline]({decline_url})\n"
            message_text += f"• [👁️ View Details]({view_url})\n"

            # Mattermost/Slack compatible message with attachments
            message = {
                "text": message_text,
                "attachments": [
                    {
                        "color": "#f2c744",
                        "fallback": f"Approval Required: {approval_request.tool_name}",
                        "title": f"⚠️ Approval Required: {approval_request.tool_name}",
                        "title_link": view_url,
                        "fields": [
                            {
                                "title": "Tool",
                                "value": approval_request.tool_name,
                                "short": True,
                            },
                            {
                                "title": "Status",
                                "value": approval_request.status.upper(),
                                "short": True,
                            },
                        ],
                        "text": f"**Arguments:**\n```json\n{tool_args_formatted}\n```",
                        "actions": [
                            {
                                "type": "button",
                                "text": "✅ Approve",
                                "url": approve_url,
                                "style": "primary",
                            },
                            {
                                "type": "button",
                                "text": "❌ Decline",
                                "url": decline_url,
                                "style": "danger",
                            },
                            {
                                "type": "button",
                                "text": "👁️ View Details",
                                "url": view_url,
                            },
                        ],
                    }
                ],
            }

            # Add reasoning field if available
            if approval_request.agent_reasoning:
                message["attachments"][0]["fields"].insert(
                    0,
                    {
                        "title": "Agent Reasoning",
                        "value": approval_request.agent_reasoning,
                        "short": False,
                    },
                )
        else:
            # Generic webhook message
            message = {
                "type": "approval_request",
                "request_id": str(approval_request.id),
                "tool_name": approval_request.tool_name,
                "tool_args": approval_request.tool_args,
                "agent_reasoning": approval_request.agent_reasoning,
                "status": approval_request.status,
                "requested_at": approval_request.requested_at.isoformat(),
                "expires_at": (
                    approval_request.expires_at.isoformat()
                    if approval_request.expires_at
                    else None
                ),
                "actions": {
                    "approve": approve_url,
                    "decline": decline_url,
                    "view": view_url,
                },
            }

        # Post to webhook
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook_url,
                    json=message,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

            # Mark as posted
            await self.update_approval_request(
                approval_request.id,
                ApprovalRequestUpdate(webhook_posted_at=datetime.utcnow()),
            )
            return True

        except Exception as e:
            error_msg = f"Failed to post webhook: {str(e)}"
            await self.update_approval_request(
                approval_request.id,
                ApprovalRequestUpdate(webhook_error=error_msg),
            )
            return False

    async def create_and_notify(
        self,
        account_id: str,
        tool_configuration_id: uuid.UUID,
        approval_policy: ApprovalPolicy,
        tool_name: str,
        tool_args: Dict[str, Any],
        agent_reasoning: Optional[str] = None,
        execution_id: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> ApprovalRequest:
        """Create approval request and send notifications through configured channels.

        For AI-driven approval policies, immediately evaluates the request using AI
        and auto-approves/denies based on the result and confidence threshold.

        Args:
            account_id: The account creating the request
            tool_configuration_id: Tool configuration ID
            approval_policy: The approval policy to use
            tool_name: Name of the tool being executed
            tool_args: Arguments passed to the tool
            agent_reasoning: Agent's reasoning for the tool call
            execution_id: Flow execution ID (if applicable)
            user_id: ID of the user who initiated the tool call

        Returns:
            Created approval request (may be already resolved if AI-driven)
        """
        # Create approval request first
        approval_request = await self.create_approval_request(
            account_id=account_id,
            tool_configuration_id=tool_configuration_id,
            approval_policy_id=approval_policy.id,
            tool_name=tool_name,
            tool_args=tool_args,
            agent_reasoning=agent_reasoning,
            execution_id=execution_id,
            timeout_seconds=approval_policy.timeout_seconds,
        )

        # Check if this is an AI-driven approval policy
        if approval_policy.approval_mode == "ai_driven":
            # Evaluate using AI
            logger.info(
                f"Evaluating approval request {approval_request.id} using AI "
                f"(policy: {approval_policy.name})"
            )

            ai_service = get_ai_approval_service()
            ai_result = await ai_service.evaluate(
                tool_name=tool_name,
                tool_args=tool_args,
                policy=approval_policy,
                context={
                    "execution_id": str(execution_id) if execution_id else None,
                    "user_id": str(user_id) if user_id else None,
                    "account_id": account_id,
                    "agent_reasoning": agent_reasoning,
                },
            )

            logger.info(
                f"AI evaluation for {approval_request.id}: "
                f"decision={ai_result.decision}, confidence={ai_result.confidence:.2f}"
            )

            # Apply the decision based on confidence threshold
            if ai_result.confidence >= approval_policy.ai_confidence_threshold:
                if ai_result.decision == "approve":
                    # Auto-approve the request
                    logger.info(
                        f"AI auto-approving request {approval_request.id} "
                        f"(confidence: {ai_result.confidence:.2f})"
                    )
                    return await self._auto_approve_request(
                        request_id=approval_request.id,
                        reason=ai_result.reasoning,
                        decided_by_ai=True,
                        ai_model=ai_result.model_used,
                        ai_confidence=ai_result.confidence,
                    )
                elif ai_result.decision == "deny":
                    # Auto-deny the request
                    logger.info(
                        f"AI auto-denying request {approval_request.id} "
                        f"(confidence: {ai_result.confidence:.2f})"
                    )
                    return await self._auto_deny_request(
                        request_id=approval_request.id,
                        reason=ai_result.reasoning,
                        decided_by_ai=True,
                        ai_model=ai_result.model_used,
                        ai_confidence=ai_result.confidence,
                    )

            # If uncertain or low confidence, apply fallback behavior
            logger.info(
                f"AI uncertain or low confidence ({ai_result.confidence:.2f} < "
                f"{approval_policy.ai_confidence_threshold}), "
                f"applying fallback: {approval_policy.ai_fallback_behavior}"
            )

            if approval_policy.ai_fallback_behavior == "approve":
                return await self._auto_approve_request(
                    request_id=approval_request.id,
                    reason=f"Fallback approval (AI uncertain): {ai_result.reasoning}",
                    decided_by_ai=True,
                    ai_model=ai_result.model_used,
                    ai_confidence=ai_result.confidence,
                )
            elif approval_policy.ai_fallback_behavior == "deny":
                return await self._auto_deny_request(
                    request_id=approval_request.id,
                    reason=f"Fallback denial (AI uncertain): {ai_result.reasoning}",
                    decided_by_ai=True,
                    ai_model=ai_result.model_used,
                    ai_confidence=ai_result.confidence,
                )
            else:  # escalate (default)
                # Update the request with AI info but keep it pending for human review
                await self.update_approval_request(
                    approval_request.id,
                    ApprovalRequestUpdate(
                        ai_model=ai_result.model_used,
                        ai_confidence=ai_result.confidence,
                        ai_reasoning=f"Escalated to human review: {ai_result.reasoning}",
                    ),
                )

                # If escalation_policy_id is set, we could switch to that policy
                # For now, just send notifications for human review
                if approval_policy.escalation_policy_id:
                    logger.info(
                        f"Escalation policy configured: {approval_policy.escalation_policy_id} "
                        f"(using current policy for notifications)"
                    )

                # Refresh the approval request to get updated fields
                approval_request = await self.get_approval_request(approval_request.id)

                # Send notifications for human review
                await self.send_notifications(approval_request, approval_policy)

                return approval_request

        # Standard (human) approval - send notifications
        await self.send_notifications(approval_request, approval_policy)

        return approval_request

    async def send_notifications(
        self,
        approval_request: ApprovalRequest,
        approval_policy: ApprovalPolicy,
    ) -> Dict[str, Any]:
        """Send notifications for an approval request based on user preferences.

        Notification channels are determined by each user's notification preferences,
        not by the policy. Each approver will be notified via their preferred channels:
        - Email if they have enable_email=True
        - Push notification if they have enable_mobile_push=True and registered devices

        For webhook-based policies (slack, mattermost, webhook), those are sent
        as configured in the policy since they're not per-user.

        Args:
            approval_request: The approval request to notify about
            approval_policy: The approval policy with approver configuration

        Returns:
            Dict with results per notification channel
        """
        results = {}

        # Guard against duplicate notifications - check if request is too old to be new
        # If request was created more than 30 seconds ago, skip notifications
        # (this handles cases where send_notifications is called multiple times)
        try:
            if approval_request.requested_at:
                request_age = (
                    datetime.utcnow() - approval_request.requested_at
                ).total_seconds()
                if request_age > 30:
                    logger.warning(
                        f"Skipping notifications for approval request {approval_request.id} - "
                        f"request is {request_age:.1f}s old (likely duplicate call)"
                    )
                    return {"skipped": True, "reason": "request_too_old"}
        except (TypeError, AttributeError):
            # In tests, requested_at might be a mock - just continue
            pass

        # Send email notifications to users who have email enabled
        try:
            email_result = await self._send_email_notification(
                approval_request, approval_policy
            )
            results["email"] = email_result
        except Exception as e:
            logger.error(f"Failed to send email notifications: {str(e)}")
            results["email"] = {"success": False, "error": str(e)}

        # Send push notifications to users who have push enabled
        try:
            push_result = await self._send_push_notification(
                approval_request, approval_policy
            )
            results["mobile_push"] = push_result
        except Exception as e:
            logger.error(f"Failed to send push notifications: {str(e)}")
            results["mobile_push"] = {"success": False, "error": str(e)}

        # Handle webhook-based notifications (these are policy-level, not per-user)
        policy_channels = approval_policy.notification_channels or []
        for channel in policy_channels:
            if channel in ["slack", "mattermost", "webhook"]:
                try:
                    result = await self.post_webhook_notification(
                        approval_request, approval_policy
                    )
                    results[channel] = {"success": result}
                except Exception as e:
                    logger.error(f"Failed to send {channel} notification: {str(e)}")
                    results[channel] = {"success": False, "error": str(e)}

        return results

    async def _get_all_approver_user_ids(
        self, approval_policy: ApprovalPolicy
    ) -> List[uuid.UUID]:
        """Get all approver user IDs, expanding team memberships (async version).

        Args:
            approval_policy: The approval policy

        Returns:
            List of user IDs who can approve
        """
        from preloop.models.models.team import TeamMembership
        from sqlalchemy import select

        user_ids: Set[uuid.UUID] = set()

        # Add direct user approvers
        if approval_policy.approver_user_ids:
            user_ids.update(approval_policy.approver_user_ids)

        # Expand team approvers to individual users
        if approval_policy.approver_team_ids:
            for team_id in approval_policy.approver_team_ids:
                result = await self.db.execute(
                    select(TeamMembership.user_id).where(
                        TeamMembership.team_id == team_id
                    )
                )
                team_member_ids = result.scalars().all()
                user_ids.update(team_member_ids)

        return list(user_ids)

    async def _send_email_notification(
        self,
        approval_request: ApprovalRequest,
        approval_policy: ApprovalPolicy,
    ) -> Dict[str, Any]:
        """Send email notification for approval request.

        Args:
            approval_request: The approval request
            approval_policy: The approval policy

        Returns:
            Dict with send result
        """
        from preloop.utils.email import send_approval_request_email
        from preloop.models.models.user import User
        from sqlalchemy import select

        # Get all approver user IDs (including team members)
        approver_user_ids = await self._get_all_approver_user_ids(approval_policy)

        if not approver_user_ids:
            logger.warning(
                f"No approvers configured for approval policy {approval_policy.id}"
            )
            return {"success": False, "error": "No approvers configured"}

        # Send email to each approver who has email notifications enabled
        from preloop.models.crud import notification_preferences
        from preloop.models.db.session import get_db_session

        # Batch fetch notification preferences in executor to avoid blocking event loop
        def _get_email_disabled_users(user_ids: List[uuid.UUID]) -> Set[uuid.UUID]:
            """Fetch users with email notifications disabled (runs in thread pool)."""
            disabled_users: Set[uuid.UUID] = set()
            sync_db = next(get_db_session())
            try:
                for uid in user_ids:
                    prefs = notification_preferences.get_by_user(sync_db, uid)
                    if prefs and not prefs.enable_email:
                        disabled_users.add(uid)
            finally:
                sync_db.close()
            return disabled_users

        loop = asyncio.get_running_loop()
        email_disabled_users = await loop.run_in_executor(
            _sync_db_executor, _get_email_disabled_users, approver_user_ids
        )

        sent_count = 0
        failed_count = 0
        skipped_count = 0

        for user_id in approver_user_ids:
            try:
                # Check if user has email notifications disabled (already fetched)
                if user_id in email_disabled_users:
                    logger.debug(
                        f"Skipping email for user {user_id} - email notifications disabled"
                    )
                    skipped_count += 1
                    continue

                # Get user email using async query
                result = await self.db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()

                if not user or not user.email:
                    logger.warning(f"User {user_id} not found or has no email")
                    failed_count += 1
                    continue

                # Generate approval URL with token
                token = approval_request.approval_token
                approval_url = (
                    f"{self.base_url}/approval/{approval_request.id}?token={token}"
                )

                # Send email
                await send_approval_request_email(
                    user_email=user.email,
                    tool_name=approval_request.tool_name,
                    tool_args=approval_request.tool_args,
                    approval_url=approval_url,
                    agent_reasoning=approval_request.agent_reasoning,
                )

                sent_count += 1
                logger.info(f"Sent approval email to {user.email}")

            except Exception as e:
                logger.error(
                    f"Failed to send email to user {user_id}: {str(e)}", exc_info=True
                )
                failed_count += 1

        return {
            "success": failed_count == 0,
            "sent": sent_count,
            "failed": failed_count,
            "skipped": skipped_count,
        }

    def _get_all_approver_user_ids_sync(
        self, approval_policy: ApprovalPolicy, sync_db
    ) -> List[uuid.UUID]:
        """Get all approver user IDs, expanding team memberships (sync version).

        Args:
            approval_policy: The approval policy
            sync_db: Synchronous database session

        Returns:
            List of user IDs who can approve
        """
        from preloop.models.models.team import TeamMembership

        user_ids: Set[uuid.UUID] = set()

        # Add direct user approvers
        if approval_policy.approver_user_ids:
            user_ids.update(approval_policy.approver_user_ids)

        # Expand team approvers to individual users
        if approval_policy.approver_team_ids:
            for team_id in approval_policy.approver_team_ids:
                team_members = (
                    sync_db.query(TeamMembership.user_id)
                    .filter(TeamMembership.team_id == team_id)
                    .all()
                )
                user_ids.update(member.user_id for member in team_members)

        return list(user_ids)

    async def _send_push_notification(
        self,
        approval_request: ApprovalRequest,
        approval_policy: ApprovalPolicy,
    ) -> Dict[str, Any]:
        """Send mobile push notification for approval request.

        This method supports two modes:
        1. Native push: Uses APNs/FCM directly (enterprise with credentials)
        2. Proxy push: Routes through preloop.ai proxy (OSS with API key)

        Args:
            approval_request: The approval request
            approval_policy: The approval policy

        Returns:
            Dict with send result
        """
        from preloop.models.crud import notification_preferences
        from preloop.services.push_notifications import (
            get_apns_service,
            NotificationPayloadBuilder,
            send_fcm_notification,
            is_fcm_configured,
        )
        from preloop.services.push_proxy import (
            is_push_proxy_configured,
            send_push_via_proxy,
        )

        apns_service = get_apns_service()
        fcm_available = is_fcm_configured()
        use_proxy = not apns_service and is_push_proxy_configured()

        if not apns_service and not fcm_available and not use_proxy:
            logger.debug(
                "Push notifications not available (no APNs/FCM config, no proxy config)"
            )
            return {"success": False, "error": "Push notifications not configured"}

        # Run sync database operations in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()

        def _get_approvers_and_tokens():
            """Sync function to get approvers and their device tokens."""
            from preloop.models.db.session import get_db_session

            # Get a fresh sync database session (not from async session)
            sync_db = next(get_db_session())
            try:
                # Get all approver user IDs (including team members)
                approver_user_ids = self._get_all_approver_user_ids_sync(
                    approval_policy, sync_db
                )

                if not approver_user_ids:
                    return [], [], []

                # Collect user tokens for both iOS and Android
                ios_tokens_list = []
                android_tokens_list = []
                for user_id in approver_user_ids:
                    prefs = notification_preferences.get_by_user(sync_db, user_id)
                    if not prefs or not prefs.enable_mobile_push:
                        continue

                    ios_tokens = prefs.get_device_tokens(platform="ios")
                    if ios_tokens:
                        for token in ios_tokens:
                            ios_tokens_list.append((user_id, token))

                    android_tokens = prefs.get_device_tokens(platform="android")
                    if android_tokens:
                        for token in android_tokens:
                            android_tokens_list.append((user_id, token))

                return approver_user_ids, ios_tokens_list, android_tokens_list
            finally:
                sync_db.close()

        approver_user_ids, ios_tokens, android_tokens = await loop.run_in_executor(
            _sync_db_executor, _get_approvers_and_tokens
        )

        if not approver_user_ids:
            logger.warning(f"No approvers configured for policy {approval_policy.id}")
            return {"success": False, "error": "No approvers configured"}

        if not ios_tokens and not android_tokens:
            logger.info(
                f"No push-enabled devices for approvers in policy {approval_policy.id}"
            )
            return {"success": True, "sent": 0, "failed": 0, "no_devices": True}

        # Derive priority safely - ApprovalRequest doesn't have a priority field
        # Default to "medium" for normal requests
        priority_str = getattr(approval_request, "priority", None) or "medium"

        # Build notification payload with tool args for context
        payload = NotificationPayloadBuilder.new_approval_request(
            request_id=str(approval_request.id),
            tool_name=approval_request.tool_name,
            priority=priority_str,
            expires_at=approval_request.expires_at,
            agent_reasoning=approval_request.agent_reasoning,
            tool_args=approval_request.tool_args,
        )

        apns_priority = 10 if priority_str in ["urgent", "high"] else 5
        fcm_priority = "high" if priority_str in ["urgent", "high"] else "normal"

        sent_count = 0
        failed_count = 0
        invalid_tokens = []

        # Extract notification details for FCM
        notification_title = (
            payload.get("aps", {}).get("alert", {}).get("title", "Approval Required")
        )
        notification_body = (
            payload.get("aps", {})
            .get("alert", {})
            .get("body", "A request needs your attention")
        )
        notification_data = payload.get("data", {})

        # Send to iOS devices
        for user_id, token in ios_tokens:
            try:
                if apns_service:
                    # Use native APNs (enterprise mode with credentials)
                    (
                        success,
                        status_code,
                        error_reason,
                    ) = await apns_service.send_notification(
                        device_token=token, payload=payload, priority=apns_priority
                    )

                    if success:
                        sent_count += 1
                    elif status_code == 410:
                        # Token is no longer valid
                        invalid_tokens.append((user_id, token, "ios"))
                    else:
                        logger.warning(
                            f"APNs notification failed: status={status_code}, reason={error_reason}"
                        )
                        failed_count += 1
                else:
                    # Use push proxy (OSS mode with API key)
                    result = await send_push_via_proxy(
                        platform="ios",
                        device_token=token,
                        title=notification_title,
                        body=notification_body,
                        data=notification_data,
                        priority="high" if apns_priority == 10 else "normal",
                    )

                    if result.get("success"):
                        sent_count += 1
                    else:
                        logger.warning(f"iOS push proxy failed: {result.get('error')}")
                        failed_count += 1

            except Exception as e:
                logger.error(
                    f"iOS push notification error for token {token[:8]}...: {e}"
                )
                failed_count += 1

        # Send to Android devices
        for user_id, token in android_tokens:
            try:
                if fcm_available:
                    # Use native FCM (enterprise mode with credentials)
                    result = await send_fcm_notification(
                        token=token,
                        title=notification_title,
                        body=notification_body,
                        data=notification_data,
                        priority=fcm_priority,
                    )

                    if result.get("success"):
                        sent_count += 1
                    elif result.get("invalid_token"):
                        # Token is no longer valid
                        invalid_tokens.append((user_id, token, "android"))
                    else:
                        logger.warning(
                            f"FCM notification failed: {result.get('error')}"
                        )
                        failed_count += 1
                else:
                    # Use push proxy (OSS mode with API key)
                    result = await send_push_via_proxy(
                        platform="android",
                        device_token=token,
                        title=notification_title,
                        body=notification_body,
                        data=notification_data,
                        priority=fcm_priority,
                    )

                    if result.get("success"):
                        sent_count += 1
                    else:
                        logger.warning(
                            f"Android push proxy failed: {result.get('error')}"
                        )
                        failed_count += 1

            except Exception as e:
                logger.error(
                    f"Android push notification error for token {token[:8]}...: {e}"
                )
                failed_count += 1

        # Remove invalid tokens in background
        if invalid_tokens:

            def _remove_invalid_tokens():
                from preloop.models.db.session import get_db_session

                # Get a fresh sync database session (not from async session)
                sync_db = next(get_db_session())
                try:
                    for user_id, token, _ in invalid_tokens:
                        notification_preferences.remove_device_token(
                            sync_db, user_id, token
                        )
                    sync_db.commit()
                    logger.info(f"Removed {len(invalid_tokens)} invalid device tokens")
                except Exception as e:
                    logger.error(f"Failed to remove invalid tokens: {e}")
                    sync_db.rollback()
                finally:
                    sync_db.close()

            # Run token cleanup in background
            loop.run_in_executor(_sync_db_executor, _remove_invalid_tokens)

        # Notify admins if push notifications failed (and we had devices to send to)
        if failed_count > 0 and (ios_tokens or android_tokens):
            try:
                task_publisher = await get_task_publisher()
                if task_publisher:
                    await task_publisher.publish_task(
                        "notify_admins",
                        subject="Push Notification Delivery Failed",
                        message=(
                            f"Push notifications failed for approval request.\n\n"
                            f"Request ID: {approval_request.id}\n"
                            f"Tool: {approval_request.tool_name}\n"
                            f"Sent: {sent_count}, Failed: {failed_count}\n"
                            f"iOS devices: {len(ios_tokens)}, Android devices: {len(android_tokens)}\n\n"
                            f"Please check APNs/FCM configuration and device token validity."
                        ),
                    )
            except Exception as e:
                logger.error(f"Failed to notify admins about push failure: {e}")

        return {
            "success": failed_count == 0,
            "sent": sent_count,
            "failed": failed_count,
            "invalid_tokens_removed": len(invalid_tokens),
        }

    async def wait_for_approval(
        self, request_id: uuid.UUID, poll_interval: float = 1.0
    ) -> ApprovalRequest:
        """Wait for an approval request to be resolved.

        This will poll the database until the request is approved, declined,
        expired, or cancelled. If escalation is configured and the request
        expires, escalation will be triggered and the timeout extended.

        Args:
            request_id: Approval request ID
            poll_interval: How often to poll (seconds)

        Returns:
            Final approval request

        Raises:
            TimeoutError: If request expires before being resolved (after escalation if configured)
        """
        while True:
            approval_request = await self.get_approval_request(request_id)
            if not approval_request:
                raise ValueError(f"Approval request {request_id} not found")

            # Check if resolved
            if approval_request.status in ["approved", "declined", "cancelled"]:
                return approval_request

            # Check if expired
            if (
                approval_request.expires_at
                and datetime.utcnow() > approval_request.expires_at
            ):
                # Get the approval policy to check for escalation configuration
                approval_policy = approval_request.approval_policy

                # Debug logging for escalation check
                logger.info(
                    f"Checking escalation for request {request_id}: "
                    f"approval_policy={approval_policy}, "
                    f"approval_policy_id={approval_request.approval_policy_id}, "
                    f"escalation_user_ids={getattr(approval_policy, 'escalation_user_ids', None) if approval_policy else None}, "
                    f"escalation_team_ids={getattr(approval_policy, 'escalation_team_ids', None) if approval_policy else None}, "
                    f"escalation_triggered_at={approval_request.escalation_triggered_at}"
                )

                # Check if escalation is configured and hasn't been triggered yet
                has_escalation = approval_policy and (
                    approval_policy.escalation_user_ids
                    or approval_policy.escalation_team_ids
                )
                escalation_already_triggered = (
                    approval_request.escalation_triggered_at is not None
                )

                logger.info(
                    f"Escalation decision for request {request_id}: "
                    f"has_escalation={has_escalation}, "
                    f"escalation_already_triggered={escalation_already_triggered}"
                )

                if has_escalation and not escalation_already_triggered:
                    # Trigger escalation
                    logger.info(
                        f"Triggering escalation for approval request {request_id}"
                    )

                    # Mark escalation as triggered
                    approval_request.escalation_triggered_at = datetime.utcnow()

                    # Extend the timeout - give escalation recipients the same amount of time
                    original_timeout = approval_policy.timeout_seconds or 300
                    new_expires_at = datetime.utcnow() + timedelta(
                        seconds=original_timeout
                    )
                    approval_request.expires_at = new_expires_at

                    await self.db.commit()
                    await self.db.refresh(approval_request)

                    # Send escalation notifications
                    await self._send_escalation_notifications(
                        approval_request, approval_policy
                    )

                    # Broadcast escalation event
                    await self._broadcast_approval_update(
                        approval_request,
                        "escalated",
                        extra_data={"new_expires_at": new_expires_at.isoformat()},
                    )

                    # Continue polling - don't expire yet
                    await asyncio.sleep(poll_interval)
                    continue

                # No escalation configured or already escalated - expire the request
                expired_request = await self.update_approval_request(
                    request_id, ApprovalRequestUpdate(status="expired")
                )
                # Broadcast expiration event
                if expired_request:
                    await self._broadcast_approval_update(expired_request, "expired")

                    # Log to audit trail (fire-and-forget)
                    _log_approval_lifecycle_async(
                        account_id=str(expired_request.account_id),
                        approval_id=expired_request.id,
                        event="expired",
                        tool_name=expired_request.tool_name,
                        reason="Request timed out without response",
                        execution_id=expired_request.execution_id,
                    )

                raise TimeoutError(
                    f"Approval request {request_id} expired without response"
                )

            # Wait before polling again
            await asyncio.sleep(poll_interval)

    async def _send_escalation_notifications(
        self,
        approval_request: ApprovalRequest,
        approval_policy: ApprovalPolicy,
    ) -> Dict[str, Any]:
        """Send notifications to escalation targets.

        Uses run_in_executor for sync DB/email operations to avoid blocking the event loop.

        Args:
            approval_request: The approval request that timed out
            approval_policy: The approval policy with escalation configuration

        Returns:
            Dict with notification results
        """
        from preloop.models.crud import notification_preferences
        from preloop.services.push_notifications import (
            get_apns_service,
            NotificationPayloadBuilder,
            send_fcm_notification,
            is_fcm_configured,
        )
        from preloop.services.push_proxy import (
            is_push_proxy_configured,
            send_push_via_proxy,
        )

        logger.info(
            f"Sending escalation notifications for request {approval_request.id}"
        )

        loop = asyncio.get_event_loop()

        # Capture values needed in sync function
        request_id = str(approval_request.id)
        tool_name = approval_request.tool_name
        approval_token = approval_request.approval_token
        base_url = self.base_url

        def _get_escalation_users_and_send_emails():
            """Sync function to get escalation users, their tokens, and send emails."""
            from preloop.models.db.session import get_db_session
            from preloop.models.crud import crud_team, crud_user
            from preloop.utils.email import send_escalation_email

            sync_db = next(get_db_session())
            try:
                # Collect escalation user IDs
                escalation_user_ids = set()

                if approval_policy.escalation_user_ids:
                    escalation_user_ids.update(approval_policy.escalation_user_ids)

                if approval_policy.escalation_team_ids:
                    for team_id in approval_policy.escalation_team_ids:
                        team_members = crud_team.get_team_members(sync_db, team_id)
                        escalation_user_ids.update(m.user_id for m in team_members)

                if not escalation_user_ids:
                    return set(), [], []

                # Send emails and collect device tokens
                ios_tokens_list = []
                android_tokens_list = []
                emails_sent = 0

                for user_id in escalation_user_ids:
                    user = crud_user.get(sync_db, id=user_id)
                    if user and user.email:
                        try:
                            send_escalation_email(
                                user_email=user.email,
                                tool_name=tool_name,
                                request_id=request_id,
                                approval_token=approval_token,
                                base_url=base_url,
                            )
                            emails_sent += 1
                        except Exception as e:
                            logger.error(
                                f"Failed to send escalation email to {user.email}: {e}"
                            )

                    # Get device tokens
                    prefs = notification_preferences.get_by_user(sync_db, user_id)
                    if prefs and prefs.enable_mobile_push:
                        ios_tokens = prefs.get_device_tokens(platform="ios")
                        if ios_tokens:
                            for token in ios_tokens:
                                ios_tokens_list.append((user_id, token))

                        android_tokens = prefs.get_device_tokens(platform="android")
                        if android_tokens:
                            for token in android_tokens:
                                android_tokens_list.append((user_id, token))

                logger.info(f"Sent {emails_sent} escalation emails")
                return escalation_user_ids, ios_tokens_list, android_tokens_list
            finally:
                sync_db.close()

        # Run sync operations in thread pool
        escalation_user_ids, ios_tokens, android_tokens = await loop.run_in_executor(
            _sync_db_executor, _get_escalation_users_and_send_emails
        )

        if not escalation_user_ids:
            logger.warning("No escalation targets configured")
            return {"success": False, "error": "No escalation targets"}

        # Send push notifications
        apns_service = get_apns_service()
        fcm_available = is_fcm_configured()
        use_proxy = not apns_service and is_push_proxy_configured()

        if not ios_tokens and not android_tokens:
            logger.info("No push-enabled devices for escalation users")
            return {
                "success": True,
                "escalation_users": len(escalation_user_ids),
                "push_sent": 0,
            }

        # Build escalation notification payload
        payload = NotificationPayloadBuilder.new_approval_request(
            request_id=request_id,
            tool_name=tool_name,
            priority="high",  # Escalations are always high priority
            expires_at=approval_request.expires_at,
            agent_reasoning=f"ESCALATED: {approval_request.agent_reasoning or 'Original approvers did not respond'}",
            tool_args=approval_request.tool_args,
        )

        sent_count = 0
        failed_count = 0

        # Extract notification details for FCM
        notification_title = (
            payload.get("aps", {})
            .get("alert", {})
            .get("title", "ESCALATED: Approval Required")
        )
        notification_body = (
            payload.get("aps", {})
            .get("alert", {})
            .get("body", "Original approvers did not respond")
        )
        notification_data = payload.get("data", {})

        # Send to iOS devices
        for _user_id, token in ios_tokens:
            try:
                if apns_service:
                    (
                        success,
                        status_code,
                        error_reason,
                    ) = await apns_service.send_notification(
                        device_token=token,
                        payload=payload,
                        priority=10,  # High priority
                    )
                    if success:
                        sent_count += 1
                    else:
                        logger.warning(
                            f"Escalation APNs failed: status={status_code}, reason={error_reason}"
                        )
                        failed_count += 1
                elif use_proxy:
                    result = await send_push_via_proxy(
                        device_token=token,
                        platform="ios",
                        title=notification_title,
                        body=notification_body,
                        data=notification_data,
                    )
                    if result.get("success"):
                        sent_count += 1
                    else:
                        failed_count += 1
            except Exception as e:
                logger.error(f"Escalation iOS push error: {e}")
                failed_count += 1

        # Send to Android devices
        for _user_id, token in android_tokens:
            try:
                if fcm_available:
                    success = await send_fcm_notification(
                        device_token=token,
                        title=notification_title,
                        body=notification_body,
                        data=notification_data,
                        priority="high",
                    )
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                elif use_proxy:
                    result = await send_push_via_proxy(
                        device_token=token,
                        platform="android",
                        title=notification_title,
                        body=notification_body,
                        data=notification_data,
                    )
                    if result.get("success"):
                        sent_count += 1
                    else:
                        failed_count += 1
            except Exception as e:
                logger.error(f"Escalation Android push error: {e}")
                failed_count += 1

        logger.info(
            f"Escalation push notifications: sent={sent_count}, failed={failed_count}"
        )

        return {
            "success": True,
            "escalation_users": len(escalation_user_ids),
            "push_sent": sent_count,
            "push_failed": failed_count,
        }
