"""Endpoints for managing issues across trackers."""

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from spacebridge.schemas.issue import (
    IssueCreate as ApiIssueCreate,
    IssueResponse,
    IssueUpdate as ApiIssueUpdate,
)  # Renamed to avoid conflict
from spacemodels.models.account import Account

from spacemodels.crud import (
    CRUDIssue,
    CRUDOrganization,
    CRUDProject,
    CRUDTracker,  # Added CRUDTracker import
    crud_embedding_model,
    crud_issue_embedding,
)
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.issue import Issue
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.tracker import Tracker  # Added Tracker model import
from spacebridge.trackers.factory import TrackerFactory  # Import TrackerFactory
from spacebridge.trackers.base import (
    IssueCreate,
    IssueUpdate,
)  # Import base tracker schemas
from spacebridge.api.auth import get_current_active_user  # Import user dependency

# Initialize CRUD operations
crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)
crud_issue = CRUDIssue(Issue)
crud_tracker = CRUDTracker(Tracker)  # Added CRUDTracker instantiation


# Define the filter class for issue searching
class IssueFilter:
    def __init__(self, query: str, limit: int = 10):
        self.query = query
        self.limit = limit
        self.status = None
        self.labels = None
        self.assignee = None


logger = logging.getLogger(__name__)
router = APIRouter()

# Helper Functions


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
        organization = crud_organization.get(db, id=organization_id)
    else:
        organization = crud_organization.get_by_identifier(
            db, identifier=organization_id
        )

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Resolve project
    project: Optional[Project] = None
    if len(project_id) == 36:  # Check if project_id looks like a UUID (our internal ID)
        project = crud_project.get(db, id=project_id)
        # Verify it belongs to the correct organization
        if project and project.organization_id != organization.id:
            logger.warning(
                f"Project ID {project_id} found but belongs to wrong org ({project.organization_id} != {organization.id})"
            )
            project = None  # Treat as not found in this context
    else:
        # Assume project_id is a slug or identifier if not a UUID
        project_list = crud_project.get_by_slug_or_identifier(
            db, organization_id=organization.id, slug_or_identifier=project_id
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

    # --- Project Selection Check ---
    project_identifier = project.identifier  # Use the resolved project's identifier
    included_list = set(tracker.included_project_identifiers or [])
    excluded_list = set(tracker.excluded_project_identifiers or [])
    has_includes = bool(included_list)

    logger.debug(
        f"Checking project '{project_identifier}' against tracker {tracker.id} rules: "
        f"includes={included_list}, excludes={excluded_list}"
    )

    if project_identifier in excluded_list:
        logger.warning(
            f"Access denied: Project '{project_identifier}' is explicitly excluded by tracker {tracker.id}."
        )
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: Project '{project.name}' is excluded.",
        )

    if has_includes and project_identifier not in included_list:
        logger.warning(
            f"Access denied: Project '{project_identifier}' is not in the inclusion list for tracker {tracker.id}."
        )
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: Project '{project.name}' is not included for this tracker.",
        )
    # --- End Project Selection Check ---

    tracker_type = tracker.tracker_type

    # --- Assemble the full configuration ---
    # Start with project-specific tracker settings
    full_config: Dict[str, Any] = project.tracker_settings or {}
    # Add credentials from the Tracker model, structured as the factory expects
    full_config["credentials"] = {
        "token": tracker.api_key,
        "url": tracker.url,
        # Add username if available in connection_details (needed for Jira)
        "username": (tracker.connection_details or {}).get("username"),
    }
    # Merge any other connection details from the tracker model
    if tracker.connection_details:
        # Prioritize credentials already set, don't overwrite with connection_details
        for key, value in tracker.connection_details.items():
            if key not in full_config:
                full_config[key] = value
            elif key == "credentials" and isinstance(value, dict):
                # Merge credentials dict carefully
                for cred_key, cred_value in value.items():
                    if cred_key not in full_config["credentials"]:
                        full_config["credentials"][cred_key] = cred_value

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
        tracker_client = await TrackerFactory.create_client(tracker_type, full_config)
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


# API Endpoints


@router.get("/issues/search", response_model=List[IssueResponse])
async def search_issues(
    organization_id: Optional[str] = Query(None, description="Organization ID (UUID)"),
    organization: Optional[str] = Query(None, description="Organization name"),
    project_id: Optional[str] = Query(None, description="Project ID (UUID)"),
    project: Optional[str] = Query(None, description="Project name"),
    query: Optional[str] = Query("", description="Search query text"),
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of issues to return"
    ),
    search_type: str = Query(
        "full_text",
        enum=["full_text", "similarity"],
        description="Type of search to perform ('full_text' or 'similarity')",
    ),
    status: Optional[str] = Query(None, description="Filter by issue status"),
    labels: Optional[str] = Query(
        None, description="Filter by comma-separated list of labels"
    ),
    assignee: Optional[str] = Query(None, description="Filter by assignee"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Search for issues within a project using text query and optional similarity search.
    Requires authentication and checks user access.
    """
    try:
        # Resolve organization and project using either ID, name, or identifier
        from spacemodels.crud import crud_organization, crud_project, crud_tracker

        user_trackers = crud_tracker.get_for_account(db, account_id=current_user.id)
        tracker_ids = [t.id for t in user_trackers]

        if not tracker_ids:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        # Get Issues linked to the user's trackers
        issues = db.query(Issue).filter(Issue.tracker_id.in_(tracker_ids))
        # Process organization parameters
        org = None
        org_id = None
        if organization_id:
            org = crud_organization.get(db, id=organization_id)
            if org:
                org_id = org.id
        elif organization:
            org = crud_organization.get_by_name(db, name=organization)
            if org:
                org_id = org.id

        # Process project parameters
        proj = None
        if project_id:
            proj = crud_project.get(db, id=project_id)
        elif project:
            project_list: List[Project] = []
            # If we have an organization, use it to narrow down the project search
            if org_id:
                project_list = crud_project.get_by_name(
                    db, name=project, organization_id=org_id
                )
                # Handle the list result when org_id is specified
                if not project_list:
                    proj = None  # No project found by name in this org
                elif len(project_list) == 1:
                    proj = project_list[
                        0
                    ]  # Exactly one project found by name in this org
                else:
                    # This case should ideally not happen if name is unique within org, but handle defensively
                    raise HTTPException(
                        status_code=400,
                        detail=f"Multiple projects found with name '{project}' within organization '{org.identifier}'.",
                    )
            else:
                # --- No organization specified: Search globally by slug/id AND name ---
                logger.warning(
                    f"API: No organization specified. Searching globally for project '{project}'"
                )  # Use warning
                # Fetch single project by slug/id, returns Project or None
                project_by_slug_id = crud_project.get_by_slug_or_identifier(
                    db, slug_or_identifier=project
                )
                logger.warning(
                    f"API: Found project matching slug/identifier '{project}' globally? {'Yes' if project_by_slug_id else 'No'}"
                )  # Use warning

                # Fetch single project by name, returns Project or None
                project_by_name = crud_project.get_by_name(db, name=project)
                logger.warning(
                    f"API: Found project matching name '{project}' globally? {'Yes' if project_by_name else 'No'}"
                )  # Use warning

                # Combine results and filter for active projects
                # Use a dictionary to handle potential duplicates from searching different fields
                combined_projects_dict: Dict[str, Project] = {}
                if project_by_slug_id:
                    combined_projects_dict[project_by_slug_id.id] = project_by_slug_id
                if project_by_name:  # Add/overwrite if found by name
                    combined_projects_dict[project_by_name.id] = project_by_name
                logger.warning(
                    f"API: Combined unique projects found: {len(combined_projects_dict)}"
                )  # Use warning

                active_projects = [
                    p for p in combined_projects_dict.values() if p.is_active
                ]
                logger.warning(
                    f"API: Active projects found matching '{project}' globally: {len(active_projects)}"
                )  # Use warning

                if not active_projects:
                    proj = None  # No active project found globally
                elif len(active_projects) == 1:
                    proj = active_projects[
                        0
                    ]  # Exactly one active project found globally
                else:
                    # Multiple active projects found globally
                    raise HTTPException(
                        status_code=400,
                        detail=f"Multiple active projects found matching '{project}'. Please specify an organization.",
                    )

        # --- Final Validation ---
        logger.warning(
            f"API: Before final validation: proj is {'set' if proj else 'None'}, project_id='{project_id}', project='{project}'"
        )  # Add log
        # Validate project (if project is specified but not found)
        # The check `if not proj` now correctly handles the case where the list was empty or ambiguity was detected earlier
        if (project_id or project) and not proj:
            # Raise 404 if proj is None after the checks above
            logger.error(
                f"API: Raising 404 because proj is None. project_id='{project_id}', project='{project}'"
            )  # Add log
            raise HTTPException(
                status_code=404, detail=f"Project '{project}' not found."
            )

        # Ensure project belongs to the specified organization, if applicable
        if org and proj and org.id != proj.organization_id:
            # This check remains valid as proj is now a single object or None
            raise HTTPException(
                status_code=400,  # Use 400 as it's a mismatch based on input
                detail=f"Project '{proj.name}' does not belong to organization '{org.identifier}'.",
            )

        # If organization wasn't specified initially, but we found a unique project, get its org
        if not org and proj:
            # Explicitly fetch the organization using CRUD
            logger.warning(
                f"API: Globally found project '{proj.name}' (ID: {proj.id}). Fetching its organization (ID: {proj.organization_id})."
            )
            org = crud_organization.get(db, id=proj.organization_id)
            if not org:
                # This indicates an orphaned project or data inconsistency
                logger.error(
                    f"API: Found project '{proj.name}' (ID: {proj.id}) but could not find its organization (ID: {proj.organization_id}) in the database."
                )
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error: Project organization data inconsistent.",
                )
            elif not org.is_active:
                # Found the org, but it's inactive
                logger.warning(
                    f"API: Found project '{proj.name}' (ID: {proj.id}) but its organization '{org.identifier}' (ID: {org.id}) is inactive."
                )
                # Treat as project not found, as the org context is invalid
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{project}' not found (its organization is inactive).",
                )
            logger.warning(
                f"API: Successfully fetched organization '{org.identifier}' for project '{proj.name}'."
            )
        # Validate access and get tracker client (even if not used directly for DB search)
        # This enforces the project selection rules before proceeding.
        try:
            await get_tracker_client(org.id, proj.id, db, current_user)
        except HTTPException as e:
            # If get_tracker_client raises an error (e.g., 403 Forbidden due to project exclusion),
            # re-raise it to stop the search.
            raise e
        except Exception as e:
            # Catch potential errors during client creation/validation
            logger.error(
                f"Error validating tracker access for search: {e}", exc_info=True
            )
            raise HTTPException(
                status_code=500, detail="Error validating tracker access."
            )

        # Create filter object for traditional search
        filter_obj = IssueFilter(query=query, limit=limit)
        if status:
            filter_obj.status = status
        if labels:
            filter_obj.labels = labels.split(",")
        if assignee:
            filter_obj.assignee = assignee

        response_items = []
        if search_type == "similarity" and query:
            try:
                # Get the active embedding model
                active_models = crud_embedding_model.get_active(db)
                if not active_models:
                    logger.error(
                        "similarity search requested, but no active embedding model found."
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="similarity search cannot be performed: No active embedding model configured.",
                    )
                model = active_models[0]
                model_id = model.id

                # Generate query vector
                query_vector = crud_issue_embedding._generate_embedding_vector(
                    query, model
                )

                # Find similar issues using similarity search
                similar_issues = crud_issue_embedding.similarity_search(
                    db,
                    model_id=model_id,
                    query_vector=query_vector,
                    limit=limit,
                    tracker_ids=tracker_ids,
                )

                # Extract issues and apply filters
                if proj:
                    results = [
                        (issue, score)
                        for issue, score in similar_issues
                        if issue.project_id == proj.id
                    ]
                else:
                    results = [(issue, score) for issue, score in similar_issues]

                # Apply additional filters if specified
                if status:
                    results = [
                        (issue, score)
                        for issue, score in results
                        if issue.status == status
                    ]
                if labels and isinstance(filter_obj.labels, list):
                    results = [
                        (issue, score)
                        for issue, score in results
                        if issue.meta_data
                        and "labels" in issue.meta_data
                        and all(
                            label in issue.meta_data["labels"]
                            for label in filter_obj.labels
                        )
                    ]
                if assignee:
                    results = [
                        (issue, score)
                        for issue, score in results
                        if issue.meta_data
                        and "assignee" in issue.meta_data
                        and issue.meta_data["assignee"] == assignee
                    ]

                # Limit results
                results = results[:limit]

                # Convert to IssueResponse
                for issue, score in results:
                    issue_project = crud_project.get(db, id=issue.project_id)
                    project_name = issue_project.name if issue_project else None
                    organization_name = None
                    if issue_project:
                        issue_org = crud_organization.get(
                            db, id=issue_project.organization_id
                        )
                        if issue_org:
                            organization_name = issue_org.name
                    created_at_str = (
                        issue.created_at.isoformat() if issue.created_at else None
                    )
                    updated_at_str = (
                        issue.updated_at.isoformat() if issue.updated_at else None
                    )
                    metadata_dict = dict(issue.meta_data) if issue.meta_data else {}
                    external_url = metadata_dict.get("url") or issue.external_url
                    # Determine response ID based on project slug
                    response_id = issue.external_id or str(
                        issue.id
                    )  # Fallback to internal ID string
                    if issue_project and issue_project.slug and issue.external_id:
                        response_id = f"{issue_project.slug}#{issue.external_id}"
                    elif issue.external_id:
                        response_id = issue.external_id

                    # Ensure required fields are present (as per task constraints, assume they are)
                    if not issue.external_id:
                        logger.warning(
                            f"Issue {issue.id} missing external_id during similarity search response creation."
                        )
                        continue
                    if not issue.key:
                        logger.warning(
                            f"Issue {issue.id} missing key during similarity search response creation."
                        )
                        continue

                    response_items.append(
                        IssueResponse(
                            id=str(issue.id),  # Use internal DB UUID
                            external_id=issue.external_id,  # Use tracker's external ID
                            key=issue.key,  # Use human-readable key
                            title=issue.title,
                            description=issue.description,
                            status=issue.status,
                            priority=issue.priority,
                            organization=organization_name,
                            project=project_name,
                            url=external_url
                            or f"https://spacebridge.io/issues/{issue.id}",  # Use external URL if available
                            created_at=created_at_str,
                            updated_at=updated_at_str,
                            metadata=metadata_dict,
                            labels=metadata_dict.get("labels", [])
                            if isinstance(metadata_dict.get("labels"), list)
                            else [],
                            assignee=metadata_dict.get("assignee"),
                            score=score,  # Include similarity score
                        )
                    )

            except Exception as e:
                logger.error(f"Error during similarity search: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="An error occurred during similarity search.",
                )

        elif search_type == "full_text":
            # Perform traditional full-text search
            try:
                from sqlalchemy import or_

                # Filter by project/org
                if proj:
                    issues = issues.filter(Issue.project_id == proj.id)
                elif org:
                    project_ids = [p.id for p in org.projects]
                    if project_ids:
                        issues = issues.filter(Issue.project_id.in_(project_ids))
                    else:
                        return []  # Org has no projects

                # Apply text query filter
                if query:
                    search_term = f"%{query}%"
                    issues = issues.filter(
                        or_(
                            Issue.title.ilike(search_term),
                            Issue.description.ilike(search_term),
                        )
                    )

                # Apply status filter
                if status:
                    issues = issues.filter(Issue.status == status)

                # Apply labels/assignee filters directly in the query if possible
                # Note: This example assumes simple JSON structure and might need adjustment
                # based on actual DB capabilities (e.g., using JSONB operators)
                if labels and isinstance(filter_obj.labels, list):
                    # Example for PostgreSQL JSONB containment:
                    # query_builder = query_builder.filter(Issue.meta_data['labels'].contains(filter_obj.labels))
                    # For now, we keep post-fetch filtering for broader compatibility
                    pass
                if assignee:
                    # Example for PostgreSQL JSONB:
                    # query_builder = query_builder.filter(Issue.meta_data['assignee'] == assignee)
                    pass

                # Fetch issues
                issues_db = issues.order_by(Issue.updated_at.desc()).limit(limit).all()

                # Post-fetch filtering (if DB filtering wasn't possible/implemented)
                if labels and isinstance(filter_obj.labels, list):
                    issues_db = [
                        issue
                        for issue in issues_db
                        if issue.meta_data
                        and "labels" in issue.meta_data
                        and all(
                            label in issue.meta_data["labels"]
                            for label in filter_obj.labels
                        )
                    ]
                if assignee:
                    issues_db = [
                        issue
                        for issue in issues_db
                        if issue.meta_data
                        and "assignee" in issue.meta_data
                        and issue.meta_data["assignee"] == assignee
                    ]

                # Convert to IssueResponse
                for issue in issues_db:
                    issue_project = crud_project.get(db, id=issue.project_id)
                    project_name = (
                        issue_project.name if issue_project else "Unknown Project"
                    )
                    organization_name = "Unknown Org"
                    if issue_project:
                        issue_org = crud_organization.get(
                            db, id=issue_project.organization_id
                        )
                        if issue_org:
                            organization_name = issue_org.name
                    created_at_str = (
                        issue.created_at.isoformat() if issue.created_at else None
                    )
                    updated_at_str = (
                        issue.updated_at.isoformat() if issue.updated_at else None
                    )
                    metadata_dict = dict(issue.meta_data) if issue.meta_data else {}
                    external_url = metadata_dict.get("url") or issue.external_url
                    # Determine response ID based on project slug
                    response_id = issue.external_id or str(
                        issue.id
                    )  # Fallback to internal ID string
                    if issue_project and issue_project.slug and issue.external_id:
                        response_id = f"{issue_project.slug}#{issue.external_id}"
                    elif issue.external_id:
                        response_id = issue.external_id

                    # Ensure required fields are present (as per task constraints, assume they are)
                    if not issue.external_id:
                        logger.warning(
                            f"Issue {issue.id} missing external_id during full-text search response creation."
                        )
                        # Decide handling: skip, error, or default? Skipping for now.
                        continue
                    if not issue.key:
                        logger.warning(
                            f"Issue {issue.id} missing key during full-text search response creation."
                        )
                        # Decide handling: skip, error, or default? Skipping for now.
                        continue

                    response_items.append(
                        IssueResponse(
                            id=str(issue.id),  # Use internal DB UUID
                            external_id=issue.external_id,  # Use tracker's external ID
                            key=issue.key,  # Use human-readable key
                            title=issue.title,
                            description=issue.description,
                            status=issue.status,
                            priority=issue.priority,
                            organization=organization_name,
                            project=project_name,
                            url=external_url
                            or f"https://spacebridge.io/issues/{issue.id}",  # Use external URL if available
                            created_at=created_at_str,
                            updated_at=updated_at_str,
                            metadata=metadata_dict,
                            labels=metadata_dict.get("labels", [])
                            if isinstance(metadata_dict.get("labels"), list)
                            else [],
                            assignee=metadata_dict.get("assignee"),
                            score=None,  # No score for full-text search
                        )
                    )

            except Exception as e:
                logger.error(f"Error during full-text search: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500, detail="An error occurred during full-text search."
                )
        elif query:  # Handle case where type is invalid but query exists
            logger.warning(f"Invalid search type specified: {search_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid search type: {search_type}. Must be 'full_text' or 'similarity'.",
            )
        else:  # No query provided, return empty list or handle as needed
            pass  # Currently returns empty list by default

        return response_items
    except HTTPException:
        # Re-raise specific HTTP exceptions (like the 404 for project not found)
        raise
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error searching issues: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during issue search."
        )


@router.post("/issues", response_model=IssueResponse, status_code=201)
async def create_issue(
    issue: ApiIssueCreate,  # Use the renamed API schema
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> IssueResponse:
    """Create a new issue in a specified project. Requires authentication and checks user access.

    Supports specifying organization/project by:
    - ID (organization_id/project_id)
    - Name (organization_name/project_name)
    - Identifier (organization/project - deprecated)
    """
    try:
        # Resolve organization and project using either ID, name, or identifier
        from spacemodels.crud import crud_organization, crud_project

        org = None
        proj = None
        org_id = None
        proj_id = None

        # --- Resolve Organization and Project ---

        # Prioritize IDs if provided
        if issue.organization_id:
            org = crud_organization.get(db, id=issue.organization_id)
            if org:
                org_id = org.id
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Organization with ID '{issue.organization_id}' not found",
                )
        if issue.project_id:
            proj = crud_project.get(db, id=issue.project_id)
            if proj:
                proj_id = proj.id
                # If project found by ID, ensure org matches if org was also found by ID
                if org_id and proj.organization_id != org_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Project does not belong to the specified organization ID",
                    )
                # If org wasn't found by ID, infer it from the project
                if not org_id:
                    org = crud_organization.get(db, id=proj.organization_id)
                    if org:
                        org_id = org.id
                    else:  # Data inconsistency
                        raise HTTPException(
                            status_code=500, detail="Project's organization not found"
                        )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project with ID '{issue.project_id}' not found",
                )

        # If IDs weren't used or didn't resolve both, try names/identifiers
        if not org or not proj:
            project_identifier = issue.project or issue.project_name
            organization_identifier = issue.organization or issue.organization_name

            if not project_identifier:
                # Schema validation should prevent this, but double-check
                raise HTTPException(
                    status_code=400, detail="Project identifier or name is required"
                )

            if organization_identifier:
                # Org and Project provided by name/identifier
                if not org:  # If org wasn't found by ID earlier
                    org = crud_organization.get_by_identifier(
                        db, identifier=organization_identifier
                    ) or crud_organization.get_by_name(db, name=organization_identifier)
                    if not org:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Organization '{organization_identifier}' not found",
                        )
                    org_id = org.id

                if not proj:  # If proj wasn't found by ID earlier
                    proj = crud_project.get_by_identifier(
                        db, organization_id=org_id, identifier=project_identifier
                    ) or crud_project.get_by_name(
                        db, organization_id=org_id, name=project_identifier
                    )
                    if not proj:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Project '{project_identifier}' not found in organization '{organization_identifier}'",
                        )
                    proj_id = proj.id

            else:
                # Only Project provided, infer Organization
                found_projects = crud_project.get_by_identifier_or_name_across_orgs(
                    db, identifier_or_name=project_identifier
                )

                if not found_projects:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Project '{project_identifier}' not found",
                    )
                if len(found_projects) > 1:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Project '{project_identifier}' is ambiguous, please specify the organization",
                    )

                proj = found_projects[0]
                proj_id = proj.id
                org = crud_organization.get(db, id=proj.organization_id)
                if not org:  # Data inconsistency
                    raise HTTPException(
                        status_code=500, detail="Project's organization not found"
                    )
                org_id = org.id

        # --- End Resolve Organization and Project ---

        # Ensure we have resolved both org and proj by now
        if not org or not proj:
            raise HTTPException(
                status_code=500, detail="Failed to resolve organization or project"
            )

        # Get the tracker client using the resolved IDs, passing the current user for auth check
        tracker_client = await get_tracker_client(org.id, proj.id, db, current_user)

        # Prepare the issue create model using the correct base class
        tracker_issue = IssueCreate(  # Use IssueCreate from base.py
            title=issue.title,
            description=issue.description,
            priority=issue.priority,
            assignee=issue.assignee,
            labels=issue.labels,
            # Map API metadata to custom_fields if needed by the tracker base model
            custom_fields=issue.metadata or None,
        )

        # Create the issue - Pass the project identifier expected by the tracker client
        # Use project.identifier as the most likely candidate for project_key
        project_key_for_tracker = proj.identifier
        if not project_key_for_tracker:
            # Fallback or specific logic might be needed if identifier isn't the key
            # For now, raise error if identifier is missing
            raise HTTPException(
                status_code=500,
                detail="Project identifier is missing for tracker interaction.",
            )

        created_issue = await tracker_client.create_issue(
            project_key_for_tracker, tracker_issue
        )

        # --- Save to local database ---
        # Extract necessary IDs and data from the tracker response
        tracker_external_id = str(created_issue.id) if created_issue.id else None
        tracker_key = created_issue.key
        tracker_url = created_issue.url

        # Ensure tracker_id is available
        if not org.tracker_id:
            logger.error(f"Organization {org.id} has no associated tracker_id.")
            raise HTTPException(
                status_code=500,
                detail="Internal configuration error: Missing tracker ID.",
            )

        # Prepare data for database insertion
        issue_data_for_db = {
            "title": created_issue.title,
            "description": created_issue.description,
            "status": created_issue.status.name if created_issue.status else None,
            "priority": created_issue.priority.name if created_issue.priority else None,
            "assignee": created_issue.assignee.name if created_issue.assignee else None,
            "labels": created_issue.labels,
            "meta_data": created_issue.custom_fields,  # Map custom_fields to meta_data
            "external_id": tracker_external_id,
            "key": tracker_key,
            "url": tracker_url,
            "tracker_id": org.tracker_id,  # Use tracker_id from the organization
            "project_id": proj.id,  # Use internal project UUID
            "created_at": created_issue.created_at,
            "updated_at": created_issue.updated_at,
            # Add other relevant fields if the Issue model requires them
        }

        # Create the issue in the database
        try:
            db_issue = crud_issue.create(db=db, obj_in=issue_data_for_db)
            db.commit()  # Commit the transaction
            db.refresh(db_issue)  # Refresh to get DB-generated values like ID
        except Exception as db_exc:
            db.rollback()  # Rollback on error
            logger.error(
                f"Error saving created issue to database: {db_exc}", exc_info=True
            )
            # Consider if we should delete the issue from the tracker here?
            # For now, return an error indicating partial success/failure.
            raise HTTPException(
                status_code=500,
                detail=f"Issue created in tracker ({tracker_key or tracker_external_id}) but failed to save locally: {str(db_exc)}",
            )

        # --- Construct the API Response using the database object ---
        return IssueResponse(
            id=str(db_issue.id),  # Use internal DB UUID
            external_id=db_issue.external_id,  # Use external ID from DB
            key=db_issue.key,  # Use key from DB
            organization=org.name,
            project=proj.name,
            title=db_issue.title,
            description=db_issue.description,
            status=db_issue.status,
            priority=db_issue.priority,
            assignee=db_issue.assignee,
            labels=db_issue.labels,
            url=db_issue.url,
            created_at=db_issue.created_at.isoformat() if db_issue.created_at else None,
            updated_at=db_issue.updated_at.isoformat() if db_issue.updated_at else None,
            metadata=db_issue.meta_data,
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error creating issue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating issue: {str(e)}")


@router.get(
    "/issues/{issue_id:path}", response_model=IssueResponse
)  # Added response_model
def get_issue(
    issue_id: str,  # Assume this is the external_id
    organization: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """Get details of a specific issue using its external ID."""
    try:
        user_trackers = crud_tracker.get_for_account(db, account_id=current_user.id)
        tracker_ids = [t.id for t in user_trackers]

        if not tracker_ids:
            raise HTTPException(status_code=404, detail="No trackers found for user")

        project_slug = None
        if "#" in issue_id:
            project_slug, issue_id = issue_id.split("#")
        # Get the project and organization
        if project_slug:
            project = crud_project.get_by_slug_or_identifier(
                db, slug_or_identifier=project_slug
            )
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            organization = crud_organization.get(db, id=project.organization_id)
            if not organization:
                raise HTTPException(status_code=404, detail="Organization not found")

        # Find the issue by external_id
        # TODO: Add get_by_external_id to CRUDIssue if it doesn't exist
        issue = (
            db.query(Issue)
            .filter(Issue.tracker_id.in_(tracker_ids), Issue.external_id == issue_id)
            .first()
        )
        # issue = crud_issue.get_by_external_id(db, external_id=issue_id) # Ideal way
        if not issue:
            # Maybe it was the internal ID? Try that as a fallback.
            issue = crud_issue.get(db, id=issue_id)
            if not issue:
                raise HTTPException(
                    status_code=404, detail="Issue not found by external or internal ID"
                )

        project = crud_project.get(db, id=issue.project_id)
        if not project:
            # This indicates data inconsistency if the issue exists but project doesn't
            logger.error(
                f"Project with ID {issue.project_id} not found for issue {issue.id}"
            )
            raise HTTPException(status_code=404, detail="Associated project not found")

        organization = crud_organization.get(db, id=project.organization_id)
        if not organization:
            logger.error(
                f"Organization with ID {project.organization_id} not found for project {project.id}"
            )
            raise HTTPException(
                status_code=404, detail="Associated organization not found"
            )

        # Extract data from JSON fields if available
        meta_data = issue.meta_data or {}
        labels_list = meta_data.get("labels", []) if isinstance(meta_data, dict) else []
        assignee = meta_data.get("assignee") if isinstance(meta_data, dict) else None

        # Determine the URL
        external_url = meta_data.get("url") or issue.external_url
        if not external_url:
            # Basic fallback if external_id exists but no URL found
            external_url = f"https://spacebridge.io/issues/{issue.id}"

        # Convert to IssueResponse model
        if (
            project and project.slug and issue.external_id
        ):  # Check external_id specifically for formatting
            final_response_key = f"{project.slug}#{issue.external_id}"

        return IssueResponse(
            id=issue.id,
            key=final_response_key,
            external_id=issue.external_id,
            organization=organization.name,
            project=project.name,
            title=issue.title,
            description=issue.description or "",
            status=issue.status or "",
            priority=issue.priority or "",
            url=external_url,
            created_at=issue.created_at.isoformat() if issue.created_at else None,
            updated_at=issue.updated_at.isoformat() if issue.updated_at else None,
            metadata=meta_data,
            labels=labels_list,
            assignee=assignee,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving issue {issue_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/issues/{issue_id:path}", response_model=IssueResponse)
async def update_issue(
    issue_id: str,
    issue_update: ApiIssueUpdate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """Update an existing issue using its internal ID or external key."""
    logger.info(f"Attempting to update issue: {issue_id}")
    try:
        user_trackers = crud_tracker.get_for_account(db, account_id=current_user.id)
        tracker_ids = [t.id for t in user_trackers]

        if not tracker_ids:
            logger.warning(f"User {current_user.username} has no associated trackers.")
            raise HTTPException(
                status_code=403, detail="User has no accessible trackers."
            )

        # --- Issue Retrieval Logic (Adapted from get_issue) ---
        issue: Optional[Issue] = None
        project_slug_from_key: Optional[str] = None
        external_id_from_key: Optional[str] = None

        # 1. Try internal UUID first
        if len(issue_id) == 36:  # Basic UUID check
            logger.debug(f"Attempting lookup by internal ID: {issue_id}")
            issue = crud_issue.get(db, id=issue_id)
            if issue and issue.tracker_id not in tracker_ids:
                logger.warning(
                    f"Issue {issue_id} found by ID, but tracker {issue.tracker_id} not accessible by user {current_user.id}"
                )
                issue = None  # Treat as not found if not accessible

        # 2. Try combined key (project_slug#external_id)
        if not issue and "#" in issue_id:
            logger.debug(f"Attempting lookup by combined key: {issue_id}")
            try:
                project_slug_from_key, external_id_from_key = issue_id.split("#", 1)
                # Use get_by_slug_or_identifier which returns a list
                project_list = crud_project.get_by_slug_or_identifier(
                    db, slug_or_identifier=project_slug_from_key
                )
                if len(project_list) == 1:
                    project_for_lookup = project_list[0]
                    # Ensure the project's tracker is accessible
                    if project_for_lookup.tracker_id in tracker_ids:
                        issue = (
                            db.query(Issue)
                            .filter(
                                Issue.project_id == project_for_lookup.id,
                                Issue.external_id == external_id_from_key,
                                Issue.tracker_id.in_(
                                    tracker_ids
                                ),  # Redundant check, but safe
                            )
                            .first()
                        )
                    else:
                        logger.warning(
                            f"Project {project_slug_from_key} found, but its tracker {project_for_lookup.tracker_id} not accessible by user {current_user.id}"
                        )
                elif len(project_list) > 1:
                    logger.warning(
                        f"Ambiguous project slug '{project_slug_from_key}' found."
                    )
                    # Don't raise error, just proceed to next lookup method
                else:
                    logger.debug(
                        f"Project with slug '{project_slug_from_key}' not found."
                    )

            except ValueError:
                logger.warning(f"Invalid combined key format: {issue_id}")
                # Proceed to next lookup method

        # 3. Try direct external ID
        if not issue:
            logger.debug(f"Attempting lookup by direct external ID: {issue_id}")
            # Search across all accessible trackers for this external ID
            issue = (
                db.query(Issue)
                .filter(
                    Issue.external_id == issue_id, Issue.tracker_id.in_(tracker_ids)
                )
                .first()
            )

        if not issue:
            logger.warning(
                f"Issue '{issue_id}' not found or not accessible by user {current_user.id}."
            )
            raise HTTPException(
                status_code=404,
                detail=f"Issue '{issue_id}' not found or access denied.",
            )

        logger.info(
            f"Found issue {issue.id} (External: {issue.external_id}) for update."
        )

        # --- Retrieve Project and Organization ---
        project = crud_project.get(db, id=issue.project_id)
        if not project:
            logger.error(
                f"Data inconsistency: Project {issue.project_id} not found for issue {issue.id}"
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error: Associated project data missing.",
            )

        organization = crud_organization.get(db, id=project.organization_id)
        if not organization:
            logger.error(
                f"Data inconsistency: Organization {project.organization_id} not found for project {project.id}"
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error: Associated organization data missing.",
            )

        # --- Validate Access & Get Tracker Client ---
        try:
            # Use internal IDs for get_tracker_client
            tracker_client = await get_tracker_client(
                organization_id=str(organization.id),  # Pass UUID
                project_id=str(project.id),  # Pass UUID
                db=db,
                current_user=current_user,
            )
        except HTTPException as e:
            # Re-raise authorization or configuration errors from get_tracker_client
            logger.warning(f"Access validation failed for issue {issue.id}: {e.detail}")
            raise e
        except Exception as e:
            logger.error(
                f"Error getting tracker client for issue {issue.id}: {e}", exc_info=True
            )
            raise HTTPException(
                status_code=500, detail="Error preparing tracker connection."
            )

        # --- Prepare Update Payload for Tracker ---
        # Use the base IssueUpdate schema expected by the tracker client
        tracker_update_payload = IssueUpdate(
            title=issue_update.title,
            description=issue_update.description,
            status=issue_update.status,
            priority=issue_update.priority,
            labels=issue_update.labels,
            assignee=issue_update.assignee,
            # Add other fields if the base IssueUpdate schema supports them
        )
        # Filter out None values, as tracker clients might interpret None as "clear this field"
        update_data_for_tracker = tracker_update_payload.model_dump(exclude_unset=True)

        if not update_data_for_tracker:
            logger.info(
                f"No fields provided to update for issue {issue.id}. Skipping tracker update."
            )
            # Optionally, you could raise a 400 Bad Request here if an empty update is invalid
            # raise HTTPException(status_code=400, detail="No update data provided.")
        else:
            # --- Call Tracker Client ---
            if not issue.external_id:
                logger.error(
                    f"Cannot update issue {issue.id} in tracker: Missing external_id."
                )
                raise HTTPException(
                    status_code=400,
                    detail="Cannot update issue in tracker: Missing external identifier.",
                )

            try:
                logger.info(
                    f"Calling tracker client to update issue {issue.external_id} with data: {update_data_for_tracker}"
                )
                # Use the issue's external_id for the tracker API call
                await tracker_client.update_issue(
                    issue.external_id, IssueUpdate(**update_data_for_tracker)
                )
                logger.info(
                    f"Successfully updated issue {issue.external_id} via tracker client."
                )
            except NotImplementedError:
                logger.warning(
                    f"Tracker type {tracker_client.tracker_type} does not support updating issues."
                )
                # Decide if this should be an error or just a warning
                # raise HTTPException(status_code=501, detail="Issue updates not supported by this tracker type.")
            except Exception as e:
                logger.error(
                    f"Error updating issue {issue.external_id} via tracker client: {e}",
                    exc_info=True,
                )
                # Depending on requirements, you might still update the local DB or raise an error
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to update issue in the external tracker: {str(e)}",
                )

        # --- Update Local DB ---
        # Prepare data for local DB update using the ApiIssueUpdate model
        update_data_for_db = issue_update.model_dump(exclude_unset=True)

        if not update_data_for_db:
            logger.info(
                f"No fields provided to update for issue {issue.id} in local DB."
            )
            # If we skipped tracker update due to no data, we might skip DB update too,
            # or just proceed to return the current state.
        else:
            try:
                logger.info(
                    f"Updating local DB for issue {issue.id} with data: {update_data_for_db}"
                )
                # Update the local database record
                # Note: crud_issue.update expects the db object, the existing db_obj, and the update obj (Pydantic model or dict)
                updated_issue_db = crud_issue.update(
                    db=db, db_obj=issue, obj_in=update_data_for_db
                )
                db.commit()
                db.refresh(
                    updated_issue_db
                )  # Ensure we have the latest data including timestamps
                issue = updated_issue_db  # Use the updated object going forward
                logger.info(f"Successfully updated issue {issue.id} in local DB.")
            except SQLAlchemyError as e:
                db.rollback()
                logger.error(
                    f"Database error updating issue {issue.id}: {e}", exc_info=True
                )
                raise HTTPException(
                    status_code=500, detail="Database error during issue update."
                )

        # --- Format Response ---
        # Fetch potentially updated metadata or related objects if necessary
        # Re-fetch project/org in case their names changed (unlikely but possible)
        # Use a joined load to potentially optimize if project/org were frequently changing,
        # but simple re-fetch is fine for now.
        db.refresh(
            issue
        )  # Refresh again after potential commit/refresh inside update block
        project = crud_project.get(db, id=issue.project_id)  # Re-fetch
        organization = (
            crud_organization.get(db, id=project.organization_id) if project else None
        )  # Re-fetch safely

        if not project or not organization:
            logger.error(
                f"Data inconsistency after update: Project or Organization missing for issue {issue.id}"
            )
            # Fallback response data
            project_name = "Error: Missing Project"
            org_name = "Error: Missing Organization"
            project_slug = "error"
        else:
            project_name = project.name
            org_name = organization.name
            project_slug = project.slug

        meta_data = issue.meta_data or {}
        labels_list = meta_data.get("labels", []) if isinstance(meta_data, dict) else []
        assignee = meta_data.get("assignee") if isinstance(meta_data, dict) else None
        external_url = (
            meta_data.get("url") or issue.external_url or f"/issues/{issue.id}"
        )  # Fallback URL

        # Construct the key using potentially updated slug/external_id
        final_response_key = (
            f"{project_slug}#{issue.external_id}"
            if project_slug and issue.external_id
            else str(issue.id)
        )

        logger.info(f"Returning updated issue details for {issue.id}")
        return IssueResponse(
            id=str(issue.id),  # Ensure ID is string
            key=final_response_key,
            external_id=issue.external_id,
            organization=org_name,
            project=project_name,
            title=issue.title,
            description=issue.description or "",
            status=issue.status or "",
            priority=issue.priority or "",
            url=external_url,
            created_at=issue.created_at.isoformat() if issue.created_at else None,
            updated_at=issue.updated_at.isoformat() if issue.updated_at else None,
            metadata=meta_data,
            labels=labels_list,
            assignee=assignee,
        )

    except HTTPException:
        # Re-raise HTTPExceptions directly
        db.rollback()  # Rollback on known HTTP errors too, just in case
        raise
    except Exception as e:
        db.rollback()  # Rollback on any unexpected error
        logger.error(f"Unexpected error updating issue {issue_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during issue update."
        )


# Note: Ensure necessary imports are present at the top of the file.
# Imports needed: logging, Optional, List, Dict, Any, APIRouter, Depends,
# HTTPException, Query, Body, Session, joinedload, SQLAlchemyError, IssueResponse,
# ApiIssueUpdate, Account, CRUD*, get_db, Issue, Organization, Project, Tracker,
# TrackerFactory, IssueUpdate (base), get_current_active_user
# Also ensure `get_tracker_client` is defined or imported correctly.
