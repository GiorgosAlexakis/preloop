"""
Endpoints for handling MCP (Model Context Protocol) tool calls via HTTP.

This module provides a secure, scalable, and integrated way for MCP clients
to interact with the Preloop platform using FastMCP.
"""

import asyncio
import logging
import re
from typing import Optional, Dict, List, Literal
from sqlalchemy.exc import SQLAlchemyError

from fastapi import HTTPException

from preloop.api.common import (
    get_tracker_client,
    load_compliance_prompts_config,
)

from preloop.api.endpoints.issues import (
    create_issue as api_create_issue,
)
from preloop.api.endpoints.search import (
    perform_search,
    SearchResponse as ApiSearchResponse,
)
from preloop.api.endpoints.issue_compliance import (
    _calculate_issue_compliance,
    get_compliance_improvement_suggestion as api_get_compliance_suggestion,
)
from preloop.schemas.issue import IssueCreate
from preloop.schemas.tracker_models import IssueUpdate
from preloop.schemas.mcp import (
    GetIssueResponse,
    CreateIssueResponse,
    UpdateIssueResponse,
    EstimateComplianceResponse,
    ImproveComplianceResponse,
    ProcessingMetadata,
    SuggestedUpdate,
    UpdateIssueRequest,
)

from preloop.services.duplicate_detection import DuplicateDetector
from preloop.config import get_settings
from preloop.models.crud import (
    CRUDIssue,
    CRUDProject,
    CRUDOrganization,
    CRUDIssueComplianceResult,
)
from preloop.models.db.session import get_db_session as get_db
from preloop.models.models.issue import Issue
from preloop.models.models.organization import Organization
from preloop.models.models.project import Project
from preloop.models.models.tracker import TrackerType
from preloop.models.models.issue_compliance_result import IssueComplianceResult
from preloop.api.auth.jwt import get_user_from_token_if_valid
from fastmcp.server.dependencies import get_http_request


logger = logging.getLogger(__name__)

crud_issue = CRUDIssue(Issue)
crud_project = CRUDProject(Project)
crud_organization = CRUDOrganization(Organization)
crud_issue_compliance_result = CRUDIssueComplianceResult(IssueComplianceResult)


class IssueProcessingError(Exception):
    """Exception for issue processing errors."""

    pass


class IssueNotFoundError(IssueProcessingError):
    """Exception for when an issue cannot be found."""

    pass


class ProcessingResult:
    """Container for processing results."""

    def __init__(
        self, success: bool, data=None, error: str = None, issue_identifier: str = None
    ):
        self.success = success
        self.data = data
        self.error = error
        self.issue_identifier = issue_identifier


async def _get_authenticated_user(request_headers):
    """Extract and authenticate user from request headers."""
    db = next(get_db())
    authorization = request_headers.get("authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split("Bearer ")[1]
    current_user = await get_user_from_token_if_valid(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return db, current_user


def _find_issue_by_identifier(db, identifier: str, account_id: str) -> Issue:
    """Find an issue by identifier (URL, key, or ID) with comprehensive lookup logic."""
    if not identifier or not identifier.strip():
        raise IssueNotFoundError(f"Empty or invalid issue identifier: '{identifier}'")

    identifier = identifier.strip()

    # Check if issue is a URL
    if identifier.startswith("http"):
        issue_obj = crud_issue.get_by_external_url(
            db, external_url=identifier, account_id=account_id
        )
        if not issue_obj:
            raise IssueNotFoundError(f"Issue not found by URL: {identifier}")
        return issue_obj

    # Try exact key match first
    issue_obj = crud_issue.get_by_key(db, key=identifier, account_id=account_id)
    if issue_obj:
        return issue_obj

    # Try key postfix match
    issue_obj = crud_issue.get_by_key_postfix(
        db, key_postfix=identifier, account_id=account_id
    )
    if issue_obj:
        return issue_obj

    # Try direct ID lookup if identifier looks like a UUID
    try:
        issue_obj = crud_issue.get(db, id=identifier, account_id=account_id)
        if issue_obj:
            return issue_obj
    except Exception:  # Catch potential UUID conversion errors
        pass

    raise IssueNotFoundError(f"Issue not found: {identifier}")


def _validate_issues_input(issues: List[str]) -> List[str]:
    """Validate and sanitize issues input."""
    if not issues:
        raise HTTPException(status_code=400, detail="No issues provided")

    if len(issues) > 100:  # Reasonable batch limit
        raise HTTPException(status_code=400, detail="Too many issues (max 100)")

    # Filter out empty strings and strip whitespace
    validated_issues = []
    for issue in issues:
        if isinstance(issue, str) and issue.strip():
            validated_issues.append(issue.strip())

    if not validated_issues:
        raise HTTPException(status_code=400, detail="No valid issues provided")

    return validated_issues


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


def _enrich_compliance_results(db_results):
    """Enrich compliance results with short_name from config."""
    settings = get_settings()
    prompts_config = load_compliance_prompts_config(settings.PROMPTS_FILE)
    enriched_results = []
    for result in db_results:
        prompt_data = prompts_config.get(result.prompt_id)
        if prompt_data:
            result_dict = result.to_dict()
            result_dict["short_name"] = prompt_data.get("short_name")
            enriched_results.append(result_dict)
    return enriched_results


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
    try:
        issue_obj = _find_issue_by_identifier(db, issue, current_user.account_id)
    except IssueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    project_name = issue_obj.project.name
    organization_name = issue_obj.project.organization.name
    project_identifier = issue_obj.project.identifier or issue_obj.project.slug

    # Get compliance results using CRUD layer
    compliance_results = crud_issue_compliance_result.get_for_issue(
        db, issue_id=issue_obj.id, account_id=str(current_user.account_id)
    )
    settings = get_settings()
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
        project_id=str(issue_obj.project_id),
        project_identifier=project_identifier,
        url=issue_obj.external_url
        or f"https://{settings.preloop_url}/issues/{issue_obj.id}",
        created_at=issue_obj.created_at,
        updated_at=issue_obj.updated_at,
        meta_data=issue_obj.meta_data,
        labels=issue_obj.meta_data.get("labels", []),
        assignee=issue_obj.meta_data.get("assignee", None),
        compliance_results=_enrich_compliance_results(compliance_results),
    )


async def create_issue(
    project: str,
    title: str,
    description: str,
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    prevent_duplicates: bool = True,
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
        db, slug_or_identifier=project, account_id=str(current_user.account_id)
    )
    if not project_obj:
        raise HTTPException(status_code=404, detail=f"Project '{project}' not found.")

    if prevent_duplicates:
        combined_text = f"{title}\n\n{description}"
        try:
            search_response = await perform_search(
                query=combined_text,
                embedding_type="issue",
                project=project_obj.slug or project_obj.identifier,
                search_type="similarity",
                limit=5,
                db=db,
                current_user=current_user,
            )
            search_results = search_response.results
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
        project=project_obj.slug or project_obj.identifier,
        title=title,
        description=description,
        project_id=str(project_obj.id),
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
    try:
        issue_obj = _find_issue_by_identifier(db, issue, current_user.account_id)
    except IssueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

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
            # Determine the correct identifier for the tracker API call
            # Prefer using the key (e.g., "owner/repo#1" for GitHub) over external_id
            # since external_id might be the internal tracker ID (e.g., GitHub's numeric ID)
            issue_repo_id = issue_obj.key if issue_obj.key else issue_obj.external_id

            logger.info(
                f"Calling tracker client to update issue {issue_repo_id} with data: {update_data_for_tracker}"
            )
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
            db, id=issue_obj.project_id, account_id=str(current_user.account_id)
        )  # Re-fetch
        organization = (
            crud_organization.get(
                db, id=project.organization_id, account_id=str(current_user.account_id)
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

    # Get compliance results using CRUD layer
    compliance_results = crud_issue_compliance_result.get_for_issue(
        db, issue_id=issue_obj.id, account_id=str(current_user.account_id)
    )
    project_name = issue_obj.project.name
    organization_name = issue_obj.project.organization.name
    project_identifier = issue_obj.project.identifier or issue_obj.project.slug
    settings = get_settings()
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
        project_id=str(issue_obj.project_id),
        project_identifier=project_identifier,
        url=issue_obj.external_url
        or f"https://{settings.preloop_url}/issues/{issue_obj.id}",
        created_at=issue_obj.created_at,
        updated_at=issue_obj.updated_at,
        meta_data=issue_obj.meta_data,
        labels=issue_obj.meta_data.get("labels", []),
        assignee=issue_obj.meta_data.get("assignee", None),
        compliance_results=_enrich_compliance_results(compliance_results),
    )


async def search(
    query: str,
    project: Optional[str] = None,
    target_type: Literal["issue", "comment", "all"] = "all",
    search_type: Literal["similarity", "fulltext"] = "similarity",
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
    project_obj = crud_project.get_by_slug_or_identifier(
        db, slug_or_identifier=project, account_id=str(current_user.account_id)
    )
    if project_obj:
        project = project_obj.slug or project_obj.identifier
    else:
        project = None
    if target_type == "all":
        target_type = None
    try:
        return await perform_search(
            query=query,
            project=project,
            embedding_type=target_type,
            limit=limit,
            search_type=search_type,
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
    compliance_metric: str = "DoR",
) -> EstimateComplianceResponse:
    """
    Handles the 'estimate_compliance' tool call with enhanced parallel processing and error reporting.

    Args:
        issues: List of issue slugs/IDs/URLs to process
        compliance_metric: Name of the compliance metric to use (default: "DoR")

    Returns:
        Enhanced response with compliance results and processing metadata
    """
    # Validate input
    validated_issues = _validate_issues_input(issues)

    # Authenticate user
    db, current_user = await _get_authenticated_user(get_http_request().headers)
    settings = get_settings()

    # Process issues with controlled parallelism (max 10 concurrent)
    semaphore = asyncio.Semaphore(10)

    async def process_with_semaphore(issue_identifier: str) -> ProcessingResult:
        async with semaphore:
            return await _process_single_issue_estimate(
                issue_identifier,
                db,
                current_user,
                compliance_metric,
                settings=settings,
            )

    # Execute all tasks in parallel
    logger.info(f"Processing {len(validated_issues)} issues for compliance estimation")
    results = await asyncio.gather(
        *[
            process_with_semaphore(issue_identifier)
            for issue_identifier in validated_issues
        ],
        return_exceptions=True,
    )

    # Separate successful and failed results
    compliance_results = []
    failed_issues = []
    errors = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Handle unexpected exceptions from gather
            issue_identifier = validated_issues[i]
            error_msg = f"Processing exception: {str(result)}"
            failed_issues.append(issue_identifier)
            errors.append(f"{issue_identifier}: {error_msg}")
            logger.error(
                f"Exception processing issue '{issue_identifier}': {result}",
                exc_info=True,
            )
        elif result.success:
            compliance_results.append(result.data)
        else:
            failed_issues.append(result.issue_identifier)
            errors.append(f"{result.issue_identifier}: {result.error}")

    # Create processing metadata
    metadata = ProcessingMetadata(
        total_requested=len(validated_issues),
        successfully_processed=len(compliance_results),
        failed_count=len(failed_issues),
        failed_issues=failed_issues,
        errors=errors,
    )

    logger.info(
        f"Compliance estimation processing completed: "
        f"{metadata.successfully_processed}/{metadata.total_requested} successful, "
        f"{metadata.failed_count} failed"
    )

    return EstimateComplianceResponse(results=compliance_results, metadata=metadata)


async def _process_single_issue_estimate(
    issue_identifier: str,
    db,
    current_user,
    compliance_metric: str,
    settings=None,
) -> ProcessingResult:
    """Process compliance estimation for a single issue."""
    try:
        # Find the issue using our enhanced lookup
        issue_obj = _find_issue_by_identifier(
            db, issue_identifier, current_user.account_id
        )

        # Get compliance estimate
        prompt_name = (
            "dor_compliance_v1" if compliance_metric == "DoR" else compliance_metric
        )
        compliance_result = _calculate_issue_compliance(
            issue_id=issue_obj.id,
            prompt_name=prompt_name,
            db=db,
            current_user=current_user,
            settings=settings,
        )

        return ProcessingResult(
            success=True, data=compliance_result, issue_identifier=issue_identifier
        )

    except IssueNotFoundError as e:
        logger.warning(f"Issue not found: '{issue_identifier}': {str(e)}")
        return ProcessingResult(
            success=False,
            error=f"Issue not found: {str(e)}",
            issue_identifier=issue_identifier,
        )
    except HTTPException as e:
        logger.warning(
            f"Could not get compliance estimate for issue '{issue_identifier}': {e.detail}"
        )
        return ProcessingResult(
            success=False,
            error=f"API error: {e.detail}",
            issue_identifier=issue_identifier,
        )
    except Exception as e:
        logger.error(
            f"Unexpected error processing issue '{issue_identifier}': {e}",
            exc_info=True,
        )
        return ProcessingResult(
            success=False,
            error=f"Unexpected error: {str(e)}",
            issue_identifier=issue_identifier,
        )


async def _process_single_issue_compliance(
    issue_identifier: str,
    db,
    current_user,
    prompt_name: str = "default",
    settings=None,
) -> ProcessingResult:
    """Process compliance improvement for a single issue."""
    try:
        # Find the issue using our enhanced lookup
        issue = _find_issue_by_identifier(db, issue_identifier, current_user.account_id)

        # Get compliance suggestion
        suggestion = api_get_compliance_suggestion(
            issue_id=issue.id,
            prompt_name=prompt_name,
            db=db,
            current_user=current_user,
            settings=settings,
        )

        # Create suggested update
        update_args = UpdateIssueRequest(
            issue=issue_identifier,
            title=suggestion.title,
            description=suggestion.description,
        )
        suggested_update = SuggestedUpdate(arguments=update_args)

        return ProcessingResult(
            success=True, data=suggested_update, issue_identifier=issue_identifier
        )

    except IssueNotFoundError as e:
        logger.warning(f"Issue not found: '{issue_identifier}': {str(e)}")
        return ProcessingResult(
            success=False,
            error=f"Issue not found: {str(e)}",
            issue_identifier=issue_identifier,
        )
    except HTTPException as e:
        logger.warning(
            f"Could not get compliance suggestion for issue '{issue_identifier}': {e.detail}"
        )
        return ProcessingResult(
            success=False,
            error=f"API error: {e.detail}",
            issue_identifier=issue_identifier,
        )
    except Exception as e:
        logger.error(
            f"Unexpected error processing issue '{issue_identifier}': {e}",
            exc_info=True,
        )
        return ProcessingResult(
            success=False,
            error=f"Unexpected error: {str(e)}",
            issue_identifier=issue_identifier,
        )


async def improve_compliance(
    issues: List[str],
    compliance_metric: str = "DoR",
) -> ImproveComplianceResponse:
    """
    Handles the 'improve_compliance' tool call with enhanced error handling and parallel processing.

    Args:
        issues: List of issue slugs/IDs/URLs to process
        compliance_metric: Name of the compliance metric to use (default: "DoR")

    Returns:
        Enhanced response with suggested updates and processing metadata
    """
    # Validate input
    validated_issues = _validate_issues_input(issues)

    # Authenticate user
    db, current_user = await _get_authenticated_user(get_http_request().headers)
    settings = get_settings()

    # Process issues with controlled parallelism (max 10 concurrent)
    semaphore = asyncio.Semaphore(10)
    prompt_name = (
        "dor_compliance_v1" if compliance_metric == "DoR" else compliance_metric
    )

    async def process_with_semaphore(issue_identifier: str) -> ProcessingResult:
        async with semaphore:
            return await _process_single_issue_compliance(
                issue_identifier,
                db,
                current_user,
                prompt_name,
                settings=settings,
            )

    # Execute all tasks in parallel
    logger.info(
        f"Processing {len(validated_issues)} issues for compliance improvements"
    )
    results = await asyncio.gather(
        *[
            process_with_semaphore(issue_identifier)
            for issue_identifier in validated_issues
        ],
        return_exceptions=True,
    )

    # Separate successful and failed results
    suggested_updates = []
    failed_issues = []
    errors = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Handle unexpected exceptions from gather
            issue_identifier = validated_issues[i]
            error_msg = f"Processing exception: {str(result)}"
            failed_issues.append(issue_identifier)
            errors.append(f"{issue_identifier}: {error_msg}")
            logger.error(
                f"Exception processing issue '{issue_identifier}': {result}",
                exc_info=True,
            )
        elif result.success:
            suggested_updates.append(result.data)
        else:
            failed_issues.append(result.issue_identifier)
            errors.append(f"{result.issue_identifier}: {result.error}")

    # Create processing metadata
    metadata = ProcessingMetadata(
        total_requested=len(validated_issues),
        successfully_processed=len(suggested_updates),
        failed_count=len(failed_issues),
        failed_issues=failed_issues,
        errors=errors,
    )

    logger.info(
        f"Compliance improvement processing completed: "
        f"{metadata.successfully_processed}/{metadata.total_requested} successful, "
        f"{metadata.failed_count} failed"
    )

    return ImproveComplianceResponse(
        suggested_updates=suggested_updates, metadata=metadata
    )


async def add_comment(target: str, comment: str) -> "AddCommentResponse":
    """
    Handles the 'add_comment' tool call.

    Adds a comment to an issue, pull request, or merge request.

    Args:
        target: Issue/PR/MR identifier (URL, key, or ID)
        comment: Comment text to add

    Returns:
        AddCommentResponse with comment details
    """
    from preloop.schemas.mcp import AddCommentResponse

    db = next(get_db())
    current_user = None
    authorization = get_http_request().headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]
        current_user = await get_user_from_token_if_valid(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    target = target.strip()

    # Detect if target is a PR/MR URL and handle separately
    # PRs and MRs are not stored in the issue table, so we need different logic
    is_pull_request = False
    is_merge_request = False
    project_path = None
    pr_mr_number = None

    if target.startswith("http"):
        # GitHub PR URL: https://github.com/owner/repo/pull/123
        if "github.com" in target and "/pull/" in target:
            is_pull_request = True
            parts = target.split("/")
            if len(parts) >= 7:
                owner = parts[3]
                repo = parts[4]
                pr_mr_number = parts[6].rstrip("/").split("?")[0].split("#")[0]
                project_path = f"{owner}/{repo}"
                logger.info(f"Detected GitHub PR: {project_path}#{pr_mr_number}")
        # GitLab MR URL: https://gitlab.com/owner/repo/-/merge_requests/1
        elif "gitlab" in target and "merge_requests/" in target:
            is_merge_request = True
            mr_parts = target.split("merge_requests/")
            pr_mr_number = mr_parts[-1].rstrip("/").split("?")[0].split("#")[0]
            # Extract project path from URL
            url_path = mr_parts[0].split("://")[1].split("/")
            if len(url_path) >= 3:
                # Remove gitlab host and get project path (everything between host and /-/)
                project_path = "/".join(url_path[1:]).rstrip("/-")
                logger.info(f"Detected GitLab MR: {project_path}#{pr_mr_number}")
    # Parse slug format for PRs/MRs: owner/repo#123
    elif "/" in target and "#" in target:
        slug_parts = target.split("#")
        pr_mr_number = slug_parts[1]
        project_path = slug_parts[0]
        # Try to determine if it's a GitHub or GitLab project
        # We'll detect this after finding the project
        logger.info(f"Detected PR/MR slug format: {project_path}#{pr_mr_number}")

    # Handle PR/MR comments separately
    if is_pull_request or is_merge_request or (project_path and pr_mr_number):
        # Find the project
        if project_path:
            project_obj = crud_project.get_by_slug_or_identifier(
                db,
                slug_or_identifier=project_path,
                account_id=str(current_user.account_id),
            )
            if not project_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project not found for {project_path}",
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Could not parse project path from PR/MR identifier",
            )

        # Get tracker client
        tracker_client = await get_tracker_client(
            project_obj.organization_id, project_obj.id, db, current_user
        )

        # If we didn't detect the type yet, check the tracker type
        if not is_pull_request and not is_merge_request:
            if tracker_client.tracker_type.lower() == "github":
                is_pull_request = True
            elif tracker_client.tracker_type.lower() == "gitlab":
                is_merge_request = True

        # Use the appropriate tracker method
        target_id = pr_mr_number
    else:
        # This is a regular issue - use the existing logic
        parsed_key = None
        if target.startswith("http"):
            # GitHub issue URL: https://github.com/owner/repo/issues/123
            if "github.com" in target and "/issues/" in target:
                parts = target.split("/")
                if len(parts) >= 7:
                    owner = parts[3]
                    repo = parts[4]
                    issue_number = parts[6].rstrip("/").split("?")[0].split("#")[0]
                    parsed_key = f"{owner}/{repo}#{issue_number}"
                    logger.info(f"Parsed GitHub issue URL to key: {parsed_key}")
            # GitLab issue URL: https://gitlab.com/owner/repo/-/issues/1
            elif "gitlab" in target and "/issues/" in target:
                issue_parts = target.split("/issues/")
                issue_number = issue_parts[-1].rstrip("/").split("?")[0].split("#")[0]
                # Extract project path from URL
                url_path = issue_parts[0].split("://")[1].split("/")
                if len(url_path) >= 3:
                    # Remove gitlab host and get project path (everything between host and /-/)
                    project_path_tmp = "/".join(url_path[1:]).rstrip("/-")
                    parsed_key = f"{project_path_tmp}#{issue_number}"
                    logger.info(f"Parsed GitLab issue URL to key: {parsed_key}")

        # Try to find the issue
        issue_obj = None
        try:
            # First, try with the parsed key if we have one
            if parsed_key:
                try:
                    issue_obj = _find_issue_by_identifier(
                        db, parsed_key, current_user.account_id
                    )
                    logger.info(f"Found issue using parsed key: {parsed_key}")
                except IssueNotFoundError:
                    logger.info(
                        f"Could not find issue with parsed key {parsed_key}, trying original target"
                    )

            # If not found with parsed key, try the original target
            if not issue_obj:
                issue_obj = _find_issue_by_identifier(
                    db, target, current_user.account_id
                )
        except IssueNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # Get tracker client
        tracker_client = await get_tracker_client(
            issue_obj.project.organization_id, issue_obj.project_id, db, current_user
        )

        if not issue_obj.external_id and not issue_obj.key:
            logger.error(
                f"Cannot add comment to {target}: Missing external_id and key."
            )
            raise HTTPException(
                status_code=400,
                detail="Cannot add comment: Missing external identifier.",
            )

        # Use key if available, otherwise use external_id
        target_id = issue_obj.key if issue_obj.key else issue_obj.external_id

    try:
        logger.info(f"Adding comment to {target_id} via tracker client")
        created_comment = await tracker_client.add_comment(target_id, comment)
        logger.info(f"Successfully added comment to {target_id}")

        return AddCommentResponse(
            comment_id=created_comment.id,
            status="created",
            message=f"Successfully added comment to {target_id}",
            url=created_comment.meta_data.get("url")
            if hasattr(created_comment, "meta_data")
            else None,
        )
    except NotImplementedError:
        logger.warning(
            f"Tracker type {tracker_client.tracker_type} does not support adding comments."
        )
        raise HTTPException(
            status_code=501,
            detail="Adding comments not supported by this tracker type.",
        )
    except Exception as e:
        logger.error(
            f"Error adding comment to {target_id} via tracker client: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to add comment to the external tracker: {str(e)}",
        )


async def get_pull_request(pull_request: str) -> "PullRequestResponse":
    """
    Handles the 'get_pull_request' tool call.

    Gets details of a GitHub pull request.

    Args:
        pull_request: PR identifier (URL, slug, or number)

    Returns:
        PullRequestResponse with PR details
    """
    from preloop.schemas.mcp import PullRequestResponse

    db = next(get_db())
    db, current_user = await _get_authenticated_user(get_http_request().headers)

    # For PRs, we need to find the project by parsing the identifier
    # Try to match it against projects in the database
    # If it's a URL, extract org/repo from it
    # If it's a slug like "org/repo#123", parse it
    # If it's just a number, we'll need more context (use first GitHub project)

    pr_identifier = pull_request.strip()
    owner = None
    repo = None
    pr_number = pr_identifier

    # Parse URL format: https://github.com/owner/repo/pull/123
    if pr_identifier.startswith("http"):
        if "github.com" in pr_identifier:
            parts = pr_identifier.split("/")
            if len(parts) >= 5:
                owner = parts[3]
                repo = parts[4]
                if "pull" in parts:
                    pr_number = parts[parts.index("pull") + 1]
        else:
            raise HTTPException(
                status_code=400,
                detail="Only GitHub pull requests are supported. Use get_merge_request for GitLab.",
            )
    # Parse slug format: owner/repo#123
    elif "/" in pr_identifier and "#" in pr_identifier:
        slug_parts = pr_identifier.split("#")
        pr_number = slug_parts[1]
        repo_parts = slug_parts[0].split("/")
        if len(repo_parts) >= 2:
            owner = repo_parts[-2]
            repo = repo_parts[-1]

    # Find the project
    if owner and repo:
        # Try to find project by slug (owner/repo format)
        project_obj = crud_project.get_by_slug_or_identifier(
            db,
            slug_or_identifier=f"{owner}/{repo}",
            account_id=str(current_user.account_id),
        )
        if not project_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Project not found for {owner}/{repo}",
            )
    else:
        # Just a number - try to find first GitHub project
        from preloop.models.crud import crud_tracker

        trackers = crud_tracker.get_by_type(
            db, tracker_type=TrackerType.GITHUB, account_id=str(current_user.account_id)
        )
        if not trackers:
            raise HTTPException(
                status_code=404,
                detail="No GitHub tracker found. Please provide full PR identifier.",
            )

        # Get first project from first GitHub tracker
        tracker = trackers[0]
        from preloop.models.crud import crud_organization

        organizations = crud_organization.get_multi_by_tracker(
            db, tracker_id=tracker.id, account_id=current_user.account_id
        )
        if not organizations:
            raise HTTPException(
                status_code=404,
                detail="No organizations found for GitHub tracker.",
            )

        projects = crud_project.get_multi_by_organization(
            db, organization_id=organizations[0].id, account_id=current_user.account_id
        )
        if not projects:
            raise HTTPException(
                status_code=404,
                detail="No projects found. Please provide full PR identifier.",
            )

        project_obj = projects[0]

    # Get tracker client
    tracker_client = await get_tracker_client(
        project_obj.organization_id, project_obj.id, db, current_user
    )

    # Verify it's a GitHub tracker
    if tracker_client.tracker_type.lower() != "github":
        raise HTTPException(
            status_code=400,
            detail="get_pull_request only works with GitHub. Use get_merge_request for GitLab.",
        )

    try:
        logger.info(f"Getting pull request {pr_number} via tracker client")
        pr_data = await tracker_client.get_pull_request(pr_number)
        logger.info(f"Successfully retrieved pull request {pr_number}")

        return PullRequestResponse(**pr_data)

    except Exception as e:
        logger.error(
            f"Error getting pull request {pr_number} via tracker client: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to get pull request from GitHub: {str(e)}",
        )


async def get_merge_request(merge_request: str) -> "MergeRequestResponse":
    """
    Handles the 'get_merge_request' tool call.

    Gets details of a GitLab merge request.

    Args:
        merge_request: MR identifier (URL, slug, or IID)

    Returns:
        MergeRequestResponse with MR details
    """
    from preloop.schemas.mcp import MergeRequestResponse

    db = next(get_db())
    db, current_user = await _get_authenticated_user(get_http_request().headers)

    mr_identifier = merge_request.strip()
    project_path = None
    mr_iid = mr_identifier

    # Parse URL format: https://gitlab.com/owner/repo/-/merge_requests/1
    if mr_identifier.startswith("http"):
        if "gitlab" in mr_identifier:
            if "merge_requests" in mr_identifier:
                parts = mr_identifier.split("merge_requests/")
                mr_iid = parts[-1].rstrip("/")
                # Extract project path from URL
                url_parts = parts[0].split("://")[1].split("/")
                if len(url_parts) >= 3:
                    # Remove gitlab host and get project path
                    project_path = "/".join(url_parts[1:]).rstrip("/-")
        else:
            raise HTTPException(
                status_code=400,
                detail="Only GitLab merge requests are supported. Use get_pull_request for GitHub.",
            )
    # Parse slug format: owner/repo#1
    elif "/" in mr_identifier and "#" in mr_identifier:
        slug_parts = mr_identifier.split("#")
        mr_iid = slug_parts[1]
        project_path = slug_parts[0]

    # Find the project
    if project_path:
        project_obj = crud_project.get_by_slug_or_identifier(
            db, slug_or_identifier=project_path, account_id=str(current_user.account_id)
        )
        if not project_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Project not found for {project_path}",
            )
    else:
        # Just a number - try to find first GitLab project
        from preloop.models.crud import crud_tracker

        trackers = crud_tracker.get_by_type(
            db, tracker_type=TrackerType.GITLAB, account_id=str(current_user.account_id)
        )
        if not trackers:
            raise HTTPException(
                status_code=404,
                detail="No GitLab tracker found. Please provide full MR identifier.",
            )

        # Get first project from first GitLab tracker
        tracker = trackers[0]
        from preloop.models.crud import crud_organization

        organizations = crud_organization.get_multi_by_tracker(
            db, tracker_id=tracker.id, account_id=current_user.account_id
        )
        if not organizations:
            raise HTTPException(
                status_code=404,
                detail="No organizations found for GitLab tracker.",
            )

        projects = crud_project.get_multi_by_organization(
            db, organization_id=organizations[0].id, account_id=current_user.account_id
        )
        if not projects:
            raise HTTPException(
                status_code=404,
                detail="No projects found. Please provide full MR identifier.",
            )

        project_obj = projects[0]

    # Get tracker client
    tracker_client = await get_tracker_client(
        project_obj.organization_id, project_obj.id, db, current_user
    )

    # Verify it's a GitLab tracker
    if tracker_client.tracker_type.lower() != "gitlab":
        raise HTTPException(
            status_code=400,
            detail="get_merge_request only works with GitLab. Use get_pull_request for GitHub.",
        )

    try:
        logger.info(f"Getting merge request {mr_iid} via tracker client")
        mr_data = await tracker_client.get_merge_request(mr_iid)
        logger.info(f"Successfully retrieved merge request {mr_iid}")

        return MergeRequestResponse(**mr_data)

    except Exception as e:
        logger.error(
            f"Error getting merge request {mr_iid} via tracker client: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to get merge request from GitLab: {str(e)}",
        )


async def update_pull_request(
    pull_request: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    state: Optional[str] = None,
    assignees: Optional[List[str]] = None,
    reviewers: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    draft: Optional[bool] = None,
) -> "UpdatePullRequestResponse":
    """
    Handles the 'update_pull_request' tool call.

    Updates a GitHub pull request.

    Args:
        pull_request: PR identifier (URL, slug, or number)
        title: New title for the PR
        description: New description for the PR
        state: New state ("open" or "closed")
        assignees: List of assignee usernames
        reviewers: List of reviewer usernames
        labels: List of label names
        draft: Whether to mark as draft

    Returns:
        UpdatePullRequestResponse with update status
    """
    from preloop.schemas.mcp import UpdatePullRequestResponse

    db, current_user = await _get_authenticated_user(get_http_request().headers)

    pr_identifier = pull_request.strip()
    owner = None
    repo = None
    pr_number = pr_identifier

    # Parse URL format: https://github.com/owner/repo/pull/123
    if pr_identifier.startswith("http"):
        if "github.com" in pr_identifier:
            parts = pr_identifier.split("/")
            if len(parts) >= 5:
                owner = parts[3]
                repo = parts[4]
                if "pull" in parts:
                    pr_number = parts[parts.index("pull") + 1]
        else:
            raise HTTPException(
                status_code=400,
                detail="Only GitHub pull requests are supported. Use update_merge_request for GitLab.",
            )
    # Parse slug format: owner/repo#123
    elif "/" in pr_identifier and "#" in pr_identifier:
        slug_parts = pr_identifier.split("#")
        pr_number = slug_parts[1]
        repo_parts = slug_parts[0].split("/")
        if len(repo_parts) >= 2:
            owner = repo_parts[-2]
            repo = repo_parts[-1]

    # Find the project
    if owner and repo:
        project_obj = crud_project.get_by_slug_or_identifier(
            db,
            slug_or_identifier=f"{owner}/{repo}",
            account_id=str(current_user.account_id),
        )
        if not project_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Project not found for {owner}/{repo}",
            )
    else:
        # Just a number - try to find first GitHub project
        from preloop.models.crud import crud_tracker

        trackers = crud_tracker.get_by_type(
            db, tracker_type=TrackerType.GITHUB, account_id=str(current_user.account_id)
        )
        if not trackers:
            raise HTTPException(
                status_code=404,
                detail="No GitHub tracker found. Please provide full PR identifier.",
            )

        tracker = trackers[0]
        from preloop.models.crud import crud_organization

        organizations = crud_organization.get_multi_by_tracker(
            db, tracker_id=tracker.id, account_id=current_user.account_id
        )
        if not organizations:
            raise HTTPException(
                status_code=404,
                detail="No organizations found for GitHub tracker.",
            )

        projects = crud_project.get_multi_by_organization(
            db, organization_id=organizations[0].id, account_id=current_user.account_id
        )
        if not projects:
            raise HTTPException(
                status_code=404,
                detail="No projects found. Please provide full PR identifier.",
            )

        project_obj = projects[0]

    # Get tracker client
    tracker_client = await get_tracker_client(
        project_obj.organization_id, project_obj.id, db, current_user
    )

    # Verify it's a GitHub tracker
    if tracker_client.tracker_type.lower() != "github":
        raise HTTPException(
            status_code=400,
            detail="update_pull_request only works with GitHub. Use update_merge_request for GitLab.",
        )

    try:
        logger.info(f"Updating pull request {pr_number} via tracker client")
        pr_data = await tracker_client.update_pull_request(
            pr_identifier=pr_number,
            title=title,
            description=description,
            state=state,
            assignees=assignees,
            reviewers=reviewers,
            labels=labels,
            draft=draft,
        )
        logger.info(f"Successfully updated pull request {pr_number}")

        return UpdatePullRequestResponse(
            pull_request_id=pr_data.get("id"),
            status="updated",
            message=f"Successfully updated pull request {pr_number}",
            url=pr_data.get("url"),
        )

    except Exception as e:
        logger.error(
            f"Error updating pull request {pr_number} via tracker client: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to update pull request in GitHub: {str(e)}",
        )


async def update_merge_request(
    merge_request: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    state_event: Optional[str] = None,
    assignee_ids: Optional[List[int]] = None,
    reviewer_ids: Optional[List[int]] = None,
    labels: Optional[List[str]] = None,
    draft: Optional[bool] = None,
) -> "UpdateMergeRequestResponse":
    """
    Handles the 'update_merge_request' tool call.

    Updates a GitLab merge request.

    Args:
        merge_request: MR identifier (URL, slug, or IID)
        title: New title for the MR
        description: New description for the MR
        state_event: State event ("close" or "reopen")
        assignee_ids: List of assignee user IDs
        reviewer_ids: List of reviewer user IDs
        labels: List of label names
        draft: Whether to mark as draft/WIP

    Returns:
        UpdateMergeRequestResponse with update status
    """
    from preloop.schemas.mcp import UpdateMergeRequestResponse

    db, current_user = await _get_authenticated_user(get_http_request().headers)

    mr_identifier = merge_request.strip()
    project_path = None
    mr_iid = mr_identifier

    # Parse URL format: https://gitlab.com/owner/repo/-/merge_requests/1
    if mr_identifier.startswith("http"):
        if "gitlab" in mr_identifier:
            if "merge_requests" in mr_identifier:
                parts = mr_identifier.split("merge_requests/")
                mr_iid = parts[-1].rstrip("/")
                # Extract project path from URL
                url_parts = parts[0].split("://")[1].split("/")
                if len(url_parts) >= 3:
                    # Remove gitlab host and get project path
                    project_path = "/".join(url_parts[1:]).rstrip("/-")
        else:
            raise HTTPException(
                status_code=400,
                detail="Only GitLab merge requests are supported. Use update_pull_request for GitHub.",
            )
    # Parse slug format: owner/repo#1
    elif "/" in mr_identifier and "#" in mr_identifier:
        slug_parts = mr_identifier.split("#")
        mr_iid = slug_parts[1]
        project_path = slug_parts[0]

    # Find the project
    if project_path:
        project_obj = crud_project.get_by_slug_or_identifier(
            db, slug_or_identifier=project_path, account_id=str(current_user.account_id)
        )
        if not project_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Project not found for {project_path}",
            )
    else:
        # Just a number - try to find first GitLab project
        from preloop.models.crud import crud_tracker

        trackers = crud_tracker.get_by_type(
            db, tracker_type=TrackerType.GITLAB, account_id=str(current_user.account_id)
        )
        if not trackers:
            raise HTTPException(
                status_code=404,
                detail="No GitLab tracker found. Please provide full MR identifier.",
            )

        tracker = trackers[0]
        from preloop.models.crud import crud_organization

        organizations = crud_organization.get_multi_by_tracker(
            db, tracker_id=tracker.id, account_id=current_user.account_id
        )
        if not organizations:
            raise HTTPException(
                status_code=404,
                detail="No organizations found for GitLab tracker.",
            )

        projects = crud_project.get_multi_by_organization(
            db, organization_id=organizations[0].id, account_id=current_user.account_id
        )
        if not projects:
            raise HTTPException(
                status_code=404,
                detail="No projects found. Please provide full MR identifier.",
            )

        project_obj = projects[0]

    # Get tracker client
    tracker_client = await get_tracker_client(
        project_obj.organization_id, project_obj.id, db, current_user
    )

    # Verify it's a GitLab tracker
    if tracker_client.tracker_type.lower() != "gitlab":
        raise HTTPException(
            status_code=400,
            detail="update_merge_request only works with GitLab. Use update_pull_request for GitHub.",
        )

    try:
        logger.info(f"Updating merge request {mr_iid} via tracker client")
        mr_data = await tracker_client.update_merge_request(
            mr_identifier=mr_iid,
            title=title,
            description=description,
            state_event=state_event,
            assignee_ids=assignee_ids,
            reviewer_ids=reviewer_ids,
            labels=labels,
            draft=draft,
        )
        logger.info(f"Successfully updated merge request {mr_iid}")

        return UpdateMergeRequestResponse(
            merge_request_id=mr_data.get("id"),
            status="updated",
            message=f"Successfully updated merge request {mr_iid}",
            url=mr_data.get("url"),
        )

    except Exception as e:
        logger.error(
            f"Error updating merge request {mr_iid} via tracker client: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to update merge request in GitLab: {str(e)}",
        )
