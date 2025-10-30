"""Reusable approval helper with streaming progress support.

This module provides a helper function for checking and waiting for tool approval
with real-time progress updates via FastMCP Context.
"""

import asyncio
import logging
import os
from typing import Optional, Tuple

from fastmcp import Context

logger = logging.getLogger(__name__)


async def require_approval(
    tool_name: str,
    tool_source: str,
    account_id: str,
    arguments: dict,
    ctx: Optional[Context] = None,
    policy_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """Check if tool requires approval and wait for decision with streaming.

    This function checks ToolConfiguration to see if the tool requires approval.
    If approval is required, it creates an approval request, sends notifications,
    and polls for approval status while streaming progress updates via Context.

    Args:
        tool_name: Name of the tool being executed
        tool_source: Tool source type ("builtin" or "mcp")
        account_id: Account ID of the user executing the tool
        arguments: Tool arguments
        ctx: FastMCP Context for streaming progress updates
        policy_id: Optional approval policy ID. If provided, uses this policy directly
                  instead of looking up from tool configuration. Useful for standalone
                  approval requests where no tool configuration exists.

    Returns:
        Tuple of (approved: bool, error_message: str)
        - If approved: (True, "")
        - If declined/error: (False, "error message")
    """
    try:
        from spacemodels.db.session import get_async_db_session
        from spacemodels.crud.tool_configuration import (
            get_tool_config_by_name_and_source_async,
        )
        from spacemodels.crud.approval_policy import get_approval_policy_async

        logger.info(
            f"Checking approval requirement for {tool_source} tool '{tool_name}' "
            f"(account_id={account_id})"
        )

        async with get_async_db_session() as db:
            # If policy_id is provided directly (for standalone requests), use it
            if policy_id:
                logger.info(
                    f"Using explicitly provided policy_id={policy_id} for tool {tool_name}"
                )
                policy = await get_approval_policy_async(db, policy_id=policy_id)

                if not policy:
                    logger.error(f"Provided approval policy {policy_id} not found")
                    return (
                        False,
                        f"Error: Approval policy with ID '{policy_id}' not found",
                    )
            else:
                # Check for tool configuration using CRUD
                config = await get_tool_config_by_name_and_source_async(
                    db,
                    account_id=account_id,
                    tool_name=tool_name,
                    tool_source=tool_source,
                )

                # If tool doesn't require approval, execute directly
                if (
                    not config
                    or not config.requires_approval
                    or not config.approval_policy_id
                ):
                    logger.info(
                        f"Tool {tool_name} ({tool_source}) does not require approval"
                    )
                    return (True, "")

                # Get approval policy from tool configuration
                policy = await get_approval_policy_async(
                    db, policy_id=config.approval_policy_id
                )

                if not policy:
                    logger.error(
                        f"Approval policy {config.approval_policy_id} not found for tool {tool_name}"
                    )
                    return (
                        False,
                        f"Error: Approval policy not found for tool '{tool_name}'",
                    )

            # Tool requires approval - handle it with streaming
            logger.info(
                f"Tool {tool_name} ({tool_source}) requires approval - initiating approval flow with streaming"
            )

            # Create approval request
            from spacebridge.services.approval_service import ApprovalService
            from spacemodels.schemas.approval_request import ApprovalRequestUpdate

            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            approval_service = ApprovalService(db, base_url)

            try:
                # Create approval request and send notification
                approval_request = await approval_service.create_and_notify(
                    account_id=account_id,
                    tool_configuration_id=config.id,
                    approval_policy=policy,
                    tool_name=tool_name,
                    tool_args=arguments,
                    agent_reasoning=None,
                    execution_id=None,
                )

                approval_url = f"{base_url}/approval/{approval_request.id}?token={approval_request.approval_token}"
                notification_channel = (
                    f"#{policy.channel}"
                    if policy.channel
                    else f"@{policy.user}"
                    if policy.user
                    else "webhook"
                )

                logger.warning(
                    f"\n{'=' * 60}\n"
                    f"🚨 APPROVAL REQUIRED ({tool_source.upper()} Tool) 🚨\n"
                    f"{'=' * 60}\n"
                    f"Tool: {tool_name}\n"
                    f"Arguments: {arguments}\n"
                    f"Request ID: {approval_request.id}\n"
                    f"Notification sent to: {policy.approval_type} ({notification_channel})\n"
                    f"Timeout: {policy.timeout_seconds or 300}s\n"
                    f"Approval URL: {approval_url}\n"
                    f"{'=' * 60}\n"
                    f"⏳ Waiting for approval (polling every 2s)..."
                )

                # Send initial notification via Context (FastMCP streaming)
                if ctx:
                    try:
                        logger.info(f"Context object: {ctx}, type: {type(ctx)}")
                        logger.info(
                            f"Has report_progress: {hasattr(ctx, 'report_progress')}"
                        )
                        # Report progress at 0% with status message
                        status_message = (
                            f"Approval request sent to {policy.approval_type} "
                            f"({notification_channel})"
                        )
                        # Check if progressToken is available
                        progress_token = None
                        try:
                            progress_token = (
                                ctx.request_context.meta.progressToken
                                if ctx.request_context.meta
                                else None
                            )
                        except Exception as e:
                            logger.error(f"Error getting progressToken: {e}")

                        logger.info(f"   progressToken: {progress_token}")
                        logger.info(
                            f"   request_context.meta: {ctx.request_context.meta if hasattr(ctx, 'request_context') else 'N/A'}"
                        )

                        # Try to send directly via session to debug
                        try:
                            await ctx.session.send_progress_notification(
                                progress_token=progress_token,
                                progress=0.0,
                                total=100.0,
                                message=status_message,
                                related_request_id=ctx.request_id,
                            )
                            logger.info(
                                "✅ DIRECT send_progress_notification succeeded"
                            )
                        except Exception as e:
                            logger.error(
                                f"❌ DIRECT send_progress_notification failed: {e}",
                                exc_info=True,
                            )

                        result = await ctx.report_progress(
                            progress=0, total=100, message=status_message
                        )
                        logger.info(
                            f"✅ Sent initial progress via ctx.report_progress: {status_message}, result: {result}"
                        )
                        logger.info(
                            f"   Context session: {ctx.session}, request_id: {ctx.request_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Could not send progress via Context: {e}", exc_info=True
                        )
                else:
                    logger.warning(
                        "❌ No Context available - cannot send progress notifications!"
                    )

                # Polling loop with progress updates
                poll_interval = 2.0
                timeout_seconds = policy.timeout_seconds or 300
                elapsed = 0

                while True:
                    # Check approval status with fresh database session
                    from spacemodels.crud.approval_request import (
                        get_approval_request_async,
                    )

                    async with get_async_db_session() as poll_db:
                        current_request = await get_approval_request_async(
                            poll_db, request_id=approval_request.id
                        )

                    logger.info(
                        f"[Polling] Checked approval status: {current_request.status if current_request else 'NOT_FOUND'} "
                        f"(elapsed: {elapsed}s)"
                    )

                    if not current_request:
                        return (
                            False,
                            f"Error: Approval request {approval_request.id} not found",
                        )

                    # Check if resolved
                    if current_request.status in ["approved", "declined", "cancelled"]:
                        logger.info(
                            f"[Polling] ✅ Approval resolved with status: {current_request.status}"
                        )
                        final_request = current_request
                        break

                    # Check if expired
                    if elapsed >= timeout_seconds:
                        # Send timeout notification
                        if ctx:
                            try:
                                timeout_message = f"Approval request timed out after {timeout_seconds}s"
                                await ctx.report_progress(
                                    progress=100, total=100, message=timeout_message
                                )
                                logger.info(
                                    f"[Polling] Sent timeout notification: {timeout_message}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to send timeout notification: {e}",
                                    exc_info=True,
                                )

                        async with get_async_db_session() as update_db:
                            update_service = ApprovalService(update_db, base_url)
                            await update_service.update_approval_request(
                                approval_request.id,
                                ApprovalRequestUpdate(status="expired"),
                            )
                        return (
                            False,
                            f"Approval timeout: request expired after {timeout_seconds}s",
                        )

                    # Send progress update every 10 seconds via Context
                    if ctx and int(elapsed) % 10 == 0 and elapsed > 0:
                        try:
                            progress_pct = int((elapsed / timeout_seconds) * 100)
                            remaining = timeout_seconds - elapsed

                            # Create meaningful status message
                            status_message = (
                                f"Waiting for approval from {notification_channel} "
                                f"({int(remaining)}s remaining)"
                            )

                            # Use Context.report_progress for streaming
                            await ctx.report_progress(
                                progress=progress_pct, total=100, message=status_message
                            )
                            logger.info(
                                f"[Polling] Sent progress: {progress_pct}% - {status_message}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to send progress update: {e}", exc_info=True
                            )

                    # Wait before next poll
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval

                # Send completion notification with final status
                if ctx:
                    try:
                        # Determine final status message
                        if final_request.status == "approved":
                            status_message = "Approved"
                            if final_request.approver_comment:
                                status_message += f": {final_request.approver_comment}"
                        elif final_request.status == "declined":
                            status_message = "Declined"
                            if final_request.approver_comment:
                                status_message += f": {final_request.approver_comment}"
                        elif final_request.status == "cancelled":
                            status_message = "Request cancelled"
                        else:
                            status_message = (
                                f"Unexpected status: {final_request.status}"
                            )

                        await ctx.report_progress(
                            progress=100, total=100, message=status_message
                        )
                        logger.info(
                            f"[Polling] Sent completion: 100% - {status_message}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to send completion notification: {e}",
                            exc_info=True,
                        )

                # Check final status
                if final_request.status == "declined":
                    logger.warning(f"Tool {tool_name} execution declined")
                    comment = (
                        f": {final_request.approver_comment}"
                        if final_request.approver_comment
                        else ""
                    )
                    return (False, f"Tool execution declined{comment}")
                elif final_request.status == "cancelled":
                    logger.warning(f"Tool {tool_name} execution cancelled")
                    return (False, "Tool execution cancelled")
                elif final_request.status != "approved":
                    logger.error(
                        f"Unexpected approval status for tool {tool_name}: {final_request.status}"
                    )
                    return (
                        False,
                        f"Unexpected approval status: {final_request.status}",
                    )

                # Approved! Continue with execution
                logger.warning(
                    f"✅ Tool {tool_name} APPROVED - proceeding with execution"
                )
                return (True, "")

            except Exception as e:
                logger.error(
                    f"Approval flow error for tool {tool_name}: {e}", exc_info=True
                )
                return (False, f"Approval error: {str(e)}")

    except Exception as e:
        logger.error(f"Error checking approval requirement: {e}", exc_info=True)
        # Fail-open: if approval check fails, allow execution
        return (True, "")
