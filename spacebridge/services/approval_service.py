"""Service for managing approval requests and webhook posting."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urljoin

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from spacemodels.models import ApprovalRequest, ApprovalPolicy
from spacemodels.schemas.approval_request import (
    ApprovalRequestUpdate,
)
from spacemodels.crud.approval_request import get_approval_request_async


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
        self, request_id: uuid.UUID, comment: Optional[str] = None
    ) -> Optional[ApprovalRequest]:
        """Approve an approval request.

        Args:
            request_id: Approval request ID
            comment: Optional comment from approver

        Returns:
            Updated approval request or None if not found
        """
        update = ApprovalRequestUpdate(
            status="approved",
            approver_comment=comment,
            resolved_at=datetime.utcnow(),
        )
        return await self.update_approval_request(request_id, update)

    async def decline_request(
        self, request_id: uuid.UUID, comment: Optional[str] = None
    ) -> Optional[ApprovalRequest]:
        """Decline an approval request.

        Args:
            request_id: Approval request ID
            comment: Optional comment from approver

        Returns:
            Updated approval request or None if not found
        """
        update = ApprovalRequestUpdate(
            status="declined",
            approver_comment=comment,
            resolved_at=datetime.utcnow(),
        )
        return await self.update_approval_request(request_id, update)

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
    ) -> ApprovalRequest:
        """Create approval request and send webhook notification.

        Args:
            account_id: The account creating the request
            tool_configuration_id: Tool configuration ID
            approval_policy: The approval policy to use
            tool_name: Name of the tool being executed
            tool_args: Arguments passed to the tool
            agent_reasoning: Agent's reasoning for the tool call
            execution_id: Flow execution ID (if applicable)

        Returns:
            Created approval request
        """
        # Create approval request
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

        # Post webhook notification (don't await - fire and forget)
        asyncio.create_task(
            self.post_webhook_notification(approval_request, approval_policy)
        )

        return approval_request

    async def wait_for_approval(
        self, request_id: uuid.UUID, poll_interval: float = 1.0
    ) -> ApprovalRequest:
        """Wait for an approval request to be resolved.

        This will poll the database until the request is approved, declined,
        expired, or cancelled.

        Args:
            request_id: Approval request ID
            poll_interval: How often to poll (seconds)

        Returns:
            Final approval request

        Raises:
            TimeoutError: If request expires before being resolved
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
                # Mark as expired
                await self.update_approval_request(
                    request_id, ApprovalRequestUpdate(status="expired")
                )
                raise TimeoutError(
                    f"Approval request {request_id} expired without response"
                )

            # Wait before polling again
            await asyncio.sleep(poll_interval)
