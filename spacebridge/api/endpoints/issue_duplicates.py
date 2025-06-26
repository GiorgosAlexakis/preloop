from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, List, Dict
import logging
import openai
import os

from spacebridge.schemas.issue_duplicate import (
    IssueDuplicate as IssueDuplicateSchema,
    IssueDuplicateCreate,
)

from fastapi import APIRouter, Depends, HTTPException, Query
from SpaceModels.spacemodels.crud.issue_duplicate import crud_issue_duplicate
from spacemodels.crud import crud_issue, crud_llm_model
from spacemodels.db.session import get_db_session as get_db

from spacebridge.schemas.duplicates import (
    ProjectDuplicatesResponse,
    DuplicateIssuePair,
)

from spacebridge.trackers.factory import TrackerFactory
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.account import Account  # Import Account model
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.issue import Issue

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
    "/issue-duplicates/",
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


@router.get(
    "/issue-duplicates", response_model=ProjectDuplicatesResponse
)
def find_issue_duplicates(
    project_ids: List[str],
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
    """Finds potential duplicate issues using semantic similarity."""
    projects = (
        db.query(Project)
        .options(joinedload(Project.organization).joinedload(Organization.tracker))
        .filter(Project.id.in_(project_ids))
        .all()
    )
    if not projects:
        raise HTTPException(status_code=404, detail="Project not found")

    # Authorization check: Ensure user has access to the project's tracker
    for project in projects:
        if (
            not project.organization
            or not project.organization.tracker
            or project.organization.tracker.account_id != current_user.id
        ):
            raise HTTPException(status_code=403, detail="Access denied to this project")

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

    # Fetch all issues for the project and eagerly load their embeddings to avoid N+1 queries.
    issues = (
        db.query(Issue)
        .options(selectinload(Issue.embeddings))
        .filter(Issue.project_id.in_(project_ids))
        .all()
    )

    if not issues:
        return ProjectDuplicatesResponse(
            project_ids=project_ids,
            model_id_used=model.id,
            threshold_used=similarity_threshold,
            duplicates=[],
        )

    all_duplicates_pairs: List[DuplicateIssuePair] = []
    # Use a set of frozensets of issue IDs to track pairs and avoid (A,B) and (B,A) and (A,A)
    reported_pairs = set()

    for current_issue_obj in issues:
        # Find the embedding vector for the current issue corresponding to the active model.
        query_embedding_vector = None
        for emb in current_issue_obj.embeddings:
            if emb.embedding_model_id == model.id:
                query_embedding_vector = emb.embedding
                break

        # If no embedding exists for this issue with the current model, we can't find duplicates.
        if query_embedding_vector is None:
            continue

        # Perform similarity search using the issue's own embedding vector.
        similar_issue_score_tuples: List[Tuple[Issue, float]] = (
            crud_issue_embedding.similarity_search(
                db=db,
                model_id=model.id,
                query_vector=query_embedding_vector,  # Correctly use the vector for the search
                limit=limit_per_issue
                + 1,  # Fetch one extra in case the source issue itself is returned
                project_ids=[project_id],  # Explicitly scope to the current project
                embedding_type="issue",  # Specify we are comparing issue embeddings
            )
        )

        for similar_issue_obj, score in similar_issue_score_tuples:
            # Manually filter by similarity_threshold
            if score < similarity_threshold:
                continue

            # Ensure we are not pairing an issue with itself
            if similar_issue_obj.id == current_issue_obj.id:
                continue

            # Create a canonical representation of the pair to avoid (A,B) and (B,A) duplicates
            # Ensure IDs are consistently typed (e.g., str) for the frozenset key
            id1_str = str(current_issue_obj.id)
            id2_str = str(similar_issue_obj.id)
            pair_key = frozenset([id1_str, id2_str])

            if pair_key not in reported_pairs:
                try:
                    # Manually construct data for IssueResponse to match its existing schema
                    # (as per IssueResponse definition in Step 140)
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
                        "description": current_issue_obj.description,
                        "status": current_issue_obj.status,
                        "priority": current_issue_obj.priority,
                        # Add other fields from IssueBase if necessary
                        # Ensure all non-optional fields in IssueResponse are covered
                    }
                    issue1_response = IssueResponse(**issue1_data)

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
                        "description": similar_issue_obj.description,
                        "status": similar_issue_obj.status,
                        "priority": similar_issue_obj.priority,
                    }
                    issue2_response = IssueResponse(**issue2_data)

                    all_duplicates_pairs.append(
                        DuplicateIssuePair(
                            issue1=issue1_response,
                            issue2=issue2_response,
                            similarity=score,
                        )
                    )
                    reported_pairs.add(pair_key)
                except Exception as e:
                    logger.error(
                        f"Error processing duplicate pair ({current_issue_obj.id}, {similar_issue_obj.id}): {e}",
                        exc_info=True,
                    )

    return ProjectDuplicatesResponse(
        project_ids=project_ids,
        model_id_used=str(model.id),
        threshold_used=similarity_threshold,
        duplicates=all_duplicates_pairs,
    )
