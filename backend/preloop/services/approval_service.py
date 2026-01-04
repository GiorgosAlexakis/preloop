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
from preloop.models.crud.approval_request import get_approval_request_async
from preloop.sync.services.event_bus import get_task_publisher

logger = logging.getLogger(__name__)

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
        self, approval_request: ApprovalRequest, event_type: str
    ):
        """Broadcast approval request update via NATS/WebSocket.

        Args:
            approval_request: The approval request
            event_type: Type of event (created, approved, declined, expired)
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
        updated_request = await self.update_approval_request(request_id, update)

        # Broadcast approval event
        if updated_request:
            await self._broadcast_approval_update(updated_request, "approved")

        return updated_request

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
        updated_request = await self.update_approval_request(request_id, update)

        # Broadcast decline event
        if updated_request:
            await self._broadcast_approval_update(updated_request, "declined")

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
    ) -> ApprovalRequest:
        """Create approval request and send notifications through configured channels.

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

        # Send notifications through configured channels
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

        # Build notification payload
        payload = NotificationPayloadBuilder.new_approval_request(
            request_id=str(approval_request.id),
            tool_name=approval_request.tool_name,
            priority=priority_str,
            expires_at=approval_request.expires_at,
            agent_reasoning=approval_request.agent_reasoning,
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
                expired_request = await self.update_approval_request(
                    request_id, ApprovalRequestUpdate(status="expired")
                )
                # Broadcast expiration event
                if expired_request:
                    await self._broadcast_approval_update(expired_request, "expired")

                raise TimeoutError(
                    f"Approval request {request_id} expired without response"
                )

            # Wait before polling again
            await asyncio.sleep(poll_interval)
