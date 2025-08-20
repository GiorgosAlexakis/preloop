"""Endpoints for detecting dependencies between issues."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from spacemodels.models.account import Account
from spacemodels.crud import CRUDIssue
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.issue import Issue
from spacebridge.api.auth import get_current_active_user
from pydantic import BaseModel, Field
import json
import openai

from spacebridge.services.billing import BillingService
from spacemodels.crud import crud_ai_model


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


class DependencyResponse(BaseModel):
    dependencies: List[DependencyPair]


logger = logging.getLogger(__name__)
router = APIRouter()
crud_issue = CRUDIssue(Issue)

# System Prompt for the AI model
SYSTEM_PROMPT = """
You are an expert project manager AI. Your task is to analyze a list of software development issues and identify dependencies between them.
An issue (B) is dependent on another issue (A) if A must be completed before B can be started or completed.

You will be given a list of issues, each with an ID, title, project, and description.
Analyze the provided issues and identify all dependency pairs.

Respond with a JSON object containing a single key \"dependencies\".
The value of \"dependencies\" should be a list of JSON objects, where each object represents a dependency pair and has the following structure:
- \"source_issue_id\": The ID of the issue that must be completed first.
- \"dependent_issue_id\": The ID of the issue that depends on the source issue.
- \"reason\": A concise, 1-2 sentence explanation for why the dependency exists.
- \"confidence_score\": A float between 0.0 and 1.0 indicating your confidence in this dependency.

If you find no dependencies, return an empty list: {\"dependencies\": []}.
"""


@router.post(
    "/issue-dependencies/detect",
    response_model=DependencyResponse,
    tags=["Issues", "AI"],
    summary="Detect dependencies between a list of issues using an AI model.",
)
async def detect_issue_dependencies(
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
    for issue_id in request.issue_ids:
        issue = crud_issue.get(db, id=issue_id, account_id=current_user.id)
        if not issue:
            raise HTTPException(
                status_code=404, detail=f"Issue with ID '{issue_id}' not found."
            )
        issues.append(issue)

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

    # 3. Construct the user prompt
    issue_details = []
    for issue in issues:
        detail = (
            f"ID: {issue.id}\n"
            f"Project: {issue.project.name}\n"
            f"Title: {issue.title}\n"
            f"Description: {issue.description or 'No description provided.'}"
        )
        issue_details.append(detail)

    user_prompt = "Please analyze the following issues for dependencies:\n\n---\n".join(
        issue_details
    )

    # 4. Call the AI model
    try:
        client = openai.OpenAI(api_key=ai_model.api_key or openai.api_key)

        response = await client.chat.completions.create(
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

        return DependencyResponse(**parsed_json)

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
