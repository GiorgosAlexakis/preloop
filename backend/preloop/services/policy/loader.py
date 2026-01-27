"""Policy loader for loading and validating YAML/JSON policy files.

This module provides functionality to:
- Load policy documents from YAML or JSON files/strings
- Validate policies against the schema
- Apply policies to the database (create/update entities)
- Export current configuration as a policy document
- Compute diffs between policies
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import yaml
from pydantic import ValidationError
from sqlalchemy.orm import Session

from preloop.services.policy.schema import (
    ApprovalPolicyDefinition,
    ConditionAction,
    DefaultsDefinition,
    MCPServerDefinition,
    PolicyDiffItem,
    PolicyDiffResult,
    PolicyDocument,
    PolicyImportResult,
    PolicyMetadata,
    PolicyValidationError,
    PolicyValidationResult,
    PolicyVersion,
    ToolCondition,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class PolicyLoadError(Exception):
    """Exception raised when policy loading fails."""

    def __init__(
        self, message: str, errors: Optional[List[PolicyValidationError]] = None
    ):
        super().__init__(message)
        self.errors = errors or []


def load_policy_from_string(
    content: str,
    format: str = "yaml",
) -> Tuple[Optional[PolicyDocument], PolicyValidationResult]:
    """Load a policy document from a string.

    Args:
        content: The policy content as a string.
        format: Format of the content ('yaml' or 'json').

    Returns:
        Tuple of (PolicyDocument or None, PolicyValidationResult).
        If validation fails, PolicyDocument will be None.
    """
    errors: List[PolicyValidationError] = []
    warnings: List[str] = []

    # Parse the content
    try:
        if format.lower() == "json":
            data = json.loads(content)
        else:
            data = yaml.safe_load(content)
    except json.JSONDecodeError as e:
        errors.append(
            PolicyValidationError(
                path="$",
                message=f"Invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}",
                value=None,
            )
        )
        return None, PolicyValidationResult(is_valid=False, errors=errors)
    except yaml.YAMLError as e:
        error_msg = str(e)
        if hasattr(e, "problem_mark"):
            mark = e.problem_mark
            error_msg = (
                f"Invalid YAML at line {mark.line + 1}, "
                f"column {mark.column + 1}: {e.problem}"
            )
        errors.append(
            PolicyValidationError(
                path="$",
                message=error_msg,
                value=None,
            )
        )
        return None, PolicyValidationResult(is_valid=False, errors=errors)

    if data is None:
        errors.append(
            PolicyValidationError(
                path="$",
                message="Empty policy document",
                value=None,
            )
        )
        return None, PolicyValidationResult(is_valid=False, errors=errors)

    # Validate against schema
    try:
        policy = PolicyDocument.model_validate(data)
    except ValidationError as e:
        for error in e.errors():
            path = ".".join(str(loc) for loc in error["loc"])
            errors.append(
                PolicyValidationError(
                    path=f"$.{path}" if path else "$",
                    message=error["msg"],
                    value=error.get("input"),
                )
            )
        return None, PolicyValidationResult(is_valid=False, errors=errors)

    # Add warnings for deprecated or unusual configurations
    if policy.tools:
        for tool in policy.tools:
            if tool.conditions and not tool.approval_policy:
                warnings.append(
                    f"Tool '{tool.name}' has conditions but no approval_policy set. "
                    "Conditions with 'require_approval' action will have no effect."
                )

    return policy, PolicyValidationResult(is_valid=True, errors=[], warnings=warnings)


def load_policy_from_file(
    file_path: str,
) -> Tuple[Optional[PolicyDocument], PolicyValidationResult]:
    """Load a policy document from a file.

    Args:
        file_path: Path to the policy file.

    Returns:
        Tuple of (PolicyDocument or None, PolicyValidationResult).

    Raises:
        PolicyLoadError: If the file cannot be read.
    """
    if not os.path.exists(file_path):
        return None, PolicyValidationResult(
            is_valid=False,
            errors=[
                PolicyValidationError(
                    path="$",
                    message=f"File not found: {file_path}",
                    value=None,
                )
            ],
        )

    # Determine format from extension
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".json"]:
        format = "json"
    elif ext in [".yaml", ".yml"]:
        format = "yaml"
    else:
        format = "yaml"  # Default to YAML

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as e:
        return None, PolicyValidationResult(
            is_valid=False,
            errors=[
                PolicyValidationError(
                    path="$",
                    message=f"Failed to read file: {e}",
                    value=None,
                )
            ],
        )

    return load_policy_from_string(content, format=format)


def export_policy_to_yaml(policy: PolicyDocument) -> str:
    """Export a policy document to YAML string.

    Args:
        policy: The policy document to export.

    Returns:
        YAML string representation.
    """
    # Convert to dict, excluding None values for cleaner output
    # mode='json' ensures enums are serialized as their values, not Python objects
    data = policy.model_dump(exclude_none=True, mode="json")

    # Use safe_dump to avoid Python-specific YAML tags
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


def export_policy_to_json(policy: PolicyDocument, indent: int = 2) -> str:
    """Export a policy document to JSON string.

    Args:
        policy: The policy document to export.
        indent: Indentation level for pretty printing.

    Returns:
        JSON string representation.
    """
    return policy.model_dump_json(exclude_none=True, indent=indent)


def compute_policy_diff(
    current: PolicyDocument,
    incoming: PolicyDocument,
) -> PolicyDiffResult:
    """Compute the diff between two policy documents.

    Args:
        current: The current/existing policy.
        incoming: The incoming/new policy.

    Returns:
        PolicyDiffResult with list of changes.
    """
    changes: List[PolicyDiffItem] = []

    # Helper to compare lists by name
    def diff_named_lists(
        path: str,
        current_items: Optional[List[Any]],
        incoming_items: Optional[List[Any]],
        name_field: str = "name",
    ) -> None:
        current_map = {
            getattr(item, name_field): item for item in (current_items or [])
        }
        incoming_map = {
            getattr(item, name_field): item for item in (incoming_items or [])
        }

        # Removed items
        for name in set(current_map.keys()) - set(incoming_map.keys()):
            changes.append(
                PolicyDiffItem(
                    path=f"{path}[name={name}]",
                    operation="remove",
                    old_value=current_map[name].model_dump(exclude_none=True),
                    new_value=None,
                )
            )

        # Added items
        for name in set(incoming_map.keys()) - set(current_map.keys()):
            changes.append(
                PolicyDiffItem(
                    path=f"{path}[name={name}]",
                    operation="add",
                    old_value=None,
                    new_value=incoming_map[name].model_dump(exclude_none=True),
                )
            )

        # Modified items
        for name in set(current_map.keys()) & set(incoming_map.keys()):
            current_dict = current_map[name].model_dump(exclude_none=True)
            incoming_dict = incoming_map[name].model_dump(exclude_none=True)
            if current_dict != incoming_dict:
                changes.append(
                    PolicyDiffItem(
                        path=f"{path}[name={name}]",
                        operation="modify",
                        old_value=current_dict,
                        new_value=incoming_dict,
                    )
                )

    # Compare metadata
    if current.metadata.model_dump(exclude_none=True) != incoming.metadata.model_dump(
        exclude_none=True
    ):
        changes.append(
            PolicyDiffItem(
                path="$.metadata",
                operation="modify",
                old_value=current.metadata.model_dump(exclude_none=True),
                new_value=incoming.metadata.model_dump(exclude_none=True),
            )
        )

    # Compare MCP servers
    diff_named_lists("$.mcp_servers", current.mcp_servers, incoming.mcp_servers)

    # Compare approval policies
    diff_named_lists(
        "$.approval_policies", current.approval_policies, incoming.approval_policies
    )

    # Compare tools
    diff_named_lists("$.tools", current.tools, incoming.tools)

    # Compare defaults
    current_defaults = (
        current.defaults.model_dump(exclude_none=True) if current.defaults else {}
    )
    incoming_defaults = (
        incoming.defaults.model_dump(exclude_none=True) if incoming.defaults else {}
    )
    if current_defaults != incoming_defaults:
        changes.append(
            PolicyDiffItem(
                path="$.defaults",
                operation="modify" if current_defaults else "add",
                old_value=current_defaults or None,
                new_value=incoming_defaults or None,
            )
        )

    # Generate summary
    add_count = sum(1 for c in changes if c.operation == "add")
    remove_count = sum(1 for c in changes if c.operation == "remove")
    modify_count = sum(1 for c in changes if c.operation == "modify")

    summary_parts = []
    if add_count:
        summary_parts.append(f"{add_count} addition(s)")
    if remove_count:
        summary_parts.append(f"{remove_count} removal(s)")
    if modify_count:
        summary_parts.append(f"{modify_count} modification(s)")

    summary = ", ".join(summary_parts) if summary_parts else "No changes"

    return PolicyDiffResult(
        has_changes=len(changes) > 0,
        changes=changes,
        summary=summary,
    )


def resolve_env_vars(value: Any) -> Any:
    """Recursively resolve environment variable references in values.

    Supports ${VAR_NAME} syntax for environment variable substitution.

    Args:
        value: The value to process (can be dict, list, or scalar).

    Returns:
        The value with environment variables resolved.
    """
    if isinstance(value, str):
        # Match ${VAR_NAME} pattern
        import re

        pattern = r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"

        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(pattern, replacer, value)
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    else:
        return value


class PolicyApplier:
    """Apply a policy document to the database.

    This class handles the creation and update of database entities
    based on a policy document.
    """

    def __init__(self, db: Session, account_id: Union[str, UUID]):
        """Initialize the policy applier.

        Args:
            db: SQLAlchemy database session.
            account_id: The account ID to apply the policy to.
        """
        self.db = db
        self.account_id = str(account_id)

        # Track created entities for rollback and reporting
        self._result = PolicyImportResult(
            success=False,
            policy_name="",
        )

        # Caches for lookups
        self._mcp_server_map: Dict[str, UUID] = {}
        self._policy_map: Dict[str, UUID] = {}

    def apply(
        self,
        policy: PolicyDocument,
        dry_run: bool = False,
        resolve_env: bool = True,
    ) -> PolicyImportResult:
        """Apply a policy document to the database.

        Args:
            policy: The policy document to apply.
            dry_run: If True, validate only without making changes.
            resolve_env: If True, resolve environment variable references.

        Returns:
            PolicyImportResult with details of what was created/updated.
        """
        self._result.policy_name = policy.metadata.name

        try:
            # Resolve environment variables if requested
            if resolve_env:
                policy_dict = resolve_env_vars(policy.model_dump())
                policy = PolicyDocument.model_validate(policy_dict)

            # Apply in order: servers, policies, tools, defaults
            if policy.mcp_servers:
                self._apply_mcp_servers(policy.mcp_servers, dry_run)

            if policy.approval_policies:
                self._apply_approval_policies(policy.approval_policies, dry_run)

            if policy.tools:
                self._apply_tools(policy.tools, dry_run)

            if policy.defaults:
                self._apply_defaults(policy.defaults, dry_run)

            if not dry_run:
                self.db.commit()

            self._result.success = True

        except Exception as e:
            logger.error(f"Failed to apply policy: {e}", exc_info=True)
            self._result.errors.append(str(e))
            if not dry_run:
                self.db.rollback()

        return self._result

    def _apply_mcp_servers(
        self,
        servers: List[MCPServerDefinition],
        dry_run: bool,
    ) -> None:
        """Apply MCP server definitions."""
        from preloop.models.crud import crud_mcp_server
        from preloop.models.models.mcp_server import MCPServer

        for server_def in servers:
            # Check if server exists by name
            existing = crud_mcp_server.get_by_name(
                self.db, account_id=self.account_id, name=server_def.name
            )

            if existing:
                # Update existing server
                if not dry_run:
                    existing.url = server_def.url
                    existing.transport = server_def.transport
                    existing.auth_type = server_def.auth_type
                    if server_def.auth_config:
                        existing.auth_config = server_def.auth_config
                self._mcp_server_map[server_def.name] = existing.id
                self._result.mcp_servers_updated += 1
                logger.info(f"Updated MCP server: {server_def.name}")
            else:
                # Create new server
                if not dry_run:
                    new_server = MCPServer(
                        account_id=self.account_id,
                        name=server_def.name,
                        url=server_def.url,
                        transport=server_def.transport,
                        auth_type=server_def.auth_type,
                        auth_config=server_def.auth_config,
                        status="active",
                    )
                    self.db.add(new_server)
                    self.db.flush()  # Get the ID
                    self._mcp_server_map[server_def.name] = new_server.id
                self._result.mcp_servers_created += 1
                logger.info(f"Created MCP server: {server_def.name}")

    def _apply_approval_policies(
        self,
        policies: List[ApprovalPolicyDefinition],
        dry_run: bool,
    ) -> None:
        """Apply approval policy definitions.

        Note: notification_channels is no longer used. Approvers configure their
        own notification preferences in user settings.
        """
        from preloop.models.crud import crud_approval_policy
        from preloop.models.models.tool_configuration import ApprovalPolicy

        for policy_def in policies:
            # Check if policy exists by name
            existing = crud_approval_policy.get_by_name(
                self.db, account_id=self.account_id, name=policy_def.name
            )

            if existing:
                # Update existing policy
                if not dry_run:
                    existing.description = policy_def.description
                    existing.timeout_seconds = policy_def.timeout_seconds
                    existing.require_reason = policy_def.require_reason
                    existing.is_default = policy_def.is_default
                    existing.workflow_type = policy_def.workflow_type
                    existing.approvals_required = policy_def.approvals_required
                    if policy_def.channel_configs:
                        existing.channel_configs = policy_def.channel_configs
                    # Note: user/team references would need resolution here
                self._policy_map[policy_def.name] = existing.id
                self._result.policies_updated += 1
                logger.info(f"Updated approval policy: {policy_def.name}")
            else:
                # Create new policy
                if not dry_run:
                    new_policy = ApprovalPolicy(
                        account_id=self.account_id,
                        name=policy_def.name,
                        description=policy_def.description,
                        approval_type="manual",  # Default for YAML-defined policies
                        timeout_seconds=policy_def.timeout_seconds,
                        require_reason=policy_def.require_reason,
                        is_default=policy_def.is_default,
                        workflow_type=policy_def.workflow_type,
                        approvals_required=policy_def.approvals_required,
                        channel_configs=policy_def.channel_configs,
                    )
                    self.db.add(new_policy)
                    self.db.flush()
                    self._policy_map[policy_def.name] = new_policy.id
                self._result.policies_created += 1
                logger.info(f"Created approval policy: {policy_def.name}")

    def _apply_tools(
        self,
        tools: List[ToolDefinition],
        dry_run: bool,
    ) -> None:
        """Apply tool configuration definitions."""
        from preloop.models.crud import crud_tool_configuration
        from preloop.models.models.tool_configuration import ToolConfiguration

        for tool_def in tools:
            # Determine tool source and MCP server ID
            source_lower = tool_def.source.lower()
            if source_lower in ["builtin", "http"]:
                tool_source = source_lower
                mcp_server_id = None
            elif source_lower == "mcp":
                # Generic MCP source (requires mcp_server_id to be set elsewhere)
                tool_source = "mcp"
                mcp_server_id = None
                self._result.warnings.append(
                    f"Tool '{tool_def.name}' has source 'mcp' but no server specified. "
                    "Use a specific server name instead."
                )
            else:
                # It's a server name reference
                tool_source = "mcp"
                if tool_def.source in self._mcp_server_map:
                    mcp_server_id = self._mcp_server_map[tool_def.source]
                else:
                    # Try to find in database
                    from preloop.models.crud import crud_mcp_server

                    server = crud_mcp_server.get_by_name(
                        self.db, account_id=self.account_id, name=tool_def.source
                    )
                    if server:
                        mcp_server_id = server.id
                    else:
                        self._result.warnings.append(
                            f"MCP server '{tool_def.source}' not found "
                            f"for tool '{tool_def.name}'"
                        )
                        mcp_server_id = None

            # Look up approval policy ID
            approval_policy_id = None
            if tool_def.approval_policy:
                if tool_def.approval_policy in self._policy_map:
                    approval_policy_id = self._policy_map[tool_def.approval_policy]
                else:
                    # Try to find in database
                    from preloop.models.crud import crud_approval_policy

                    policy = crud_approval_policy.get_by_name(
                        self.db,
                        account_id=self.account_id,
                        name=tool_def.approval_policy,
                    )
                    if policy:
                        approval_policy_id = policy.id
                    else:
                        self._result.warnings.append(
                            f"Approval policy '{tool_def.approval_policy}' not found "
                            f"for tool '{tool_def.name}'"
                        )

            # Check if tool config exists
            existing = crud_tool_configuration.get_by_tool_name_and_source(
                self.db,
                account_id=self.account_id,
                tool_name=tool_def.name,
                tool_source=tool_source,
            )

            if existing:
                # Update existing config
                if not dry_run:
                    existing.is_enabled = tool_def.enabled
                    existing.approval_policy_id = approval_policy_id
                    if tool_def.description:
                        existing.tool_description = tool_def.description
                    if tool_def.custom_config:
                        existing.custom_config = tool_def.custom_config
                    if mcp_server_id:
                        existing.mcp_server_id = mcp_server_id

                    # Handle conditions
                    if tool_def.conditions:
                        self._apply_tool_conditions(
                            existing.id, tool_def.conditions, dry_run
                        )

                self._result.tools_updated += 1
                logger.info(f"Updated tool config: {tool_def.name}")
            else:
                # Create new config
                if not dry_run:
                    new_config = ToolConfiguration(
                        account_id=self.account_id,
                        tool_name=tool_def.name,
                        tool_source=tool_source,
                        mcp_server_id=mcp_server_id,
                        is_enabled=tool_def.enabled,
                        approval_policy_id=approval_policy_id,
                        tool_description=tool_def.description,
                        custom_config=tool_def.custom_config,
                    )
                    self.db.add(new_config)
                    self.db.flush()

                    # Handle conditions
                    if tool_def.conditions:
                        self._apply_tool_conditions(
                            new_config.id, tool_def.conditions, dry_run
                        )

                self._result.tools_created += 1
                logger.info(f"Created tool config: {tool_def.name}")

    def _apply_tool_conditions(
        self,
        tool_config_id: UUID,
        conditions: List[ToolCondition],
        dry_run: bool,
    ) -> None:
        """Apply tool approval conditions.

        Note: Currently supports a single condition per tool (1:1 relationship).
        Multiple conditions are combined with OR logic into a single expression.
        """
        from preloop.models.crud import tool_approval_condition
        from preloop.models.models.tool_approval_condition import ToolApprovalCondition

        if not conditions:
            return

        # Combine multiple conditions into a single CEL expression with OR
        # Only include conditions that require approval
        approval_conditions = [
            c
            for c in conditions
            if c.action in [ConditionAction.REQUIRE_APPROVAL, "require_approval"]
        ]

        if not approval_conditions:
            return

        if len(approval_conditions) == 1:
            expression = approval_conditions[0].expression
        else:
            # Combine with OR
            expression = " || ".join(f"({c.expression})" for c in approval_conditions)

        # Get or create the condition
        existing = tool_approval_condition.get_by_tool_configuration(
            self.db,
            tool_configuration_id=tool_config_id,
            account_id=self.account_id,
        )

        if existing:
            if not dry_run:
                existing.condition_expression = expression
                existing.is_enabled = True
        else:
            if not dry_run:
                new_condition = ToolApprovalCondition(
                    account_id=self.account_id,
                    tool_configuration_id=tool_config_id,
                    condition_type="argument",
                    condition_expression=expression,
                    is_enabled=True,
                )
                self.db.add(new_condition)

    def _apply_defaults(
        self,
        defaults: DefaultsDefinition,
        dry_run: bool,
    ) -> None:
        """Apply default behavior settings.

        Note: Defaults are stored at the account level and may require
        custom handling depending on your account model.
        """
        # TODO: Implement default settings storage
        # This might involve:
        # 1. An account_settings table
        # 2. A dedicated defaults column on the account table
        # 3. Creating catch-all tool configurations
        logger.info(
            f"Default settings would be applied: unknown_tools={defaults.unknown_tools}"
        )
        pass


def export_current_policy(
    db: Session,
    account_id: Union[str, UUID],
    policy_name: str = "Exported Policy",
) -> PolicyDocument:
    """Export the current configuration as a policy document.

    Args:
        db: SQLAlchemy database session.
        account_id: The account ID to export from.
        policy_name: Name for the exported policy.

    Returns:
        PolicyDocument representing the current configuration.
    """
    from datetime import datetime, timezone

    from preloop.models.crud import (
        crud_approval_policy,
        crud_mcp_server,
        crud_tool_configuration,
    )

    account_id_str = str(account_id)

    # Export MCP servers
    mcp_servers = crud_mcp_server.get_active_by_account(db, account_id=account_id_str)
    server_defs = [
        MCPServerDefinition(
            name=server.name,
            url=server.url,
            transport=server.transport,
            auth_type=server.auth_type,
            # Don't export auth_config for security
        )
        for server in mcp_servers
    ]

    # Export approval policies
    policies = crud_approval_policy.get_multi_by_account(db, account_id=account_id_str)
    policy_defs = [
        ApprovalPolicyDefinition(
            name=policy.name,
            description=policy.description,
            timeout_seconds=policy.timeout_seconds,
            require_reason=policy.require_reason,
            is_default=policy.is_default,
            workflow_type=policy.workflow_type,
            approvals_required=policy.approvals_required,
            channel_configs=policy.channel_configs,
        )
        for policy in policies
    ]

    # Build policy name lookup
    policy_name_map = {str(p.id): p.name for p in policies}
    server_name_map = {str(s.id): s.name for s in mcp_servers}

    # Export tool configurations
    tool_configs = crud_tool_configuration.get_multi_by_account(
        db, account_id=account_id_str
    )
    tool_defs = []

    for config in tool_configs:
        # Determine source name
        if config.tool_source == "mcp" and config.mcp_server_id:
            source = server_name_map.get(str(config.mcp_server_id), "mcp")
        else:
            source = config.tool_source

        # Get approval conditions
        conditions = []
        if config.approval_condition:
            cond = config.approval_condition
            if cond.condition_expression:
                conditions.append(
                    ToolCondition(
                        expression=cond.condition_expression,
                        action=ConditionAction.REQUIRE_APPROVAL,
                        description=cond.description,
                    )
                )

        tool_def = ToolDefinition(
            name=config.tool_name,
            source=source,
            enabled=config.is_enabled,
            approval_policy=policy_name_map.get(str(config.approval_policy_id))
            if config.approval_policy_id
            else None,
            conditions=conditions if conditions else None,
            description=config.tool_description,
            custom_config=config.custom_config,
        )
        tool_defs.append(tool_def)

    return PolicyDocument(
        version=PolicyVersion.V1_0,
        metadata=PolicyMetadata(
            name=policy_name,
            description="Exported from current configuration",
            created_at=datetime.now(timezone.utc),
        ),
        mcp_servers=server_defs if server_defs else None,
        approval_policies=policy_defs if policy_defs else None,
        tools=tool_defs if tool_defs else None,
        defaults=DefaultsDefinition(),  # Default settings
    )
