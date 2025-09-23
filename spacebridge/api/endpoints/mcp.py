"""
Endpoints for handling MCP (Model Context Protocol) tool calls via HTTP.

This module provides a secure, scalable, and integrated way for MCP clients
to interact with the SpaceBridge platform.
"""

import logging
import re
from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from spacebridge.api.auth import get_current_active_user
from spacebridge.api.endpoints.issues import (
    create_issue as api_create_issue,
    search_issues as api_search_issues,
    update_issue as api_update_issue,
)
from spacebridge.api.endpoints.search import (
    search_all as api_search_all,
    SearchResponse as ApiSearchResponse,
)
from spacebridge.api.endpoints.issue_compliance import (
    get_issue_compliance as api_get_issue_compliance,
    get_compliance_improvement_suggestion as api_get_compliance_suggestion,
)
from spacebridge.schemas.issue import IssueCreate, IssueUpdate
from spacebridge.schemas.mcp import (
    GetIssueRequest,
    GetIssueResponse,
    CreateIssueRequest,
    CreateIssueResponse,
    UpdateIssueRequest,
    UpdateIssueResponse,
    SearchRequest,
    EstimateComplianceRequest,
    EstimateComplianceResponse,
    ImproveComplianceRequest,
    ImproveComplianceResponse,
    SuggestedUpdate,
)
from spacebridge.services.duplicate_detection import DuplicateDetector
from spacemodels.crud import (
    CRUDIssue,
    CRUDProject,
    CRUDOrganization,
    CRUDIssueComplianceResult,
)
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.account import Account
from spacemodels.models.issue import Issue
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.issue_compliance_result import IssueComplianceResult
from spacemodels.models.tracker import Tracker

logger = logging.getLogger(__name__)
router = APIRouter()

crud_issue = CRUDIssue(Issue)
crud_project = CRUDProject(Project)
crud_organization = CRUDOrganization(Organization)
crud_issue_compliance_result = CRUDIssueComplianceResult(IssueComplianceResult)


def _parse_issue_slug(slug: str) -> Dict[str, Optional[str]]:
    """
    Parses a full issue slug into its components.
    Handles formats: org/project#key, project#key, or a standalone key/UUID.
    """
    match = re.match(r"^(?:([^/]+)/)?([^#]+)#(.+)$", slug)
    if match:
        org, proj, key = match.groups()
        return {"organization": org, "project": proj, "key": key}
    return {"organization": None, "project": None, "key": slug}


@router.post(
    "/mcp/get_issue", response_model=GetIssueResponse, summary="MCP Tool: Get Issue"
)
async def mcp_get_issue(
    request: GetIssueRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Handles the 'get_issue' tool call.

    Retrieves a specific issue by its URL or slug, including compliance data.
    """
    slug_parts = _parse_issue_slug(request.issue)
    key = slug_parts["key"]
    project_slug = slug_parts["project"]
    org_slug = slug_parts["organization"]

    if not key:
        raise HTTPException(status_code=400, detail="Issue key could not be parsed.")

    issue = None
    project = None

    if project_slug:
        project = crud_project.get_by_slug_or_identifier(
            db, slug_or_identifier=project_slug, account_id=current_user.id
        )
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_slug}' not found."
            )
        if org_slug:
            organization = crud_organization.get(
                db, id=project.organization_id, account_id=current_user.id
            )
            if not organization or organization.name != org_slug:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{project_slug}' not found in organization '{org_slug}'.",
                )
        issue = (
            db.query(Issue)
            .filter(Issue.key == key, Issue.project_id == project.id)
            .first()
        )
    else:
        # If no project context, try to find the issue by its UUID
        try:
            issue = crud_issue.get(db, id=key, account_id=current_user.id)
        except Exception:
            # Not a valid UUID, or not found
            pass

    if not issue:
        raise HTTPException(
            status_code=404,
            detail=f"Issue '{request.issue}' not found. If using a non-unique key, please provide the project context (e.g., 'project-slug#{key}').",
        )

    # Re-fetch project and org for the response model if they weren't part of the query
    if not project:
        project = crud_project.get(db, id=issue.project_id, account_id=current_user.id)

    project_name = project.name if project else None
    organization_name = None
    if project:
        organization = crud_organization.get(
            db, id=project.organization_id, account_id=current_user.id
        )
        if organization:
            organization_name = organization.name

    metadata_dict = dict(issue.meta_data) if issue.meta_data else {}
    external_url = metadata_dict.get("url") or issue.external_url

    # Fetch compliance results
    compliance_results = (
        db.query(IssueComplianceResult)
        .join(Issue, IssueComplianceResult.issue_id == Issue.id)
        .join(Project, Issue.project_id == Project.id)
        .join(Organization, Project.organization_id == Organization.id)
        .join(Tracker, Organization.tracker_id == Tracker.id)
        .filter(
            IssueComplianceResult.issue_id == issue.id,
            Tracker.account_id == current_user.id,
        )
        .all()
    )

    return GetIssueResponse(
        id=str(issue.id),
        external_id=issue.external_id,
        key=issue.key,
        title=issue.title,
        description=issue.description,
        status=issue.status,
        priority=issue.priority,
        organization=organization_name,
        project=project_name,
        project_id=issue.project_id,
        url=external_url or f"https://spacebridge.io/issues/{issue.id}",
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        meta_data=metadata_dict,
        labels=metadata_dict.get("labels", []),
        assignee=metadata_dict.get("assignee"),
        compliance_results=compliance_results,
    )


@router.post(
    "/mcp/create_issue",
    response_model=CreateIssueResponse,
    summary="MCP Tool: Create Issue",
)
async def mcp_create_issue(
    request: CreateIssueRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Handles the 'create_issue' tool call.

    Creates a new issue after checking for potential duplicates.
    """
    project_slug = request.project
    project = crud_project.get_by_slug_or_identifier(
        db, slug_or_identifier=project_slug, account_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=404, detail=f"Project '{project_slug}' not found."
        )

    if request.similarity_search:
        # 1. Search for potential duplicates
        combined_text = f"{request.title}\n\n{request.description}"
        try:
            search_results = await api_search_issues(
                query=combined_text,
                project=project.name,
                search_type="similarity",
                limit=5,
                db=db,
                current_user=current_user,
            )
        except Exception as e:
            logger.error(f"Similarity search failed during duplicate check: {e}")
            search_results = []

        # 2. Perform duplicate check
        if search_results:
            detector = DuplicateDetector()
            # The detector expects a list of dicts.
            potential_duplicates = [r.model_dump() for r in search_results]
            decision = await detector.check_duplicates(
                new_title=request.title,
                new_description=request.description,
                potential_duplicates=potential_duplicates,
            )

            if decision.get("status") == "duplicate":
                dup_issue = decision.get("duplicate_issue", {})
                return CreateIssueResponse(
                    issue_id=dup_issue.get("id", "Unknown"),
                    status="existing_duplicate_found",
                    message=f"Duplicate detection found a likely match: {dup_issue.get('key')}",
                    url=dup_issue.get("url"),
                )

    # 3. Create the issue if no duplicates were found
    issue_create_schema = IssueCreate(
        title=request.title,
        description=request.description,
        project_id=project.id,
        labels=request.labels,
        assignee=request.assignee,
        priority=request.priority,
        status=request.status,
    )

    try:
        created_issue = await api_create_issue(
            issue=issue_create_schema, db=db, current_user=current_user
        )
        return CreateIssueResponse(
            issue_id=created_issue.id,
            status="created",
            message="Successfully created new issue.",
            url=created_issue.url,
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions from the create_issue call
        raise e
    except Exception as e:
        logger.error(f"Failed to create issue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create issue.")


@router.post(
    "/mcp/update_issue",
    response_model=UpdateIssueResponse,
    summary="MCP Tool: Update Issue",
)
async def mcp_update_issue(
    request: UpdateIssueRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Handles the 'update_issue' tool call.
    """
    slug_parts = _parse_issue_slug(request.issue)
    key = slug_parts["key"]

    if not key:
        raise HTTPException(status_code=400, detail="Issue key could not be parsed.")

    # The underlying api_update_issue handles finding the issue by key/UUID
    # and does not require project context for the update itself.
    issue_update_schema = IssueUpdate(
        title=request.title,
        description=request.description,
        status=request.status,
        priority=request.priority,
        assignee=request.assignee,
        labels=request.labels,
    )

    try:
        updated_issue = await api_update_issue(
            issue_id=key,  # Pass the key/UUID
            issue_update=issue_update_schema,
            db=db,
            current_user=current_user,
        )
        return UpdateIssueResponse(
            issue_id=updated_issue.id,
            status="updated",
            message="Successfully updated issue.",
            url=updated_issue.url,
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions from the update_issue call
        raise e
    except Exception as e:
        logger.error(f"Failed to update issue '{key}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update issue '{key}'.")


@router.post(
    "/mcp/search", response_model=ApiSearchResponse, summary="MCP Tool: Search"
)
async def mcp_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Handles the 'search' tool call.
    """
    try:
        return await api_search_all(
            query=request.query,
            project=request.project,
            limit=request.limit,
            search_type="similarity",  # Default to similarity for MCP
            db=db,
            current_user=current_user,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to perform search for query '{request.query}': {e}")
        raise HTTPException(status_code=500, detail="Failed to perform search.")


@router.post(
    "/mcp/estimate_compliance",
    response_model=EstimateComplianceResponse,
    summary="MCP Tool: Estimate Compliance",
)
async def mcp_estimate_compliance(
    request: EstimateComplianceRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Handles the 'estimate_compliance' tool call.
    """
    results = []
    for issue_slug in request.issues:
        slug_parts = _parse_issue_slug(issue_slug)
        key = slug_parts["key"]
        if not key:
            continue  # Skip invalid slugs

        # Find the issue first to get its ID
        issue = crud_issue.get(db, id=key, account_id=current_user.id)
        if not issue:
            continue  # Skip if issue not found

        try:
            # This assumes a single, default prompt for now.
            # A more advanced version could accept a prompt_name.
            compliance_result = api_get_issue_compliance(
                issue_id=issue.id,
                prompt_name="default",
                db=db,
                current_user=current_user,
            )
            results.append(compliance_result)
        except HTTPException as e:
            # Log or handle errors for individual issues
            logger.warning(
                f"Could not get compliance for issue '{issue_slug}': {e.detail}"
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred for issue '{issue_slug}': {e}")

    return EstimateComplianceResponse(results=results)


@router.post(
    "/mcp/improve_compliance",
    response_model=ImproveComplianceResponse,
    summary="MCP Tool: Improve Compliance",
)
async def mcp_improve_compliance(
    request: ImproveComplianceRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Handles the 'improve_compliance' tool call.
    """
    suggested_updates = []
    for issue_slug in request.issues:
        slug_parts = _parse_issue_slug(issue_slug)
        key = slug_parts["key"]
        if not key:
            continue

        issue = crud_issue.get(db, id=key, account_id=current_user.id)
        if not issue:
            continue

        try:
            suggestion = api_get_compliance_suggestion(
                issue_id=issue.id,
                prompt_name="default",
                db=db,
                current_user=current_user,
            )
            update_args = UpdateIssueRequest(
                issue=issue_slug,
                title=suggestion.title,
                description=suggestion.description,
            )
            suggested_updates.append(SuggestedUpdate(arguments=update_args))
        except HTTPException as e:
            logger.warning(
                f"Could not get compliance suggestion for issue '{issue_slug}': {e.detail}"
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred getting suggestion for '{issue_slug}': {e}"
            )

    return ImproveComplianceResponse(suggested_updates=suggested_updates)


# Other tool endpoints will be added here.
