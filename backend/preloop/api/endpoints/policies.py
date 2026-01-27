"""Policies router for managing YAML-based policy definitions.

This module provides API endpoints for declarative policy-as-code management:
- Upload and apply YAML/JSON policy files
- Export current configuration as YAML policy
- Preview changes (diff) before applying
- Validate policy files without applying
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from preloop.api.common import get_account_for_user
from preloop.models.db.session import get_db_session
from preloop.models.models.account import Account
from preloop.services.policy import (
    PolicyApplier,
    PolicyDiffResult,
    PolicyDocument,
    PolicyImportResult,
    PolicyValidationResult,
    compute_policy_diff,
    export_current_policy,
    export_policy_to_json,
    export_policy_to_yaml,
    load_policy_from_string,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/policies/validate",
    response_model=PolicyValidationResult,
    summary="Validate a policy file",
    description="Validate a YAML/JSON policy file without applying any changes.",
)
async def validate_policy(
    file: UploadFile = File(..., description="YAML or JSON policy file to validate"),
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> PolicyValidationResult:
    """Validate a policy file without applying changes.

    This endpoint parses and validates the policy file against the schema,
    checking for:
    - Valid YAML/JSON syntax
    - Required fields
    - Valid references (approval policies, MCP servers)
    - Expression syntax

    Args:
        file: The policy file to validate (YAML or JSON).
        account: Current user's account.
        db: Database session.

    Returns:
        PolicyValidationResult with validation status and any errors.
    """
    # Read file content
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
    except UnicodeDecodeError as e:
        logger.warning(f"Failed to decode policy file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded text",
        )

    # Determine format from filename
    filename = file.filename or ""
    if filename.lower().endswith(".json"):
        format = "json"
    else:
        format = "yaml"

    # Validate the policy
    policy, result = load_policy_from_string(content_str, format=format)

    if policy:
        logger.info(
            f"Policy '{policy.metadata.name}' validated successfully "
            f"for account {account.id}"
        )

    return result


@router.post(
    "/policies/upload",
    response_model=PolicyImportResult,
    summary="Upload and apply a policy file",
    description="Upload a YAML/JSON policy file and apply it to your account.",
)
async def upload_policy(
    file: UploadFile = File(..., description="YAML or JSON policy file to apply"),
    dry_run: bool = Form(
        False, description="If true, validate only without making changes"
    ),
    resolve_env: bool = Form(
        True, description="If true, resolve ${VAR} environment variable references"
    ),
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> PolicyImportResult:
    """Upload and apply a policy file.

    This endpoint:
    1. Parses and validates the policy file
    2. Creates/updates MCP servers defined in the policy
    3. Creates/updates approval policies
    4. Creates/updates tool configurations
    5. Applies default behavior settings

    Args:
        file: The policy file to apply (YAML or JSON).
        dry_run: If True, validate without applying changes.
        resolve_env: If True, resolve environment variable references.
        account: Current user's account.
        db: Database session.

    Returns:
        PolicyImportResult with details of what was created/updated.

    Raises:
        HTTPException: If validation fails or application fails.
    """
    # Read file content
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
    except UnicodeDecodeError as e:
        logger.warning(f"Failed to decode policy file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded text",
        )

    # Determine format from filename
    filename = file.filename or ""
    if filename.lower().endswith(".json"):
        format = "json"
    else:
        format = "yaml"

    # Load and validate the policy
    policy, validation_result = load_policy_from_string(content_str, format=format)

    if not validation_result.is_valid or policy is None:
        logger.warning(
            f"Policy validation failed for account {account.id}: "
            f"{validation_result.errors}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Policy validation failed",
                "errors": [e.model_dump() for e in validation_result.errors],
            },
        )

    # Apply the policy
    applier = PolicyApplier(db, account_id=account.id)
    result = applier.apply(policy, dry_run=dry_run, resolve_env=resolve_env)

    if not result.success:
        logger.error(
            f"Failed to apply policy '{policy.metadata.name}' for account {account.id}: "
            f"{result.errors}"
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Failed to apply policy",
                "errors": result.errors,
                "warnings": result.warnings,
            },
        )

    action = "validated (dry run)" if dry_run else "applied"
    logger.info(
        f"Policy '{policy.metadata.name}' {action} for account {account.id}: "
        f"{result.mcp_servers_created + result.mcp_servers_updated} servers, "
        f"{result.policies_created + result.policies_updated} policies, "
        f"{result.tools_created + result.tools_updated} tools"
    )

    return result


@router.get(
    "/policies/export",
    summary="Export current configuration as policy",
    description=(
        "Export your current MCP servers, approval policies, and tool "
        "configurations as a YAML or JSON policy file."
    ),
)
async def export_policy(
    format: Literal["yaml", "json"] = "yaml",
    policy_name: str = "Exported Policy",
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> Response:
    """Export current configuration as a policy file.

    This endpoint exports:
    - MCP server configurations (without auth credentials)
    - Approval policies
    - Tool configurations with approval conditions

    Args:
        format: Output format ('yaml' or 'json').
        policy_name: Name to give the exported policy.
        account: Current user's account.
        db: Database session.

    Returns:
        YAML or JSON file response.
    """
    # Export current configuration
    policy = export_current_policy(db, account_id=account.id, policy_name=policy_name)

    # Convert to requested format
    if format == "json":
        content = export_policy_to_json(policy)
        media_type = "application/json"
        filename = "policy.json"
    else:
        content = export_policy_to_yaml(policy)
        media_type = "application/x-yaml"
        filename = "policy.yaml"

    logger.info(f"Exported policy for account {account.id} as {format}")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/policies/diff",
    response_model=PolicyDiffResult,
    summary="Preview changes from a policy file",
    description=(
        "Compare an uploaded policy file with your current configuration "
        "to see what would change."
    ),
)
async def diff_policy(
    file: UploadFile = File(..., description="YAML or JSON policy file to compare"),
    account: Account = Depends(get_account_for_user),
    db: Session = Depends(get_db_session),
) -> PolicyDiffResult:
    """Compare uploaded policy with current configuration.

    This endpoint shows what would change if the policy were applied:
    - Added items (new servers, policies, tools)
    - Removed items (items in current config but not in policy)
    - Modified items (items with different settings)

    Note: This does NOT apply any changes - use POST /policies/upload for that.

    Args:
        file: The policy file to compare (YAML or JSON).
        account: Current user's account.
        db: Database session.

    Returns:
        PolicyDiffResult showing all differences.

    Raises:
        HTTPException: If validation fails.
    """
    # Read file content
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
    except UnicodeDecodeError as e:
        logger.warning(f"Failed to decode policy file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded text",
        )

    # Determine format from filename
    filename = file.filename or ""
    if filename.lower().endswith(".json"):
        format = "json"
    else:
        format = "yaml"

    # Load and validate the incoming policy
    incoming_policy, validation_result = load_policy_from_string(
        content_str, format=format
    )

    if not validation_result.is_valid or incoming_policy is None:
        logger.warning(
            f"Policy validation failed for diff, account {account.id}: "
            f"{validation_result.errors}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Policy validation failed",
                "errors": [e.model_dump() for e in validation_result.errors],
            },
        )

    # Export current configuration as a policy document
    current_policy = export_current_policy(
        db, account_id=account.id, policy_name="Current Configuration"
    )

    # Compute diff
    diff_result = compute_policy_diff(current_policy, incoming_policy)

    logger.info(f"Computed policy diff for account {account.id}: {diff_result.summary}")

    return diff_result


@router.get(
    "/policies/schema",
    summary="Get policy schema documentation",
    description="Get the JSON schema for policy files with documentation.",
)
async def get_policy_schema() -> dict:
    """Get the JSON schema for policy files.

    This endpoint returns the JSON schema that describes the structure
    of policy files, including:
    - All available fields and their types
    - Required vs optional fields
    - Enum values for constrained fields
    - Field descriptions

    This schema can be used for:
    - IDE autocompletion (with YAML/JSON language servers)
    - Documentation
    - Custom validation

    Returns:
        JSON schema for PolicyDocument.
    """
    schema = PolicyDocument.model_json_schema()

    # Add helpful metadata
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    schema["title"] = "Preloop Policy Schema"
    schema["description"] = (
        "Schema for Preloop policy-as-code YAML/JSON files. "
        "Define MCP servers, approval policies, tool configurations, and defaults."
    )

    return schema
