"""Common utility functions for the SpaceBridge API."""

import logging
from typing import Any, Dict, Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from spacebridge.schemas.issue_compliance import CompliancePromptMetadata
from spacesync.spacesync.trackers import create_tracker_client
from spacemodels.crud import (
    CRUDOrganization,
    CRUDProject,
    crud_tracker_scope_rule,
)
from spacemodels.models.account import Account
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
import yaml
import os

logger = logging.getLogger(__name__)

# Initialize CRUD operations
crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)


async def get_tracker_client(
    organization_id: str, project_id: str, db: Session, current_user: Account
):
    """Get the appropriate tracker client for the given organization and project,
    ensuring the current user has access.

    Args:
        organization_id: The organization ID or identifier.
        project_id: The project ID or identifier.
        db: Database session.
        current_user: The authenticated user account.

    Returns:
        A tracker client instance.

    Raises:
        HTTPException: If the organization or project is not found, if the user
            does not have access, or if a tracker client cannot be created.
    """
    # Check if organization_id is a UUID or an identifier
    if len(organization_id) == 36:  # Simple UUID check
        organization = crud_organization.get(
            db, id=organization_id, account_id=current_user.id
        )
    else:
        organization = crud_organization.get_by_identifier(
            db, identifier=organization_id, account_id=current_user.id
        )

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Resolve project
    project: Optional[Project] = None
    if len(project_id) == 36:  # Check if project_id looks like a UUID (our internal ID)
        project = crud_project.get(db, id=project_id, account_id=current_user.id)
        # Verify it belongs to the correct organization
        if project and project.organization_id != organization.id:
            logger.warning(
                f"Project ID {project_id} found but belongs to wrong org ({project.organization_id} != {organization.id})"
            )
            project = None  # Treat as not found in this context
    else:
        # Assume project_id is a slug or identifier if not a UUID
        project_list = crud_project.get_by_slug_or_identifier(
            db,
            organization_id=organization.id,
            slug_or_identifier=project_id,
            account_id=current_user.id,
        )
        if len(project_list) == 1:
            project = project_list[0]
        elif len(project_list) > 1:
            # This shouldn't happen if org is specified, but handle defensively
            logger.error(
                f"Ambiguous project identifier '{project_id}' within organization '{organization.identifier}'."
            )
            raise HTTPException(
                status_code=400,
                detail=f"Ambiguous project identifier '{project_id}' within organization.",
            )

    if not project:
        # If project is still None after trying ID and slug/identifier
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_id}' not found within organization '{organization.identifier}'.",
        )

    # Get tracker details from the organization
    tracker = organization.tracker
    if not tracker:
        raise HTTPException(
            status_code=500, detail="Organization has no associated tracker."
        )

    # --- Authorization Check ---
    if tracker.account_id != current_user.id:
        logger.warning(
            f"Access denied: User {current_user.username} (Account ID: {current_user.id}) "
            f"attempted to access tracker {tracker.id} (Account ID: {tracker.account_id})."
        )
        raise HTTPException(
            status_code=403, detail="Forbidden: Access denied to this resource."
        )
    # --- End Authorization Check ---

    # --- New Scoping Logic ---
    scope_rules = crud_tracker_scope_rule.get_by_tracker(
        db, tracker_id=tracker.id, account_id=current_user.id
    )

    org_identifier = organization.identifier
    project_identifier = project.identifier

    org_rules = [rule for rule in scope_rules if rule.scope_type == "ORGANIZATION"]
    project_rules = [rule for rule in scope_rules if rule.scope_type == "PROJECT"]

    # Rule 1: Organization must be included
    org_included = any(
        rule.rule_type == "INCLUDE" and rule.identifier == org_identifier
        for rule in org_rules
    )
    org_excluded = any(
        rule.rule_type == "EXCLUDE" and rule.identifier == org_identifier
        for rule in org_rules
    )

    if org_excluded:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Organization is explicitly excluded.",
        )
    if not org_included:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Organization is not included in tracker scope.",
        )

    # Rule 2: Project must not be excluded
    project_excluded = any(
        rule.rule_type == "EXCLUDE" and rule.identifier == project_identifier
        for rule in project_rules
    )
    if project_excluded:
        raise HTTPException(
            status_code=403, detail="Access denied: Project is explicitly excluded."
        )

    # Rule 3: If project-level includes exist, project must be in the list
    project_level_includes = [
        rule for rule in project_rules if rule.rule_type == "INCLUDE"
    ]
    if project_level_includes:
        project_included = any(
            rule.identifier == project_identifier for rule in project_level_includes
        )
        if not project_included:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Project is not in the tracker's include list.",
            )
    # --- End New Scoping Logic ---

    tracker_type = tracker.tracker_type

    # --- Assemble the full configuration ---
    # This will be passed as connection_details to the tracker client
    # Start with project-specific tracker settings from the database
    full_config: Dict[str, Any] = project.tracker_settings or {}

    # Add URL and other connection details from the main tracker object
    # The token/api_key is passed separately to the factory
    if tracker.url:
        full_config["url"] = tracker.url

    # Merge any other connection details from the tracker model's JSON field
    if tracker.connection_details:
        for key, value in tracker.connection_details.items():
            # Avoid overwriting settings that might have been set at the project level
            if key not in full_config:
                full_config[key] = value

    # Ensure project-specific identifiers are included, checking settings/metadata/identifier
    if tracker_type == "gitlab":
        if "project_id" not in full_config:
            # Check tracker_settings, then meta_data, then use project.identifier
            full_config["project_id"] = (
                (project.tracker_settings or {}).get("project_id")
                or (project.meta_data or {}).get("project_id")
                or project.identifier
            )
    elif tracker_type == "github":
        full_config["owner"] = organization.name
        full_config["repo"] = project.name
    elif tracker_type == "jira":
        # Jira might need project_key in config for some operations, add if available
        if "project_key" not in full_config:
            full_config["project_key"] = (
                (project.tracker_settings or {}).get("project_key")
                or (project.meta_data or {}).get("project_key")
                or project.identifier
            )

    logger.debug(
        f"Creating tracker client of type '{tracker_type}' with config: {full_config}"
    )

    try:
        # Create the tracker client using the combined config
        tracker_client = await create_tracker_client(
            tracker_type=tracker_type,
            tracker_id=str(tracker.id),
            api_key=tracker.api_key,
            connection_details=full_config,
        )
        if not tracker_client:
            # Raise specific error if factory returns None (e.g., unsupported type or config error)
            raise ValueError(
                f"Failed to create tracker client for type '{tracker_type}'. Check configuration: {full_config}"
            )

        return tracker_client
    except ValueError as ve:  # Catch config errors from factory
        logger.error(f"Configuration error creating tracker client: {ve}")
        raise HTTPException(
            status_code=500, detail=f"Configuration error for tracker: {str(ve)}"
        )
    except Exception as e:
        logger.error(f"Error creating tracker client: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error creating tracker client: {str(e)}"
        )


def get_compliance_prompts_from_config(
    config_path: str,
) -> List[CompliancePromptMetadata]:
    """Load and parse compliance prompts from a YAML file."""
    if not os.path.exists(config_path):
        logger.error(f"Compliance config file not found at: {config_path}")
        return []

    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {config_path}: {e}")
        return []

    compliance_section = config_data.get("compliance", {})
    if not compliance_section:
        logger.warning(f"'compliance' section not found or empty in {config_path}")
        return []

    prompts_metadata = [
        CompliancePromptMetadata(
            id=prompt_id,
            name=prompt_data.get("name", "Unnamed Prompt"),
            short_name=prompt_data.get("short_name", "N/A"),
        )
        for prompt_id, prompt_data in compliance_section.items()
    ]

    return prompts_metadata


def load_compliance_prompts_config(config_path: str) -> Dict[str, Any]:
    """Load the full compliance prompts configuration from a YAML file."""
    if not os.path.exists(config_path):
        logger.error(f"Compliance config file not found at: {config_path}")
        return {}

    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {config_path}: {e}")
        return {}

    return config_data.get("compliance", {})


def load_dependencies_prompts_config(config_path: str) -> Dict[str, Any]:
    """Load the full dependency detection prompts configuration from a YAML file."""
    if not os.path.exists(config_path):
        logger.error(f"Prompts config file not found at: {config_path}")
        return {}

    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {config_path}: {e}")
        return {}

    return config_data.get("dependencies", {})


def load_duplicates_prompts_config(config_path: str) -> Dict[str, Any]:
    """Load the full duplicates prompts configuration from a YAML file."""
    if not os.path.exists(config_path):
        logger.error(f"Prompts config file not found at: {config_path}")
        return {}

    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {config_path}: {e}")
        return {}

    return config_data.get("duplicates", {})
