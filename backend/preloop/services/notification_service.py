"""Notification service for approval requests.

This module handles sending notifications through various channels:
- Email (Open Core + Proprietary)
- Mobile Push (Open Core + Proprietary)
- Slack (Proprietary)
- Mattermost (Proprietary)
- Webhook (Proprietary)
"""

import uuid
import logging
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from preloop.models import models
from preloop.models.crud import notification_preferences

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending approval notifications."""

    def __init__(self, db: Session):
        """Initialize notification service.

        Args:
            db: Database session.
        """
        self.db = db

    async def notify_approval_request(
        self,
        approval_request: models.ApprovalRequest,
        approval_policy: models.ApprovalPolicy,
    ) -> Dict[str, Any]:
        """Send notifications for an approval request.

        Args:
            approval_request: The approval request to notify about.
            approval_policy: The approval policy containing notification config.

        Returns:
            Dict with notification results per channel.
        """
        results = {}

        # Get list of approvers (expand teams to users)
        approver_user_ids = await self._get_approver_user_ids(approval_policy)

        # Send notifications through configured channels
        for channel in approval_policy.notification_channels:
            try:
                if channel == "email":
                    result = await self._send_email_notifications(
                        approval_request, approver_user_ids
                    )
                    results["email"] = result

                elif channel == "mobile_push":
                    result = await self._send_push_notifications(
                        approval_request, approver_user_ids
                    )
                    results["mobile_push"] = result

                elif channel == "slack":
                    result = await self._send_slack_notification(
                        approval_request, approval_policy
                    )
                    results["slack"] = result

                elif channel == "mattermost":
                    result = await self._send_mattermost_notification(
                        approval_request, approval_policy
                    )
                    results["mattermost"] = result

                elif channel == "webhook":
                    result = await self._send_webhook_notification(
                        approval_request, approval_policy
                    )
                    results["webhook"] = result

                else:
                    logger.warning(f"Unknown notification channel: {channel}")

            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {str(e)}")
                results[channel] = {"success": False, "error": str(e)}

        return results

    async def notify_escalation(
        self,
        approval_request: models.ApprovalRequest,
        approval_policy: models.ApprovalPolicy,
    ) -> Dict[str, Any]:
        """Send escalation notifications.

        Args:
            approval_request: The approval request that timed out.
            approval_policy: The approval policy containing escalation config.

        Returns:
            Dict with notification results per channel.
        """
        results = {}

        # Get escalation approvers
        escalation_user_ids = await self._get_escalation_user_ids(approval_policy)

        if not escalation_user_ids:
            logger.warning("No escalation approvers configured")
            return {"error": "No escalation approvers configured"}

        # Send through same channels as original request
        for channel in approval_policy.notification_channels:
            try:
                if channel == "email":
                    result = await self._send_email_notifications(
                        approval_request, escalation_user_ids, is_escalation=True
                    )
                    results["email"] = result

                elif channel == "mobile_push":
                    result = await self._send_push_notifications(
                        approval_request, escalation_user_ids, is_escalation=True
                    )
                    results["mobile_push"] = result

                elif channel in ["slack", "mattermost", "webhook"]:
                    # Use same notification method but with escalation context
                    # (Implementation would add "ESCALATION" prefix to message)
                    pass

            except Exception as e:
                logger.error(
                    f"Failed to send escalation {channel} notification: {str(e)}"
                )
                results[channel] = {"success": False, "error": str(e)}

        return results

    async def _get_approver_user_ids(
        self, approval_policy: models.ApprovalPolicy
    ) -> List[uuid.UUID]:
        """Get list of approver user IDs, expanding teams.

        Args:
            approval_policy: Approval policy.

        Returns:
            List of user IDs who can approve.
        """
        user_ids = set()

        # Add direct user approvers
        if approval_policy.approver_user_ids:
            user_ids.update(approval_policy.approver_user_ids)

        # Expand team approvers to individual users
        if approval_policy.approver_team_ids:
            for team_id in approval_policy.approver_team_ids:
                team_members = (
                    self.db.query(models.TeamMembership.user_id)
                    .filter(models.TeamMembership.team_id == team_id)
                    .all()
                )
                user_ids.update([member.user_id for member in team_members])

        return list(user_ids)

    async def _get_escalation_user_ids(
        self, approval_policy: models.ApprovalPolicy
    ) -> List[uuid.UUID]:
        """Get list of escalation approver user IDs, expanding teams.

        Args:
            approval_policy: Approval policy.

        Returns:
            List of escalation user IDs.
        """
        user_ids = set()

        # Add direct escalation users
        if approval_policy.escalation_user_ids:
            user_ids.update(approval_policy.escalation_user_ids)

        # Expand escalation teams
        if approval_policy.escalation_team_ids:
            for team_id in approval_policy.escalation_team_ids:
                team_members = (
                    self.db.query(models.TeamMembership.user_id)
                    .filter(models.TeamMembership.team_id == team_id)
                    .all()
                )
                user_ids.update([member.user_id for member in team_members])

        return list(user_ids)

    async def _send_email_notifications(
        self,
        approval_request: models.ApprovalRequest,
        user_ids: List[uuid.UUID],
        is_escalation: bool = False,
    ) -> Dict[str, Any]:
        """Send email notifications to approvers.

        Args:
            approval_request: Approval request.
            user_ids: List of user IDs to notify.
            is_escalation: Whether this is an escalation notification.

        Returns:
            Dict with send results.
        """
        # TODO: Integrate with email service
        # For now, log and return placeholder
        logger.info(
            f"Would send {'escalation ' if is_escalation else ''}email to {len(user_ids)} users "
            f"for approval request {approval_request.id}"
        )

        return {
            "success": True,
            "recipients": len(user_ids),
            "is_escalation": is_escalation,
        }

    async def _send_push_notifications(
        self,
        approval_request: models.ApprovalRequest,
        user_ids: List[uuid.UUID],
        is_escalation: bool = False,
    ) -> Dict[str, Any]:
        """Send mobile push notifications to approvers.

        Args:
            approval_request: Approval request.
            user_ids: List of user IDs to notify.
            is_escalation: Whether this is an escalation notification.

        Returns:
            Dict with send results.
        """
        from preloop.services.push_notifications import (
            get_apns_service,
            NotificationPayloadBuilder,
        )

        apns_service = get_apns_service()
        if not apns_service:
            logger.warning("APNs service not configured")
            return {
                "success": False,
                "error": "APNs not configured",
                "sent": 0,
                "failed": 0,
            }

        sent_count = 0
        failed_count = 0
        invalid_tokens = []  # Track 410 responses

        for user_id in user_ids:
            # Get user's notification preferences
            prefs = notification_preferences.get_by_user(self.db, user_id)
            if not prefs or not prefs.enable_mobile_push:
                continue

            # Get iOS device tokens
            ios_tokens = prefs.get_device_tokens(platform="ios")
            if not ios_tokens:
                continue

            # Build notification payload
            # Note: ApprovalRequest model doesn't have a priority field,
            # so we default to "medium" and set to "high" for escalations
            priority_str = "high" if is_escalation else "medium"
            payload = NotificationPayloadBuilder.new_approval_request(
                request_id=str(approval_request.id),
                tool_name=approval_request.tool_name,
                priority=priority_str,
                expires_at=approval_request.expires_at,
                agent_reasoning=approval_request.agent_reasoning,
            )

            # Add escalation prefix if needed
            if is_escalation:
                payload["aps"]["alert"]["title"] = (
                    "ESCALATION: " + payload["aps"]["alert"]["title"]
                )

            # Determine APNs priority
            apns_priority = 10 if priority_str in ["urgent", "high"] else 5

            # Send to each device
            for token in ios_tokens:
                try:
                    (
                        success,
                        status_code,
                        error_reason,
                    ) = await apns_service.send_notification(
                        device_token=token,
                        payload=payload,
                        priority=apns_priority,
                    )

                    if success:
                        sent_count += 1
                    elif status_code == 410:
                        # Token is invalid/expired
                        invalid_tokens.append((user_id, token))
                        logger.info(f"Marking token as invalid: {token[:10]}...")
                    else:
                        failed_count += 1

                except Exception as e:
                    logger.error(f"Failed to send push to token {token[:10]}...: {e}")
                    failed_count += 1

        # Remove invalid tokens from database
        for user_id, token in invalid_tokens:
            try:
                notification_preferences.remove_device_token(self.db, user_id, token)
                logger.info(f"Removed invalid token for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to remove token: {e}")

        # Commit token removals
        if invalid_tokens:
            self.db.commit()

        return {
            "success": failed_count == 0,
            "sent": sent_count,
            "failed": failed_count,
            "invalid_tokens_removed": len(invalid_tokens),
            "is_escalation": is_escalation,
        }

    async def _send_slack_notification(
        self,
        approval_request: models.ApprovalRequest,
        approval_policy: models.ApprovalPolicy,
    ) -> Dict[str, Any]:
        """Send Slack notification.

        Args:
            approval_request: Approval request.
            approval_policy: Approval policy with Slack configuration.

        Returns:
            Dict with send result.
        """
        # TODO: Implement Slack webhook integration
        channel_config = approval_policy.channel_configs.get("slack", {})
        webhook_url = channel_config.get("webhook_url")

        if not webhook_url:
            return {"success": False, "error": "No Slack webhook URL configured"}

        logger.info(
            f"Would send Slack notification for approval request {approval_request.id}"
        )

        return {"success": True, "channel": approval_policy.channel}

    async def _send_mattermost_notification(
        self,
        approval_request: models.ApprovalRequest,
        approval_policy: models.ApprovalPolicy,
    ) -> Dict[str, Any]:
        """Send Mattermost notification.

        Args:
            approval_request: Approval request.
            approval_policy: Approval policy with Mattermost configuration.

        Returns:
            Dict with send result.
        """
        # TODO: Implement Mattermost webhook integration
        channel_config = approval_policy.channel_configs.get("mattermost", {})
        webhook_url = channel_config.get("webhook_url")

        if not webhook_url:
            return {"success": False, "error": "No Mattermost webhook URL configured"}

        logger.info(
            f"Would send Mattermost notification for approval request {approval_request.id}"
        )

        return {"success": True, "channel": approval_policy.channel}

    async def _send_webhook_notification(
        self,
        approval_request: models.ApprovalRequest,
        approval_policy: models.ApprovalPolicy,
    ) -> Dict[str, Any]:
        """Send generic webhook notification.

        Args:
            approval_request: Approval request.
            approval_policy: Approval policy with webhook configuration.

        Returns:
            Dict with send result.
        """
        # TODO: Implement generic webhook POST
        channel_config = approval_policy.channel_configs.get("webhook", {})
        webhook_url = channel_config.get("url")

        if not webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        logger.info(
            f"Would send webhook notification for approval request {approval_request.id}"
        )

        return {"success": True, "url": webhook_url}
