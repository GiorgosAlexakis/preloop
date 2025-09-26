"""
Endpoints for handling MCP (Model Context Protocol) tool calls via HTTP.

This module provides a secure, scalable, and integrated way for MCP clients
to interact with the SpaceBridge platform using FastMCP.
"""

import asyncio
import logging
import re
from typing import Optional, Dict, List, Literal
from sqlalchemy.exc import SQLAlchemyError

from fastapi import HTTPException

from spacebridge.api.common import (
    get_tracker_client,
    load_compliance_prompts_config,
)

from spacebridge.api.endpoints.issues import (
    create_issue as api_create_issue,
)
from spacebridge.api.endpoints.search import (
    perform_search,
    SearchResponse as ApiSearchResponse,
)
from spacebridge.api.endpoints.issue_compliance import (
    _calculate_issue_compliance,
    get_compliance_improvement_suggestion as api_get_compliance_suggestion,
)
from spacebridge.schemas.issue import IssueCreate, IssueUpdate
from spacebridge.services.billing import BillingService
from spacebridge.schemas.mcp import (
    GetIssueResponse,
    CreateIssueResponse,
    UpdateIssueResponse,
    EstimateComplianceResponse,
    ImproveComplianceResponse,
    ProcessingMetadata,
    SuggestedUpdate,
    UpdateIssueRequest,
)

from spacebridge.services.duplicate_detection import DuplicateDetector
from spacebridge.config import get_settings
from spacebridge.api.endpoints.billing import get_billing_service
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
        issue_obj = _find_issue_by_identifier(db, issue, current_user.id)
    except IssueNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

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
        db, slug_or_identifier=project, account_id=current_user.id
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
    try:
        issue_obj = _find_issue_by_identifier(db, issue, current_user.id)
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
        db, slug_or_identifier=project, account_id=current_user.id
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
    billing_service = get_billing_service(db)

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
                billing_service=billing_service,
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
    billing_service: BillingService = None,
) -> ProcessingResult:
    """Process compliance estimation for a single issue."""
    try:
        # Find the issue using our enhanced lookup
        issue_obj = _find_issue_by_identifier(db, issue_identifier, current_user.id)

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
            billing_service=billing_service,
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
    billing_service: BillingService = None,
) -> ProcessingResult:
    """Process compliance improvement for a single issue."""
    try:
        # Find the issue using our enhanced lookup
        issue = _find_issue_by_identifier(db, issue_identifier, current_user.id)

        # Get compliance suggestion
        suggestion = api_get_compliance_suggestion(
            issue_id=issue.id,
            prompt_name=prompt_name,
            db=db,
            current_user=current_user,
            settings=settings,
            billing_service=billing_service,
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
    billing_service = get_billing_service(db)
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
                billing_service=billing_service,
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
