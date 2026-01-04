"""Service for calculating flow execution metrics."""

import logging
import re
from typing import Dict

from sqlalchemy.orm import Session

from preloop.models import models

logger = logging.getLogger(__name__)


class ExecutionMetricsService:
    """Calculate metrics for flow executions including token usage and costs."""

    def __init__(self, db: Session):
        self.db = db

    def get_execution_metrics(self, execution_id: str) -> Dict:
        """Get comprehensive metrics for a flow execution.

        Args:
            execution_id: UUID of the flow execution

        Returns:
            Dictionary with:
            - tool_calls: Number of MCP tool calls
            - api_requests: Number of API requests made
            - token_usage: Token usage from codex logs
            - estimated_cost: Estimated cost based on token usage (0.0 if no pricing)
            - has_pricing: Whether pricing is configured in AI model metadata
        """
        execution = (
            self.db.query(models.FlowExecution)
            .filter(models.FlowExecution.id == execution_id)
            .first()
        )

        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        # Parse logs for tool calls
        tool_calls = self._count_tool_calls(execution)

        # Parse codex logs for token usage
        token_usage = self._parse_token_usage(execution)

        # Query API usage for this execution
        api_requests = self._count_api_requests(execution)

        # Calculate estimated cost
        estimated_cost, has_pricing = self._calculate_cost(execution, token_usage)

        return {
            "tool_calls": tool_calls,
            "api_requests": api_requests,
            "token_usage": token_usage,
            "estimated_cost": estimated_cost,
            "has_pricing": has_pricing,
        }

    def _count_tool_calls(self, execution: models.FlowExecution) -> int:
        """Count tool calls from execution logs.

        Args:
            execution: FlowExecution model

        Returns:
            Number of tool calls
        """
        count = 0

        # Count from mcp_usage_logs if available
        if execution.mcp_usage_logs and isinstance(execution.mcp_usage_logs, list):
            count += len(execution.mcp_usage_logs)

        # Count from execution_logs for real-time executions
        if execution.execution_logs and isinstance(execution.execution_logs, list):
            for log in execution.execution_logs:
                if isinstance(log, dict) and log.get("type") in [
                    "tool_call",
                    "mcp_call",
                ]:
                    count += 1

        return count

    def _parse_token_usage(self, execution: models.FlowExecution) -> Dict[str, int]:
        """Parse token usage from codex output logs.

        Looks for pattern: "tokens used\n{number}"

        Args:
            execution: FlowExecution model

        Returns:
            Dictionary with total_tokens, input_tokens, output_tokens
        """
        token_usage = {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0}

        if not execution.execution_logs:
            return token_usage

        # Regex pattern for token usage (supports comma-separated thousands)
        # Pattern: "tokens used" followed by newline and number with optional commas
        pattern = r"tokens used[:\s]*\n\s*(\d{1,3}(?:,\d{3})*)"

        logs_text = ""

        # Build a text corpus from all logs
        if isinstance(execution.execution_logs, list):
            for log in execution.execution_logs:
                if isinstance(log, dict):
                    # Check payload for log messages
                    if "payload" in log and isinstance(log["payload"], dict):
                        payload = log["payload"]

                        # Check for content (used by agent_log_line type)
                        if "content" in payload:
                            logs_text += str(payload["content"]) + "\n"

                        # Check for message (used by other log types)
                        if "message" in payload:
                            logs_text += str(payload["message"]) + "\n"

                        # Also check line (alternative format)
                        if "line" in payload:
                            logs_text += str(payload["line"]) + "\n"

                        # Also check stdout/stderr
                        if "stdout" in payload:
                            logs_text += str(payload["stdout"]) + "\n"
                        if "stderr" in payload:
                            logs_text += str(payload["stderr"]) + "\n"

        # Find all token usage mentions
        matches = re.findall(pattern, logs_text, re.IGNORECASE | re.MULTILINE)

        if matches:
            # Sum all token usages found (remove commas first)
            total = sum(int(match.replace(",", "")) for match in matches)
            token_usage["total_tokens"] = total

            logger.info(
                f"Found {len(matches)} token usage entries in execution {execution.id}, "
                f"total: {total} tokens"
            )

        return token_usage

    def _count_api_requests(self, execution: models.FlowExecution) -> int:
        """Count API requests made during execution timeframe.

        Uses the execution's start_time and end_time to filter ApiUsage records
        by the user who owns the flow.

        Args:
            execution: FlowExecution model

        Returns:
            Number of API requests
        """
        if not execution.start_time:
            return 0

        # Get the flow and its owner
        flow = (
            self.db.query(models.Flow)
            .filter(models.Flow.id == execution.flow_id)
            .first()
        )

        if not flow or not flow.account_id:
            return 0

        # Get the first user in the account (the one who owns the API key)
        account = (
            self.db.query(models.Account)
            .filter(models.Account.id == flow.account_id)
            .first()
        )

        if not account or not account.users:
            return 0

        # Get API usage for the execution timeframe
        query = self.db.query(models.ApiUsage).filter(
            models.ApiUsage.user_id.in_([u.id for u in account.users]),
            models.ApiUsage.timestamp >= execution.start_time,
        )

        if execution.end_time:
            query = query.filter(models.ApiUsage.timestamp <= execution.end_time)

        count = query.count()

        logger.info(
            f"Found {count} API requests for execution {execution.id} "
            f"between {execution.start_time} and {execution.end_time or 'now'}"
        )

        return count

    def _calculate_cost(
        self, execution: models.FlowExecution, token_usage: Dict[str, int]
    ) -> tuple[float, bool]:
        """Calculate estimated cost based on token usage and model pricing.

        Args:
            execution: FlowExecution model
            token_usage: Dictionary with token counts

        Returns:
            Tuple of (estimated_cost, has_pricing_configured)
            - estimated_cost: Cost in USD (0.0 if no pricing configured)
            - has_pricing_configured: True if pricing was found in AI model metadata
        """
        total_cost = 0.0
        has_pricing = False
        total_tokens = token_usage.get("total_tokens", 0)

        if total_tokens == 0:
            return (0.0, False)

        # Get the flow and AI model
        flow = (
            self.db.query(models.Flow)
            .filter(models.Flow.id == execution.flow_id)
            .first()
        )

        if not flow or not flow.ai_model_id:
            # No pricing available - return 0 cost
            return (0.0, False)

        ai_model = (
            self.db.query(models.AIModel)
            .filter(models.AIModel.id == flow.ai_model_id)
            .first()
        )

        if not ai_model:
            return (0.0, False)

        # Check for pricing in meta_data or model_parameters
        pricing = None

        if ai_model.meta_data and isinstance(ai_model.meta_data, dict):
            pricing = ai_model.meta_data.get("pricing")

        if (
            not pricing
            and ai_model.model_parameters
            and isinstance(ai_model.model_parameters, dict)
        ):
            pricing = ai_model.model_parameters.get("pricing")

        if pricing and isinstance(pricing, dict):
            has_pricing = True
            # Calculate based on input/output tokens if available
            input_tokens = token_usage.get("input_tokens", 0)
            output_tokens = token_usage.get("output_tokens", 0)

            input_price_per_1k = pricing.get("input_price_per_1k", 0)
            output_price_per_1k = pricing.get("output_price_per_1k", 0)

            if (
                input_price_per_1k
                and output_price_per_1k
                and (input_tokens or output_tokens)
            ):
                total_cost = (input_tokens / 1000.0) * input_price_per_1k + (
                    output_tokens / 1000.0
                ) * output_price_per_1k
            else:
                # Use average price per token
                price_per_1k = pricing.get("price_per_1k", 0)
                if price_per_1k:
                    total_cost = (total_tokens / 1000.0) * price_per_1k

        if has_pricing:
            logger.info(
                f"Calculated cost for execution {execution.id}: "
                f"${total_cost:.4f} ({total_tokens} tokens)"
            )
        else:
            logger.info(
                f"No pricing configured for execution {execution.id} "
                f"({total_tokens} tokens)"
            )

        return (round(total_cost, 4), has_pricing)
