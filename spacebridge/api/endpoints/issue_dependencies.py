"""Endpoints for detecting dependencies between issues."""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from spacemodels.models.account import Account
from spacemodels.crud import (
    CRUDIssue,
    crud_ai_model,
    crud_issue_set,
    crud_issue_relationship,
)
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.issue import Issue
from spacebridge.api.auth import get_current_active_user
from pydantic import BaseModel, Field
import json
import openai

from spacebridge.services.billing import BillingService


# Schemas
class DependencyRequest(BaseModel):
    issue_ids: List[str] = Field(
        ..., description="A list of issue IDs to analyze for dependencies."
    )
    model_id: Optional[str] = Field(
        None, description="Optional AI Model ID to use for detection."
    )


class DependencyPair(BaseModel):
    source_issue_id: str = Field(
        ..., description="The ID of the issue that must be completed first."
    )
    dependent_issue_id: str = Field(
        ..., description="The ID of the issue that depends on the source issue."
    )
    reason: str = Field(..., description="A brief explanation of the dependency.")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="The model's confidence in this dependency."
    )
    issue_key: Optional[str] = Field(None, description="The key of the source issue.")
    dependency_key: Optional[str] = Field(
        None, description="The key of the dependent issue."
    )


class DependencyResponse(BaseModel):
    dependencies: List[DependencyPair]


logger = logging.getLogger(__name__)
router = APIRouter()
crud_issue = CRUDIssue(Issue)

# System Prompt for the AI model
SYSTEM_PROMPT = """
You are an expert project manager AI. Your task is to analyze a list of software development issues and identify dependencies between them.
An issue (B) is dependent on another issue (A) if A must be completed before B can be started or completed. Avoid circular dependencies.

You will be given a list of issues, each with an ID, title, project, and description.
Analyze the provided issues and identify all dependency pairs.

Respond with a JSON object containing a single key \"dependencies\".
The value of \"dependencies\" should be a list of JSON objects, where each object represents a dependency pair and has the following structure:
- \"source_issue_id\": The ID of the issue that must be completed first.
- \"dependent_issue_id\": The ID of the issue that depends on the source issue.
- \"reason\": A concise, 1-2 sentence explanation for why the dependency exists.
- \"confidence_score\": A float between 0.0 and 1.0 indicating your confidence in this dependency.
- \"issue_key\": The key of the source issue.
- \"dependency_key\": The key of the dependent issue.

If you find no dependencies, return an empty list: {\"dependencies\": []}.
"""


@router.post(
    "/issue-dependencies/detect",
    response_model=DependencyResponse,
    tags=["Issues", "AI"],
    summary="Detect dependencies between a list of issues using an AI model.",
)
def detect_issue_dependencies(
    request: DependencyRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Analyzes a list of issues to find potential dependencies between them.

    - **issue_ids**: A list of UUIDs for the issues to be analyzed.
    - **model_id**: Optional ID of a specific AI model to use. If not provided, the user's default model will be used.
    """
    if len(request.issue_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least two issue IDs are required for dependency analysis.",
        )

    billing_service = BillingService(db)

    # 1. Fetch issues from the database
    issues = []
    issue_map = {}
    for issue_id in request.issue_ids:
        issue = crud_issue.get(db, id=issue_id, account_id=current_user.id)
        if not issue:
            raise HTTPException(
                status_code=404, detail=f"Issue with ID '{issue_id}' not found."
            )
        issues.append(issue)
        issue_map[str(issue.id)] = issue

    # 2. Select AI Model
    if request.model_id:
        ai_model = crud_ai_model.get(db, id=request.model_id)
        if not ai_model or ai_model.account_id != current_user.id:
            raise HTTPException(
                status_code=404,
                detail=f"AI Model with ID '{request.model_id}' not found or access denied.",
            )
    else:
        ai_model = crud_ai_model.get_default_active_model(
            db, account_id=current_user.id
        )
        if not ai_model:
            raise HTTPException(
                status_code=404,
                detail="No default AI model configured for your account.",
            )

    # 3. Check for a cached IssueSet
    sorted_issue_ids = sorted(request.issue_ids)
    existing_sets = crud_issue_set.get_supersets_by_issues(
        db,
        issue_ids=sorted_issue_ids,
        ai_model_id=ai_model.id,
        account_id=current_user.id,
    )

    if existing_sets:
        logger.info(f"Cache hit for issue set with AI model {ai_model.id}.")
        # If a superset exists, we can return the cached relationships
        cached_relationships = crud_issue_relationship.get_relationships_for_issues(
            db, issue_ids=request.issue_ids
        )

        dependencies = []
        for rel in cached_relationships:
            if rel.type == "depends_on":
                source_issue = issue_map.get(str(rel.source_issue_id))
                dependent_issue = issue_map.get(str(rel.target_issue_id))

                if source_issue and dependent_issue:
                    dependencies.append(
                        DependencyPair(
                            source_issue_id=str(rel.source_issue_id),
                            dependent_issue_id=str(rel.target_issue_id),
                            reason=rel.reason or "No reason provided",
                            confidence_score=rel.confidence_score or 0.0,
                            issue_key=source_issue.key,
                            dependency_key=dependent_issue.key,
                        )
                    )
        return DependencyResponse(dependencies=dependencies)

    logger.info(f"Cache miss for issue set. Calling AI model {ai_model.id}.")

    # 4. Construct the user prompt
    issue_details = []
    for issue in issues:
        detail = (
            f"ID: {issue.id}\n"
            f"Project: {issue.project.name}\n"
            f"Title: {issue.title}\n"
            f"Description: {issue.description or 'No description provided.'}"
        )
        issue_details.append(detail)

    user_prompt = (
        "Please analyze the following issues for dependencies:\n\n---\n"
        + "\n\n---\n".join(issue_details)
    )

    # 5. Call the AI model
    try:
        client = openai.OpenAI(api_key=ai_model.api_key or openai.api_key)

        response = client.chat.completions.create(
            model=ai_model.model_identifier,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        billing_service.record_usage(
            account_id=current_user.id, metric="ai_calls", quantity=1
        )

        response_content = response.choices[0].message.content
        parsed_json = json.loads(response_content)

        dependencies_from_ai = parsed_json.get("dependencies", [])

        # 6. Store new relationships and add issue keys to the response
        for dep in dependencies_from_ai:
            source_id = dep.get("source_issue_id")
            target_id = dep.get("dependent_issue_id")

            # Validate that the AI is not hallucinating dependencies for issues not in the request
            if source_id not in request.issue_ids or target_id not in request.issue_ids:
                logger.warning(
                    f"AI returned dependency for an issue not in the request: {source_id} -> {target_id}"
                )
                continue

            try:
                crud_issue_relationship.create(
                    db,
                    source_issue_id=source_id,
                    target_issue_id=target_id,
                    type="depends_on",
                    reason=dep.get("reason"),
                    confidence_score=dep.get("confidence_score"),
                )
            except IntegrityError:
                db.rollback()
                logger.warning(
                    f"Duplicate dependency relationship: {source_id} -> {target_id}"
                )
            source_issue = issue_map.get(source_id)
            dependent_issue = issue_map.get(target_id)
            if source_issue:
                dep["issue_key"] = source_issue.key
            if dependent_issue:
                dep["dependency_key"] = dependent_issue.key

        # 7. Create a new IssueSet to mark this analysis as complete
        set_name = f"Analysis for {len(sorted_issue_ids)} issues at {datetime.utcnow().isoformat()}"
        crud_issue_set.create_and_remove_subsets(
            db,
            name=set_name,
            issue_ids=sorted_issue_ids,
            ai_model_id=ai_model.id,
            account_id=current_user.id,
        )

        return DependencyResponse(dependencies=dependencies_from_ai)

    except openai.APIError as e:
        logger.error(f"OpenAI API call failed: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to get dependency analysis from AI model."
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Error parsing AI model response: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing AI model response: {e}"
        )


class ExtendScanRequest(BaseModel):
    issue_ids: List[str] = Field(
        ..., description="The ID of the issues to start the scan from."
    )
    extend_by: int = Field(
        ..., gt=0, description="The number of new issues to include in the scan."
    )


@router.post(
    "/issue-dependencies/extend",
    response_model=DependencyResponse,  # Assuming it returns a similar response
    tags=["Issues", "AI"],
    summary="Extend dependency scan from a given issue.",
)
def extend_dependency_scan(
    request: ExtendScanRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Extends the dependency scan for a specific issue to find more related issues.

    - **issue_ids**: The IDs of the issues to extend the scan from.
    - **extend_by**: The number of additional issues to fetch and analyze.
    """
    if not request.issue_ids:
        raise HTTPException(
            status_code=400, detail="At least one issue ID is required."
        )

    billing_service = BillingService(db)

    # Fetch the first issue to determine the project context
    initial_issue = crud_issue.get(
        db, id=request.issue_ids[0], account_id=current_user.id
    )
    if not initial_issue:
        raise HTTPException(
            status_code=404, detail=f"Issue with ID '{request.issue_ids[0]}' not found."
        )
    project_id = initial_issue.project_id

    # 1. Get all issues for the project
    # Note: get_for_project is paginated, we might need a way to get ALL issues.
    # Assuming for now it returns enough issues or we get all of them.
    project_issues = crud_issue.get_for_project(
        db, project_id=project_id, limit=1000, account_id=current_user.id
    )  # Arbitrary high limit
    project_issue_ids = {str(issue.id) for issue in project_issues}

    # Select AI Model (same logic as detect_issue_dependencies)
    ai_model = crud_ai_model.get_default_active_model(db, account_id=current_user.id)
    if not ai_model:
        raise HTTPException(status_code=404, detail="No default AI model configured.")

    # 2. Get all supersets containing the initial issues
    existing_sets = crud_issue_set.get_supersets_by_issues(
        db,
        issue_ids=request.issue_ids,
        ai_model_id=ai_model.id,
        account_id=current_user.id,
    )

    # 3. Union all retrieved sets to get the final set of issues
    known_issue_ids = set(request.issue_ids)
    for issue_set in existing_sets:
        known_issue_ids.update(issue_set.issue_ids)

    # 4. Subtract the final set of issues from project_set
    unknown_issue_ids = project_issue_ids - known_issue_ids

    if not unknown_issue_ids:
        return DependencyResponse(dependencies=[])  # No remaining issues to scan

    # 5. Get the n most recent issues from unknown_set
    unknown_issues = [
        issue for issue in project_issues if str(issue.id) in unknown_issue_ids
    ]
    # Already sorted by created_at desc in get_for_project
    query_issues = unknown_issues[: request.extend_by]
    query_issue_ids = {str(issue.id) for issue in query_issues}

    # Combine requested and unscanned issues for analysis
    analysis_issue_ids = list(set(request.issue_ids).union(query_issue_ids))
    analysis_issues = [
        issue for issue in project_issues if str(issue.id) in analysis_issue_ids
    ]
    issue_map = {str(issue.id): issue for issue in analysis_issues}

    # 6. Call AI model to analyze the query_set
    issue_details = []
    for issue in analysis_issues:
        detail = (
            f"ID: {issue.id}\n"
            f"Project: {issue.project.name}\n"
            f"Title: {issue.title}\n"
            f"Description: {issue.description or 'No description provided.'}"
        )
        issue_details.append(detail)

    user_prompt = (
        "Please analyze the following issues for dependencies:\n\n---\n"
        + "\n\n---".join(issue_details)
    )

    try:
        client = openai.OpenAI(api_key=ai_model.api_key or openai.api_key)
        response = client.chat.completions.create(
            model=ai_model.model_identifier,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        billing_service.record_usage(
            account_id=current_user.id, metric="ai_calls", quantity=1
        )
        response_content = response.choices[0].message.content
        dependencies_from_ai = json.loads(response_content).get("dependencies", [])

        new_dependencies = []
        # 7. Store the new relationships
        for dep in dependencies_from_ai:
            source_id = dep.get("source_issue_id")
            target_id = dep.get("dependent_issue_id")

            if (
                source_id not in analysis_issue_ids
                or target_id not in analysis_issue_ids
            ):
                continue  # Skip hallucinated issues

            # Only consider new dependencies involving the query set
            if source_id not in query_issue_ids and target_id not in query_issue_ids:
                continue

            try:
                crud_issue_relationship.create(
                    db,
                    source_issue_id=source_id,
                    target_issue_id=target_id,
                    type="depends_on",
                    reason=dep.get("reason"),
                    confidence_score=dep.get("confidence_score"),
                )

            except IntegrityError:
                db.rollback()  # Rollback the session to a clean state
                logger.warning(
                    f"Duplicate relationship skipped: {source_id}-{target_id}"
                )
            source_issue = issue_map.get(source_id)
            dependent_issue = issue_map.get(target_id)
            if source_issue:
                dep["issue_key"] = source_issue.key
            if dependent_issue:
                dep["dependency_key"] = dependent_issue.key
            new_dependencies.append(dep)

        # 7b. Store the new combined set in the IssueSet table
        set_name = f"Extended analysis for {len(analysis_issue_ids)} issues at {datetime.utcnow().isoformat()}"
        crud_issue_set.create_and_remove_subsets(
            db,
            name=set_name,
            issue_ids=sorted(analysis_issue_ids),
            ai_model_id=ai_model.id,
            account_id=current_user.id,
        )

        # 8. Return the dependencies found
        return DependencyResponse(dependencies=new_dependencies)

    except openai.APIError as e:
        logger.error(f"OpenAI API call failed: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to get dependency analysis from AI model."
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Error parsing AI model response: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing AI model response: {e}"
        )
