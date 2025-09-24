"""
Endpoints for handling MCP (Model Context Protocol) tool calls via HTTP.

This module provides a secure, scalable, and integrated way for MCP clients
to interact with the SpaceBridge platform using FastMCP.
"""

import logging
import re
from typing import Optional, Dict, List
from sqlalchemy.exc import SQLAlchemyError

from fastapi import HTTPException

from spacebridge.api.common import get_tracker_client

from spacebridge.api.endpoints.issues import (
    create_issue as api_create_issue,
    search_issues as api_search_issues,
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
    GetIssueResponse,
    CreateIssueResponse,
    UpdateIssueResponse,
    EstimateComplianceResponse,
    ImproveComplianceResponse,
    SuggestedUpdate,
    UpdateIssueRequest,
)

from spacebridge.services.duplicate_detection import DuplicateDetector
from spacemodels.crud import (
    CRUDIssue,
    CRUDProject,
    CRUDOrganization,
    CRUDIssueComplianceResult,
)
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.issue import Issue
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.issue_compliance_result import IssueComplianceResult
from spacemodels.models.tracker import Tracker
from spacebridge.api.auth.jwt import get_user_from_token_if_valid
from fastmcp.server.dependencies import get_http_request


logger = logging.getLogger(__name__)

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
    elif re.match(r"^(?:([^/]+)/)?([^#]+)$", slug):
        proj, key = match.groups()
        return {"organization": None, "project": proj, "key": key}
    return {"organization": None, "project": None, "key": slug}


async def get_issue(
    issue: str,
) -> GetIssueResponse:
    """
    Handles the 'get_issue' tool call.
    """
    db = next(get_db())
    current_user = None
    authorization = get_http_request().headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]
        current_user = await get_user_from_token_if_valid(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Check if issue is a URL
    if issue.startswith("http"):
        issue_obj = crud_issue.get_by_external_url(
            db, external_url=issue, account_id=current_user.id
        )
        if not issue_obj:
            raise HTTPException(status_code=404, detail="Issue not found")
    else:
        issue_obj = crud_issue.get_by_key(db, key=issue, account_id=current_user.id)
        if not issue_obj:
            issue_obj = crud_issue.get_by_key_postfix(
                db, key_postfix=issue, account_id=current_user.id
            )
            if not issue_obj:
                raise HTTPException(status_code=404, detail="Issue not found")

    project_name = issue_obj.project.name
    organization_name = issue_obj.project.organization.name

    compliance_results = (
        db.query(IssueComplianceResult)
        .join(Issue, IssueComplianceResult.issue_id == Issue.id)
        .join(Project, Issue.project_id == Project.id)
        .join(Organization, Project.organization_id == Organization.id)
        .join(Tracker, Organization.tracker_id == Tracker.id)
        .filter(
            IssueComplianceResult.issue_id == issue_obj.id,
            Tracker.account_id == current_user.id,
        )
        .all()
    )

    return GetIssueResponse(
        id=str(issue_obj.id),
        external_id=issue_obj.external_id,
        key=issue_obj.key,
        title=issue_obj.title,
        description=issue_obj.description,
        status=issue_obj.status,
        priority=issue_obj.priority,
        organization=organization_name,
        project=project_name,
        project_id=issue_obj.project_id,
        url=issue_obj.external_url or f"https://spacebridge.io/issues/{issue_obj.id}",
        created_at=issue_obj.created_at,
        updated_at=issue_obj.updated_at,
        meta_data=issue_obj.meta_data,
        labels=issue_obj.meta_data.get("labels", []),
        assignee=issue_obj.meta_data.get("assignee", None),
        compliance_results=[c.to_dict() for c in compliance_results],
    )


async def create_issue(
    project: str,
    title: str,
    description: str,
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    similarity_search: bool = True,
) -> CreateIssueResponse:
    """
    Handles the 'create_issue' tool call.
    """
    db = next(get_db())
    current_user = None
    authorization = get_http_request().headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]
        current_user = await get_user_from_token_if_valid(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    project_obj = crud_project.get_by_slug_or_identifier(
        db, slug_or_identifier=project, account_id=current_user.id
    )
    if not project_obj:
        raise HTTPException(status_code=404, detail=f"Project '{project}' not found.")

    if similarity_search:
        combined_text = f"{title}\n\n{description}"
        try:
            search_results = await api_search_issues(
                query=combined_text,
                project=project_obj.name,
                search_type="similarity",
                limit=5,
                db=db,
                current_user=current_user,
            )
        except Exception as e:
            logger.error(f"Similarity search failed during duplicate check: {e}")
            search_results = []

        if search_results:
            detector = DuplicateDetector()
            potential_duplicates = [r.model_dump() for r in search_results]
            decision = await detector.check_duplicates(
                new_title=title,
                new_description=description,
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

    issue_create_schema = IssueCreate(
        title=title,
        description=description,
        project_id=project_obj.id,
        labels=labels,
        assignee=assignee,
        priority=priority,
        status=status,
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
        raise e
    except Exception as e:
        logger.error(f"Failed to create issue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create issue.")


async def update_issue(
    issue: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee: Optional[str] = None,
    labels: Optional[List[str]] = None,
) -> UpdateIssueResponse:
    """
    Handles the 'update_issue' tool call.
    """
    db = next(get_db())
    current_user = None
    authorization = get_http_request().headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]
        current_user = await get_user_from_token_if_valid(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Check if issue is a URL
    if issue.startswith("http"):
        issue_obj = crud_issue.get_by_external_url(
            db, external_url=issue, account_id=current_user.id
        )
        if not issue_obj:
            raise HTTPException(status_code=404, detail="Issue not found")
    else:
        issue_obj = crud_issue.get_by_key(db, key=issue, account_id=current_user.id)
        if not issue_obj:
            issue_obj = crud_issue.get_by_key_postfix(
                db, key_postfix=issue, account_id=current_user.id
            )
            if not issue_obj:
                raise HTTPException(status_code=404, detail="Issue not found")

    # --- Prepare Update Payload for Tracker ---
    # Use the base IssueUpdate schema expected by the tracker client
    issue_update = IssueUpdate()
    if title:
        issue_update.title = title
    if description:
        issue_update.description = description
    if status:
        issue_update.status = status
    if priority:
        issue_update.priority = priority
    if labels:
        issue_update.labels = labels
    if assignee:
        issue_update.assignee = assignee
    # Filter out None values, as tracker clients might interpret None as "clear this field"
    update_data_for_tracker = issue_update.model_dump(exclude_unset=True)

    if not update_data_for_tracker:
        logger.info(
            f"No fields provided to update for issue {issue_obj.id}. Skipping tracker update."
        )
    else:
        # --- Call Tracker Client ---
        tracker_client = await get_tracker_client(
            issue_obj.project.organization_id, issue_obj.project_id, db, current_user
        )

        if not issue_obj.external_id:
            logger.error(
                f"Cannot update issue {issue_obj.id} in tracker: Missing external_id."
            )
            raise HTTPException(
                status_code=400,
                detail="Cannot update issue in tracker: Missing external identifier.",
            )

        try:
            logger.info(
                f"Calling tracker client to update issue {issue_obj.external_id} with data: {update_data_for_tracker}"
            )
            # Use the issue's external_id for the tracker API call
            issue_repo_id = issue_obj.external_id
            if issue_obj.external_url:
                issue_repo_id = issue_obj.external_url.split("/")[-1]
            await tracker_client.update_issue(
                issue_repo_id, IssueUpdate(**update_data_for_tracker)
            )
            logger.info(
                f"Successfully updated issue {issue_obj.external_id} via tracker client."
            )
        except NotImplementedError:
            logger.warning(
                f"Tracker type {tracker_client.tracker_type} does not support updating issues."
            )
            # Decide if this should be an error or just a warning
            # raise HTTPException(status_code=501, detail="Issue updates not supported by this tracker type.")
        except Exception as e:
            logger.error(
                f"Error updating issue {issue_obj.external_id} via tracker client: {e}",
                exc_info=True,
            )
            # Depending on requirements, you might still update the local DB or raise an error
            raise HTTPException(
                status_code=502,
                detail=f"Failed to update issue in the external tracker: {str(e)}",
            )

        # --- Update Local DB ---
        # Prepare data for local DB update using the IssueUpdate model
        update_data_for_db = issue_update.model_dump(exclude_unset=True)

        if not update_data_for_db:
            logger.info(
                f"No fields provided to update for issue {issue_obj.id} in local DB."
            )
            # If we skipped tracker update due to no data, we might skip DB update too,
            # or just proceed to return the current state.
        else:
            try:
                logger.info(
                    f"Updating local DB for issue {issue_obj.id} with data: {update_data_for_db}"
                )
                # Update the local database record
                # Note: crud_issue.update expects the db object, the existing db_obj, and the update obj (Pydantic model or dict)
                updated_issue_db = crud_issue.update(
                    db=db, db_obj=issue_obj, obj_in=update_data_for_db
                )
                db.commit()
                db.refresh(
                    updated_issue_db
                )  # Ensure we have the latest data including timestamps
                issue_obj = updated_issue_db  # Use the updated object going forward
                logger.info(f"Successfully updated issue {issue_obj.id} in local DB.")
            except SQLAlchemyError as e:
                db.rollback()
                logger.error(
                    f"Database error updating issue {issue_obj.id}: {e}", exc_info=True
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
            issue_obj
        )  # Refresh again after potential commit/refresh inside update block
        project = crud_project.get(
            db, id=issue_obj.project_id, account_id=current_user.id
        )  # Re-fetch
        organization = (
            crud_organization.get(
                db, id=project.organization_id, account_id=current_user.id
            )
            if project
            else None
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

        meta_data = issue_obj.meta_data or {}
        labels_list = meta_data.get("labels", []) if isinstance(meta_data, dict) else []
        assignee = meta_data.get("assignee") if isinstance(meta_data, dict) else None
        external_url = (
            meta_data.get("url") or issue_obj.external_url or f"/issues/{issue_obj.id}"
        )  # Fallback URL

        # Construct the key using potentially updated slug/external_id
        final_response_key = (
            f"{project_slug}#{issue_obj.external_id}"
            if project_slug and issue_obj.external_id
            else str(issue_obj.id)
        )

    compliance_results = (
        db.query(IssueComplianceResult)
        .join(Issue, IssueComplianceResult.issue_id == Issue.id)
        .join(Project, Issue.project_id == Project.id)
        .join(Organization, Project.organization_id == Organization.id)
        .join(Tracker, Organization.tracker_id == Tracker.id)
        .filter(
            IssueComplianceResult.issue_id == issue_obj.id,
            Tracker.account_id == current_user.id,
        )
        .all()
    )
    project_name = issue_obj.project.name
    organization_name = issue_obj.project.organization.name
    return GetIssueResponse(
        id=str(issue_obj.id),
        external_id=issue_obj.external_id,
        key=issue_obj.key,
        title=issue_obj.title,
        description=issue_obj.description,
        status=issue_obj.status,
        priority=issue_obj.priority,
        organization=organization_name,
        project=project_name,
        project_id=issue_obj.project_id,
        url=issue_obj.external_url or f"https://spacebridge.io/issues/{issue_obj.id}",
        created_at=issue_obj.created_at,
        updated_at=issue_obj.updated_at,
        meta_data=issue_obj.meta_data,
        labels=issue_obj.meta_data.get("labels", []),
        assignee=issue_obj.meta_data.get("assignee", None),
        compliance_results=[c.to_dict() for c in compliance_results],
    )


async def search(
    query: str,
    project: Optional[str] = None,
    limit: int = 10,
) -> ApiSearchResponse:
    """
    Handles the 'search' tool call.
    """
    db = next(get_db())
    current_user = None
    authorization = get_http_request().headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]
        current_user = await get_user_from_token_if_valid(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        return await api_search_all(
            query=query,
            project=project,
            limit=limit,
            search_type="similarity",
            db=db,
            current_user=current_user,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to perform search for query '{query}': {e}")
        raise HTTPException(status_code=500, detail="Failed to perform search.")


async def estimate_compliance(
    issues: List[str],
) -> EstimateComplianceResponse:
    """
    Handles the 'estimate_compliance' tool call.
    """
    db = next(get_db())
    current_user = None
    authorization = get_http_request().headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]
        current_user = await get_user_from_token_if_valid(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    results = []
    for issue_slug in issues:
        slug_parts = _parse_issue_slug(issue_slug)
        key = slug_parts["key"]
        if not key:
            continue

        issue = crud_issue.get(db, id=key, account_id=current_user.id)
        if not issue:
            continue

        try:
            compliance_result = api_get_issue_compliance(
                issue_id=issue.id,
                prompt_name="default",
                db=db,
                current_user=current_user,
            )
            results.append(compliance_result)
        except HTTPException as e:
            logger.warning(
                f"Could not get compliance for issue '{issue_slug}': {e.detail}"
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred for issue '{issue_slug}': {e}")

    return EstimateComplianceResponse(results=results)


async def improve_compliance(
    issues: List[str],
) -> ImproveComplianceResponse:
    """
    Handles the 'improve_compliance' tool call.
    """
    db = next(get_db())
    current_user = None
    authorization = get_http_request().headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]
        current_user = await get_user_from_token_if_valid(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    suggested_updates = []
    for issue_slug in issues:
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
