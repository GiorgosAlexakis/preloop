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


async def get_tracker_client(organization_id: str, project_id: str, db: Session):
    """Get the appropriate tracker client for the given organization and project.

    Args:
        organization_id: The organization ID or identifier.
        project_id: The project ID or identifier.
        db: Database session.

    Returns:
        A tracker client instance.

    Raises:
        HTTPException: If the organization or project is not found, or if a tracker
            client cannot be created.
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
        if "owner" not in full_config:
            full_config["owner"] = (project.tracker_settings or {}).get("owner") or (
                project.meta_data or {}
            ).get("owner")
        if "repo" not in full_config:
            full_config["repo"] = (
                (project.tracker_settings or {}).get("repo")
                or (project.meta_data or {}).get("repo")
                or project.identifier
            )  # Use identifier as repo fallback if owner exists
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
    semantic: bool = Query(
        True, description="Whether to use semantic search with vector embeddings"
    ),
    status: Optional[str] = Query(None, description="Filter by issue status"),
    labels: Optional[str] = Query(
        None, description="Filter by comma-separated list of labels"
    ),
    assignee: Optional[str] = Query(None, description="Filter by assignee"),
    db: Session = Depends(get_db),
):
    """
    Search for issues within a project using text query and optional semantic search.
    (Code unchanged from previous version)
    """
    try:
        # Resolve organization and project using either ID, name, or identifier
        from spacemodels.crud import crud_organization, crud_project

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

        if semantic and query:
            # Get the active embedding model
            active_models = crud_embedding_model.get_active(db)
            model_id = active_models[0].id

            # Generate query vector
            query_vector = crud_issue_embedding._generate_embedding_vector(
                query, active_models[0]
            )

            # 2. Find similar issues using similarity search
            similar_issues = crud_issue_embedding.similarity_search(
                db, model_id=model_id, query_vector=query_vector, limit=limit
            )

            # 3. Extract issues and return them
            if proj:
                results = [
                    issue for issue, _ in similar_issues if issue.project_id == proj.id
                ]
            else:
                results = [issue for issue, _ in similar_issues]

            # Apply additional filters if specified
            if status:
                results = [issue for issue in results if issue.status == status]
            if labels and isinstance(filter_obj.labels, list):
                results = [
                    issue
                    for issue in results
                    if issue.meta_data
                    and "labels" in issue.meta_data
                    and all(
                        label in issue.meta_data["labels"]
                        for label in filter_obj.labels
                    )
                ]
            if assignee:
                results = [
                    issue
                    for issue in results
                    if issue.meta_data
                    and "assignee" in issue.meta_data
                    and issue.meta_data["assignee"] == assignee
                ]

            # Limit results to requested count
            results = results[:limit]

            # Convert database Issue models to IssueResponse objects
            # Need to handle datetime conversion and add required fields
            response_items = []
            for issue in results:
                # Format datetime fields as ISO strings
                created_at_str = (
                    issue.created_at.isoformat() if issue.created_at else None
                )
                updated_at_str = (
                    issue.updated_at.isoformat() if issue.updated_at else None
                )

                # Convert metadata to dictionary if it's not already
                metadata_dict = dict(issue.meta_data) if issue.meta_data else {}

                # Find the project and organization names
                issue_project = crud_project.get(db, id=issue.project_id)
                project_name = None
                organization_name = None
                if issue_project:
                    project_name = issue_project.name
                    issue_org = crud_organization.get(
                        db, id=issue_project.organization_id
                    )
                    if issue_org:
                        organization_name = issue_org.name

                # Determine the URL
                external_url = metadata_dict.get("url") or issue.external_url

                # Create response object with updated fields
                response_item = IssueResponse(
                    id=issue.external_id or issue.id,  # Prioritize external_id
                    title=issue.title,
                    description=issue.description,
                    status=issue.status,
                    priority=issue.priority,
                    organization=organization_name,
                    project=project_name,
                    url=external_url
                    or f"https://spacebridge.io/issues/{issue.id}",  # Final fallback
                    created_at=created_at_str,
                    updated_at=updated_at_str,
                    metadata=metadata_dict,
                    labels=metadata_dict.get("labels", [])
                    if isinstance(metadata_dict.get("labels"), list)
                    else [],
                    assignee=metadata_dict.get("assignee"),
                )
                response_items.append(response_item)

            return response_items
        else:
            # Use regular text search (Needs similar update if used)
            # TODO: Update this part if regular search is still needed and should return IssueResponse
            issues = crud_issue.search(db, project_id=proj.id, filter_obj=filter_obj)
            # This part needs updating to fetch names and use external_id like above
            # For now, returning raw issues might be safer until fully implemented
            # return [IssueResponse.from_orm(issue) for issue in issues] # Old way
            # Placeholder: Return raw issues or implement full conversion
            logger.warning("Regular issue search response format needs updating.")
            # Returning empty list for now to avoid errors with mismatched schema
            return []
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
) -> IssueResponse:
    """Create a new issue in a specified project.

    Supports specifying organization/project by:
    - ID (organization_id/project_id)
    - Name (organization_name/project_name)
    - Identifier (organization/project - deprecated)
    """
    try:
        # Resolve organization and project using either ID, name, or identifier
        from spacemodels.crud import crud_organization, crud_project

        # Process organization parameters (prioritize new parameters over deprecated ones)
        org = None
        org_id = None

        if issue.organization_id:
            org = crud_organization.get(db, id=issue.organization_id)
            if org:
                org_id = org.id
        elif issue.organization:
            org = crud_organization.get_by_name(db, name=issue.organization)
            if org:
                org_id = org.id

        if not org_id:
            raise HTTPException(status_code=400, detail="Organization not found")

        # Process project parameters
        proj = None
        proj_id = None

        if issue.project_id:
            proj = crud_project.get(db, id=issue.project_id)
            if proj:
                proj_id = proj.id
        elif issue.project:
            # If we have an organization, use it to narrow down the project search
            proj = crud_project.get_by_name(
                db, name=issue.project, organization_id=org_id
            )
            if proj:
                proj_id = proj.id

        if not proj_id or not proj:  # Ensure proj object is available
            raise HTTPException(status_code=400, detail="Project not found")

        # Get the tracker client using the resolved IDs
        tracker_client = await get_tracker_client(org_id, proj_id, db)

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
):
    """Get details of a specific issue using its external ID."""
    try:
        # Find the issue by external_id
        # TODO: Add get_by_external_id to CRUDIssue if it doesn't exist
        issue = db.query(Issue).filter(Issue.external_id == issue_id).first()
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
        tracker_client = await get_tracker_client(org_obj.id, proj_obj.id, db)

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
):
    """Delete an issue using its external ID."""
    try:
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
        tracker_client = await get_tracker_client(org_obj.id, proj_obj.id, db)

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
