from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import Any, List, Dict, Optional, Tuple
import logging
import openai
import os

from spacebridge.schemas.issue_duplicate import (
    IssueDuplicate as IssueDuplicateSchema,
    IssueDuplicateCreate,
)

from fastapi import Query
from SpaceModels.spacemodels.crud.issue_duplicate import crud_issue_duplicate
from spacemodels.crud import crud_issue, crud_llm_model
from spacemodels.db.session import get_db_session as get_db

from spacebridge.schemas.duplicates import (
    ProjectDuplicatesResponse,
    DuplicateIssuePair,
)

from spacemodels.models.account import Account  # Import Account model
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.issue import Issue
from spacemodels.models.tracker import Tracker

from spacebridge.api.auth import get_current_active_user  # Import user dependency

logger = logging.getLogger(__name__)

router = APIRouter()

LLM_DUPLICATE_SYSTEM_PROMPT = "You are an expert issue tracker assistant. Your task is to determine if two issues are duplicates of each other."
LLM_DUPLICATE_USER_PROMPT_TEMPLATE = """
Use your expert judgement to determine if the following two issues are duplicates.

- Two issues are considered duplicates if they describe the same core problem, request, or task, even if the wording differs slightly or one contains minor additional details.
- Two issues are not considered duplicates even if they look almost identical, if they refer to different components.

Issue 1:
Title: {issue1_title}
Description:
---
{issue1_description}
---

Issue 2:
Title: {issue2_title}
Description:
---
{issue2_description}
---

Based on the information above, is Issue 2 a duplicate of Issue 1?

Are these two issues duplicates? Your answer must be only two lines.
On the first line, write a single word: either 'YES' or 'NO'.
On the second line, provide a single-sentence reasoning for your decision.
"""


@router.get(
    "/issue-duplicates/confirmed",
    response_model=List[IssueDuplicateSchema],
    tags=["Issue Duplicates"],
)
def get_duplicate_issues(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve confirmed duplicate issues.
    """
    duplicates = crud_issue_duplicate.get_multi(
        db, skip=skip, limit=limit, decision="confirmed"
    )
    return duplicates


@router.get(
    "/issue-duplicates/check",
    response_model=IssueDuplicateSchema,
    tags=["Issue Duplicates"],
)
def check_or_create_issue_duplicate(
    *,
    db: Session = Depends(get_db),
    issue1_id: str,
    issue2_id: str,
) -> Any:
    if issue1_id == issue2_id:
        raise HTTPException(status_code=400, detail="Issue IDs cannot be the same.")

    existing_duplicate = crud_issue_duplicate.get_by_issue_ids(
        db, issue1_id=issue1_id, issue2_id=issue2_id
    )
    if existing_duplicate:
        logger.info(
            f"Found existing duplicate entry for issues {issue1_id} and {issue2_id}."
        )
        return existing_duplicate

    logger.info(
        f"No existing duplicate entry for issues {issue1_id} and {issue2_id}. Proceeding with LLM analysis."
    )

    issue1 = crud_issue.get(db, id=issue1_id)
    issue2 = crud_issue.get(db, id=issue2_id)

    if not issue1 or not issue2:
        missing_ids_str = []
        if not issue1:
            missing_ids_str.append(str(issue1_id))
        if not issue2:
            missing_ids_str.append(str(issue2_id))
        detail = f"Issue(s) not found: {', '.join(missing_ids_str)}."
        logger.warning(detail)
        raise HTTPException(status_code=404, detail=detail)

    default_model = crud_llm_model.get_default_active_model(db)
    if not default_model:
        logger.error("No default active LLM model configured.")
        raise HTTPException(
            status_code=500, detail="No default active LLM model configured."
        )

    logger.info(f"Using LLM model '{default_model.model_name}'.")

    prompt_text = LLM_DUPLICATE_USER_PROMPT_TEMPLATE.format(
        issue1_id=issue1.id,
        issue1_title=issue1.title or "N/A",
        issue1_description=issue1.description or "No description provided.",
        issue2_id=issue2.id,
        issue2_title=issue2.title or "N/A",
        issue2_description=issue2.description or "No description provided.",
    )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": LLM_DUPLICATE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt_text},
    ]

    llm_response_text = ""
    try:
        api_key = default_model.api_key
        if not api_key:
            logger.warning(
                f"API key not found in credentials for model {default_model.model_name}. Trying OPENAI_API_KEY env var."
            )
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            logger.error(
                f"OpenAI API key not found for model {default_model.model_name} or environment variable."
            )
            raise HTTPException(
                status_code=500, detail="OpenAI API key not configured."
            )

        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=default_model.model_name,
            messages=messages,
        )
        llm_response_text = response.choices[0].message.content.strip()
        logger.info(
            f"LLM response for issues {issue1_id}, {issue2_id}: '{llm_response_text}'"
        )

        response_lines = llm_response_text.split("\n")

        if len(response_lines) < 2:
            raise HTTPException(
                status_code=500, detail="LLM response is not in the expected format."
            )

        decision_word = response_lines[0].strip().upper()
        reason = response_lines[1].strip()

        if decision_word == "YES":
            parsed_status = "confirmed"
        elif decision_word == "NO":
            parsed_status = "rejected"
        else:
            logger.warning(
                f"LLM returned unexpected status: '{decision_word}'. Defaulting to 'undecided'."
            )
            parsed_status = "undecided"
            reason = llm_response_text

        duplicate_create_data = IssueDuplicateCreate(
            issue1_id=issue1.id,
            issue2_id=issue2.id,
            decision=parsed_status,
            llm_model_id=default_model.id,
            llm_model_name=default_model.model_name,
            reason=reason,
        )

        new_duplicate_entry = crud_issue_duplicate.create(
            db, obj_in=duplicate_create_data.model_dump()
        )
        logger.info(
            f"Created new IssueDuplicate entry ID {new_duplicate_entry.id} for issues {issue1_id}, {issue2_id} with status '{parsed_status}'."
        )
        return new_duplicate_entry

    except openai.APIError as e:
        logger.exception(
            f"OpenAI API call for model '{default_model.model_name}' failed: {e}"
        )
        raise HTTPException(status_code=500, detail="LLM API error")
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during LLM invocation for model '{default_model.model_name}': {e}"
        )
        raise HTTPException(status_code=500, detail=f"LLM processing error: {str(e)}")


@router.get("/issue-duplicates", response_model=ProjectDuplicatesResponse)
def find_issue_duplicates(
    project_ids: Optional[List[str]] = Query(
        None,
        description=(
            "Optional list of project IDs to search within. "
            "If not provided, searches across all accessible projects."
        ),
    ),
    limit: int = Query(
        5,
        ge=1,
        description="Maximum number of duplicates to return.",
    ),
    similarity_threshold: float = Query(
        0.7,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for considering issues as duplicates.",
    ),
    limit_per_issue: int = Query(
        5,
        ge=1,
        le=20,
        description="Maximum number of duplicates to find for each issue.",
    ),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Finds potential duplicate issues using semantic similarity.
    If project_ids is provided, the search is limited to those projects.
    Otherwise, it searches across all projects accessible by the user.
    """
    project_query = (
        db.query(Project)
        .options(joinedload(Project.organization).joinedload(Organization.tracker))
        .join(Project.organization)
        .join(Organization.tracker)
        .filter(Tracker.account_id == current_user.id)
    )

    if project_ids:
        project_query = project_query.filter(Project.id.in_(project_ids))

    projects = project_query.all()

    if not projects:
        detail = (
            "The specified project(s) were not found or you do not have access."
            if project_ids
            else "No projects found for the current user."
        )
        raise HTTPException(status_code=404, detail=detail)

    accessible_project_ids = [str(p.id) for p in projects]

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

    issues = (
        db.query(Issue)
        .options(selectinload(Issue.embeddings))
        .filter(Issue.project_id.in_(accessible_project_ids))
        .all()
    )

    if not issues:
        return ProjectDuplicatesResponse(
            project_ids=accessible_project_ids,
            model_id_used=model.id,
            threshold_used=similarity_threshold,
            duplicates=[],
        )

    all_duplicates_pairs: List[DuplicateIssuePair] = []
    reported_pairs = set()

    for current_issue_obj in issues:
        if len(all_duplicates_pairs) >= limit:
            break

        query_embedding_vector = next(
            (
                emb.embedding
                for emb in current_issue_obj.embeddings
                if emb.embedding_model_id == model.id
            ),
            None,
        )

        if query_embedding_vector is None:
            continue

        similar_issue_score_tuples: List[Tuple[Issue, float]] = (
            crud_issue_embedding.similarity_search(
                db=db,
                model_id=model.id,
                query_vector=query_embedding_vector,
                limit=limit_per_issue + 1,
                project_ids=accessible_project_ids,
                embedding_type="issue",
            )
        )

        for similar_issue_obj, score in similar_issue_score_tuples:
            if len(all_duplicates_pairs) >= limit:
                break

            if score < similarity_threshold:
                continue

            if similar_issue_obj.id == current_issue_obj.id:
                continue

            id1_str = str(current_issue_obj.id)
            id2_str = str(similar_issue_obj.id)
            pair_key = frozenset([id1_str, id2_str])

            if pair_key not in reported_pairs:
                try:
                    issue1_data = {
                        "id": str(current_issue_obj.id),
                        "external_id": current_issue_obj.external_id,
                        "key": current_issue_obj.key,
                        "organization": "",
                        "project": "",
                        "url": current_issue_obj.external_url or "",
                        "created_at": current_issue_obj.created_at,
                        "updated_at": current_issue_obj.updated_at,
                        "title": current_issue_obj.title,
                        "description": current_issue_obj.description or "",
                        "status": current_issue_obj.status or "",
                        "priority": current_issue_obj.priority or "",
                        "author": "",
                        "assignees": [],
                        "labels": [],
                        "comments": [],
                        "project_id": str(current_issue_obj.project_id),
                        "organization_id": str(
                            current_issue_obj.project.organization_id
                        ),
                    }
                    issue2_data = {
                        "id": str(similar_issue_obj.id),
                        "external_id": similar_issue_obj.external_id,
                        "key": similar_issue_obj.key,
                        "organization": "",
                        "project": "",
                        "url": similar_issue_obj.external_url or "",
                        "created_at": similar_issue_obj.created_at,
                        "updated_at": similar_issue_obj.updated_at,
                        "title": similar_issue_obj.title,
                        "description": similar_issue_obj.description or "",
                        "status": similar_issue_obj.status or "",
                        "priority": similar_issue_obj.priority or "",
                        "author": "",
                        "assignees": [],
                        "labels": [],
                        "comments": [],
                        "project_id": str(similar_issue_obj.project_id),
                        "organization_id": str(
                            similar_issue_obj.project.organization_id
                        ),
                    }
                    all_duplicates_pairs.append(
                        DuplicateIssuePair(
                            issue1=IssueResponse(**issue1_data),
                            issue2=IssueResponse(**issue2_data),
                            similarity=score,
                        )
                    )
                    reported_pairs.add(pair_key)
                except Exception as e:
                    logger.error(
                        f"Error creating issue response for duplicate pair: {e}"
                    )
                    continue

    return ProjectDuplicatesResponse(
        project_ids=accessible_project_ids,
        model_id_used=model.id,
        threshold_used=similarity_threshold,
        duplicates=all_duplicates_pairs,
    )
