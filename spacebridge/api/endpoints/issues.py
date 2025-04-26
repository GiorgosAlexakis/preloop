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
    crud_embedding_model,
    crud_issue_embedding,
)
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.issue import Issue
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
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

    # Check if project_id is a UUID or an identifier
    if len(project_id) == 36:  # Simple UUID check
        project = crud_project.get(db, id=project_id)
    else:
        project = crud_project.get_by_identifier(
            db, organization_id=organization.id, identifier=project_id
        )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
            # If we have an organization, use it to narrow down the project search
            if org_id:
                proj = crud_project.get_by_name(
                    db, name=project, organization_id=org_id
                )
            else:
                proj = crud_project.get_by_name(db, name=project)

        # Validate project (if project is specified but not found)
        if (project_id or project) and not proj:
            raise HTTPException(status_code=404, detail="Project not found")

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
                    response_items.append(
                        IssueResponse(
                            id=issue.external_id or issue.id,
                            title=issue.title,
                            description=issue.description,
                            status=issue.status,
                            priority=issue.priority,
                            organization=organization_name,
                            project=project_name,
                            url=external_url
                            or f"https://spacebridge.io/issues/{issue.id}",
                            created_at=created_at_str,
                            updated_at=updated_at_str,
                            metadata=metadata_dict,
                            labels=metadata_dict.get("labels", [])
                            if isinstance(metadata_dict.get("labels"), list)
                            else [],
                            assignee=metadata_dict.get("assignee"),
                            score=score,
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
                    response_items.append(
                        IssueResponse(
                            id=issue.external_id or issue.id,
                            title=issue.title,
                            description=issue.description,
                            status=issue.status,
                            priority=issue.priority,
                            organization=organization_name,
                            project=project_name,
                            url=external_url
                            or f"https://spacebridge.io/issues/{issue.id}",
                            created_at=created_at_str,
                            updated_at=updated_at_str,
                            metadata=metadata_dict,
                            labels=metadata_dict.get("labels", [])
                            if isinstance(metadata_dict.get("labels"), list)
                            else [],
                            assignee=metadata_dict.get("assignee"),
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

        # For the response, use the names and external ID
        # Map the returned tracker Issue object to the API IssueResponse
        return IssueResponse(
            id=created_issue.key
            or created_issue.id,  # Use external key/id from tracker
            organization=org.name,  # Use resolved organization name
            project=proj.name,  # Use resolved project name
            title=created_issue.title,
            description=created_issue.description,
            status=created_issue.status.name
            if created_issue.status
            else None,  # Extract name
            priority=created_issue.priority.name
            if created_issue.priority
            else None,  # Extract name
            assignee=created_issue.assignee.name
            if created_issue.assignee
            else None,  # Extract name
            labels=created_issue.labels,
            url=created_issue.url
            or f"https://tracker.example.com/issues/{created_issue.key}",  # Use tracker URL or fallback
            created_at=created_issue.created_at.isoformat()
            if created_issue.created_at
            else None,
            updated_at=created_issue.updated_at.isoformat()
            if created_issue.updated_at
            else None,
            metadata=created_issue.custom_fields,  # Map custom fields to metadata
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error creating issue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating issue: {str(e)}")


@router.get("/issues/{issue_id}", response_model=IssueResponse)  # Added response_model
def get_issue(
    issue_id: str,  # Assume this is the external_id
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """Get details of a specific issue using its external ID."""

    try:
        user_trackers = crud_tracker.get_for_account(db, account_id=current_user.id)
        tracker_ids = [t.id for t in user_trackers]

        if not tracker_ids:
            raise HTTPException(status_code=404, detail="No trackers found for user")

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
            # If found by internal ID, use external_id for the response 'id' field if available
            response_id = issue.external_id or issue.id
        else:
            response_id = issue.external_id  # Should be same as input issue_id

        # Get the project and organization
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
        if not external_url and issue.external_id:
            # Basic fallback if external_id exists but no URL found
            external_url = (
                f"https://tracker.example.com/issues/{issue.external_id}"  # Placeholder
            )

        # Convert to IssueResponse model
        return IssueResponse(
            id=response_id,  # Use external_id
            organization=organization.name,
            project=project.name,
            title=issue.title,
            description=issue.description or "",
            status=issue.status or "",
            priority=issue.priority or "",
            url=external_url
            or f"https://spacebridge.io/issues/{issue.id}",  # Final fallback
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


@router.put("/issues/{issue_id}", response_model=IssueResponse)
async def update_issue(
    issue_id: str,  # Assume this is the external_id
    issue_update: ApiIssueUpdate,
    # Removed org/project query params, should be derived if needed, but tracker client needs them
    # Let's try finding the issue first to get org/project context
    db: Session = Depends(get_db),
) -> IssueResponse:
    """Update an existing issue using its external ID."""
    try:
        raise HTTPException(status_code=500, detail="Not implemented")
        # Find the issue by external_id to get its context (project/org)
        # TODO: Add get_by_external_id to CRUDIssue if it doesn't exist
        db_issue = db.query(Issue).filter(Issue.external_id == issue_id).first()
        # db_issue = crud_issue.get_by_external_id(db, external_id=issue_id) # Ideal way
        if not db_issue:
            raise HTTPException(
                status_code=404, detail="Issue not found by external ID"
            )

        # Get project and organization from the found issue
        proj_obj = crud_project.get(db, id=db_issue.project_id)
        if not proj_obj:
            raise HTTPException(status_code=404, detail="Associated project not found")
        org_obj = crud_organization.get(db, id=proj_obj.organization_id)
        if not org_obj:
            raise HTTPException(
                status_code=404, detail="Associated organization not found"
            )

        # Get the tracker client using the resolved IDs
        tracker_client = await get_tracker_client(
            org_obj.id, proj_obj.id, db, current_user
        )

        # Prepare the update data using the base tracker schema
        update_data = {
            k: v
            for k, v in issue_update.dict(exclude_unset=True).items()
            if v is not None
        }
        # Map API metadata to custom_fields if needed by the tracker base model
        if "metadata" in update_data:
            update_data["custom_fields"] = update_data.pop("metadata")

        tracker_update = IssueUpdate(**update_data)  # Use IssueUpdate from base.py

        # Update the issue via the tracker client using the external ID (issue_id)
        updated_issue = await tracker_client.update_issue(issue_id, tracker_update)

        # Map the returned tracker Issue object to the API IssueResponse
        return IssueResponse(
            id=updated_issue.key
            or updated_issue.id,  # Use external key/id from tracker
            organization=org_obj.name,  # Use resolved org name
            project=proj_obj.name,  # Use resolved project name
            title=updated_issue.title,
            description=updated_issue.description,
            status=updated_issue.status.name if updated_issue.status else None,
            priority=updated_issue.priority.name if updated_issue.priority else None,
            assignee=updated_issue.assignee.name if updated_issue.assignee else None,
            labels=updated_issue.labels,
            url=updated_issue.url
            or f"https://tracker.example.com/issues/{updated_issue.key}",  # Use tracker URL or fallback
            created_at=updated_issue.created_at.isoformat()
            if updated_issue.created_at
            else None,
            updated_at=updated_issue.updated_at.isoformat()
            if updated_issue.updated_at
            else None,
            metadata=updated_issue.custom_fields,  # Map custom fields back to metadata
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating issue {issue_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating issue: {str(e)}")


@router.delete("/issues/{issue_id}", status_code=204)
async def delete_issue(
    issue_id: str,  # Assume this is the external_id
    # Removed org/project query params, derive from issue_id
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """Delete an issue using its external ID. Requires authentication and checks user access."""
    try:
        raise HTTPException(status_code=500, detail="Not implemented")
        # Find the issue by external_id to get its context (project/org)
        # TODO: Add get_by_external_id to CRUDIssue if it doesn't exist
        db_issue = db.query(Issue).filter(Issue.external_id == issue_id).first()
        # db_issue = crud_issue.get_by_external_id(db, external_id=issue_id) # Ideal way
        if not db_issue:
            # If not found by external ID, maybe it doesn't exist or sync is needed.
            # For deletion, it's often okay to proceed if the tracker handles "not found" gracefully.
            # However, we need org/project to get the client.
            # Let's raise 404 for now. A more robust solution might try to find org/proj differently.
            raise HTTPException(
                status_code=404,
                detail="Issue not found by external ID, cannot determine tracker.",
            )

        # Get project and organization from the found issue
        proj_obj = crud_project.get(db, id=db_issue.project_id)
        if not proj_obj:
            raise HTTPException(status_code=404, detail="Associated project not found")
        org_obj = crud_organization.get(db, id=proj_obj.organization_id)
        if not org_obj:
            raise HTTPException(
                status_code=404, detail="Associated organization not found"
            )

        # Get the tracker client using the resolved IDs
        tracker_client = await get_tracker_client(
            org_obj.id, proj_obj.id, db, current_user
        )

        # Delete the issue via the tracker client using the external ID (issue_id)
        await tracker_client.delete_issue(issue_id)

        # Optional: Delete the issue from the local DB as well
        # crud_issue.remove(db, id=db_issue.id)

        # No content to return on successful deletion
        return None
    except HTTPException:
        raise
    except Exception as e:
        # Catch potential errors from the tracker client (e.g., issue not found there)
        logger.error(f"Error deleting issue {issue_id}: {e}", exc_info=True)
        # Consider returning a different status code if tracker deletion failed vs internal error
        raise HTTPException(status_code=500, detail=f"Error deleting issue: {str(e)}")
