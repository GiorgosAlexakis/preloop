"""Tool approval evaluation service.

This module provides the logic for determining whether a tool execution
requires approval based on tool configuration and approval conditions.
"""

import uuid
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from preloop.models import models
from preloop.models.crud import tool_approval_condition


def should_require_approval(
    db: Session,
    tool_name: str,
    tool_args: Dict[str, Any],
    account_id: uuid.UUID,
    tool_configuration_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    execution_id: Optional[uuid.UUID] = None,
    trigger_event: Optional[Dict[str, Any]] = None,
) -> tuple[bool, Optional[uuid.UUID], Optional[str]]:
    """Determine if a tool execution requires approval.

    This function implements the approval decision logic:
    1. Check if tool has an approval_policy_id set
    2. If no policy → no approval required
    3. If policy but no condition → always require approval
    4. If policy and condition → evaluate condition expression

    Args:
        db: Database session.
        tool_name: Name of the tool being executed.
        tool_args: Arguments passed to the tool.
        account_id: Account ID.
        tool_configuration_id: Optional tool configuration ID (for lookup).
        user_id: Optional user ID (for condition evaluation context).
        execution_id: Optional execution ID (for condition evaluation context).
        trigger_event: Optional trigger event data (for condition evaluation context).

    Returns:
        Tuple of (requires_approval, approval_policy_id, reason).
        - requires_approval: Whether approval is required.
        - approval_policy_id: Policy ID to use if approval is required.
        - reason: Human-readable reason for the decision.
    """
    # Get tool configuration
    if tool_configuration_id:
        tool_config = (
            db.query(models.ToolConfiguration)
            .filter(
                models.ToolConfiguration.id == tool_configuration_id,
                models.ToolConfiguration.account_id == account_id,
            )
            .first()
        )
    else:
        tool_config = (
            db.query(models.ToolConfiguration)
            .filter(
                models.ToolConfiguration.tool_name == tool_name,
                models.ToolConfiguration.account_id == account_id,
            )
            .first()
        )

    if not tool_config:
        # No configuration found, no approval required
        return False, None, "No tool configuration found"

    if not tool_config.approval_policy_id:
        # No approval policy set, no approval required
        return False, None, "No approval policy configured for this tool"

    # Tool has an approval policy, check if there's a condition
    condition = tool_approval_condition.get_by_tool_configuration(
        db, tool_config.id, account_id
    )

    if not condition or not condition.is_enabled:
        # No condition or disabled condition → always require approval
        return (
            True,
            tool_config.approval_policy_id,
            "Tool requires approval (no condition or condition disabled)",
        )

    # Condition exists and is enabled, evaluate it
    if not condition.condition_expression:
        # Condition exists but no expression → always require approval
        return (
            True,
            tool_config.approval_policy_id,
            "Tool requires approval (condition has no expression)",
        )

    # Evaluate the condition expression
    try:
        matches = _evaluate_condition(
            condition.condition_expression,
            condition.condition_type,
            condition.condition_config or {},
            tool_name=tool_name,
            tool_args=tool_args,
            user_id=user_id,
            account_id=account_id,
            execution_id=execution_id,
            trigger_event=trigger_event,
        )

        if matches:
            return (
                True,
                tool_config.approval_policy_id,
                f"Condition matched: {condition.condition_expression}",
            )
        else:
            return (
                False,
                None,
                f"Condition not matched: {condition.condition_expression}",
            )

    except Exception as e:
        # If evaluation fails, err on the side of caution and require approval
        return (
            True,
            tool_config.approval_policy_id,
            f"Condition evaluation failed: {str(e)}",
        )


def evaluate_cel_expression(expression: str, tool_args: Dict[str, Any]) -> bool:
    """Evaluate a CEL expression for testing purposes.

    This is a simplified version of _evaluate_condition that's used by the
    test endpoint to validate CEL expressions before saving them.

    Args:
        expression: CEL expression to evaluate.
        tool_args: Sample tool arguments to test against.

    Returns:
        True if expression matches, False otherwise.

    Raises:
        Exception: If expression is invalid or evaluation fails.
    """
    from preloop.plugins.argument_evaluator import ArgumentEvaluator

    evaluator = ArgumentEvaluator()

    # Build minimal context for testing
    context = {
        "args": tool_args,
        "tool_name": "test_tool",
        "user_id": None,
        "account_id": None,
        "execution_id": None,
        "trigger_event": {},
    }

    # Evaluate expression
    result = evaluator.evaluate(expression, context)
    return bool(result)


def _evaluate_condition(
    expression: str,
    condition_type: str,
    condition_config: Dict[str, Any],
    tool_name: str,
    tool_args: Dict[str, Any],
    user_id: Optional[uuid.UUID],
    account_id: uuid.UUID,
    execution_id: Optional[uuid.UUID],
    trigger_event: Optional[Dict[str, Any]],
) -> bool:
    """Evaluate a condition expression.

    Args:
        expression: CEL expression to evaluate.
        condition_type: Type of condition evaluator.
        condition_config: Additional configuration.
        tool_name: Name of the tool.
        tool_args: Tool arguments.
        user_id: User ID.
        account_id: Account ID.
        execution_id: Execution ID.
        trigger_event: Trigger event data.

    Returns:
        True if condition matches, False otherwise.
    """
    if condition_type == "argument":
        # Use ArgumentEvaluator plugin for CEL expression evaluation
        from preloop.plugins.argument_evaluator import ArgumentEvaluator

        evaluator = ArgumentEvaluator()

        # Build context for evaluation
        context = {
            "tool_name": tool_name,
            "args": tool_args,
            "user_id": str(user_id) if user_id else None,
            "account_id": str(account_id),
            "execution_id": str(execution_id) if execution_id else None,
            "trigger_event": trigger_event or {},
        }

        # Evaluate expression
        result = evaluator.evaluate(expression, context)
        return bool(result)

    elif condition_type == "state":
        # State-based evaluation (future implementation)
        # Could check system state, time of day, environment, etc.
        raise NotImplementedError("State-based conditions not yet implemented")

    elif condition_type == "risk":
        # Risk-based evaluation (future implementation)
        # Could use ML model to assess risk score
        raise NotImplementedError("Risk-based conditions not yet implemented")

    else:
        raise ValueError(f"Unknown condition type: {condition_type}")
