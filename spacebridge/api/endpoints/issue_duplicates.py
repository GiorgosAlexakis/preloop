from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import Any, Dict, List, Literal, Optional, Tuple
import logging
import openai
import os
import json

from spacebridge.schemas.issue_duplicate import (
    IssueDuplicate as IssueDuplicateSchema,
    IssueDuplicateCreate,
    IssueDuplicateResolve,
    IssueDuplicateSuggestionResponse,
)
from spacemodels.crud import issue as issue_crud
from spacemodels.crud import issue_duplicate as issue_duplicate_crud

from spacebridge.schemas.issue import IssueResponse

from fastapi import Query
from SpaceModels.spacemodels.crud.issue_duplicate import crud_issue_duplicate
from spacemodels.crud import (
    crud_issue_embedding,
    crud_embedding_model,
    crud_issue,
    crud_llm_model,
    crud_project,
    crud_organization,
)
from spacemodels.db.session import get_db_session as get_db

from spacebridge.schemas.duplicates import (
    ProjectDuplicatesResponse,
    DuplicateIssuePair,
)
from spacebridge.schemas.issue_duplicate import (
    IssueDuplicateProjectStats,
    IssueDuplicateStats,
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

    default_model = crud_llm_model.get_default_active_model(db, include_ownerless=True)
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


@router.patch(
    "/issue-duplicates/resolve",
    response_model=IssueDuplicateSchema,
    tags=["Issue Duplicates"],
)
async def resolve_issue_duplicate(
    resolution: IssueDuplicateResolve,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """Resolve an issue duplicate."""
    existing_duplicate = crud_issue_duplicate.get_by_issue_ids(
        db, issue1_id=resolution.issue1_id, issue2_id=resolution.issue2_id
    )
    if not existing_duplicate:
        raise HTTPException(status_code=404, detail="Duplicate entry not found.")

    # Check if the user has access to the project containing the issues
    # Raises an exception if not
    project_id = existing_duplicate.issue1.project_id
    _get_accessible_projects(db, current_user, [project_id])

    if resolution.resolution == "merge":
        if not all(
            [
                resolution.resulting_issue1_id,
                resolution.merged_title,
                resolution.merged_description,
            ]
        ):
            raise HTTPException(
                status_code=400,
                detail="Merge resolution requires resulting_issue1_id, merged_title, and merged_description.",
            )
        issue_to_update = await issue_crud.get(db=db, id=resolution.resulting_issue1_id)
        if not issue_to_update:
            raise HTTPException(status_code=404, detail="Resulting issue not found.")
        update_data = {
            "title": resolution.merged_title,
            "description": resolution.merged_description,
        }
        await issue_crud.update(db=db, db_obj=issue_to_update, obj_in=update_data)

    elif resolution.resolution == "disambiguate":
        if not all(
            [
                resolution.disambiguated_title1,
                resolution.disambiguated_description1,
                resolution.disambiguated_title2,
                resolution.disambiguated_description2,
            ]
        ):
            raise HTTPException(
                status_code=400,
                detail="Disambiguate resolution requires titles and descriptions for both issues.",
            )

        issue1_to_update = await issue_crud.get(db=db, id=resolution.issue1_id)
        issue2_to_update = await issue_crud.get(db=db, id=resolution.issue2_id)
        if not issue1_to_update or not issue2_to_update:
            raise HTTPException(status_code=404, detail="One or both issues not found.")

        update_data1 = {
            "title": resolution.disambiguated_title1,
            "description": resolution.disambiguated_description1,
        }
        await issue_crud.update(db=db, db_obj=issue1_to_update, obj_in=update_data1)

        update_data2 = {
            "title": resolution.disambiguated_title2,
            "description": resolution.disambiguated_description2,
        }
        await issue_crud.update(db=db, db_obj=issue2_to_update, obj_in=update_data2)

    db_duplicate = await issue_duplicate_crud.update_resolution(
        db=db,
        issue1_id=resolution.issue1_id,
        issue2_id=resolution.issue2_id,
        resolution_in=resolution,
    )

    if not db_duplicate:
        raise HTTPException(status_code=404, detail="Issue duplicate not found.")

    return db_duplicate


def _find_issue_duplicates_logic(
    db: Session,
    accessible_projects: List[Project],
    similarity_threshold: float,
    limit: int,
    skip: int,
    limit_per_issue: int,
    status: Optional[str],
) -> Tuple[List[DuplicateIssuePair], str]:
    """Shared logic to find potential duplicate issues within specified projects."""
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

    issues_query = db.query(Issue).filter(
        Issue.project_id.in_([p.id for p in accessible_projects])
    )

    if status and status != "all":
        issues_query = issues_query.filter(Issue.status == status)

    issue_ids = [row[0] for row in issues_query.with_entities(Issue.id).all()]

    if not issue_ids:
        return [], model.id

    all_duplicates_pairs: List[DuplicateIssuePair] = []
    reported_pairs = set()

    for i in range(0, len(issue_ids), 100):
        batch_ids = issue_ids[i : i + 100]
        issues_batch = (
            db.query(Issue)
            .options(selectinload(Issue.embeddings))
            .filter(Issue.id.in_(batch_ids))
            .all()
        )
        for current_issue_obj in issues_batch:
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

            project_id = str(current_issue_obj.project_id)

            similar_issue_score_tuples: List[Tuple[Issue, float]] = (
                crud_issue_embedding.similarity_search(
                    db=db,
                    model_id=model.id,
                    query_vector=query_embedding_vector,
                    limit=limit_per_issue + 1,
                    project_ids=[project_id],
                    embedding_type="issue",
                    similarity=similarity_threshold,
                    status=status if status and status != "all" else None,
                )
            )

            for similar_issue_obj, score in similar_issue_score_tuples:
                if similar_issue_obj.id == current_issue_obj.id:
                    continue

                id1_str = str(current_issue_obj.id)
                id2_str = str(similar_issue_obj.id)
                pair_key = frozenset([id1_str, id2_str])

                if pair_key not in reported_pairs:
                    try:
                        duplicate_pair = DuplicateIssuePair(
                            issue1=IssueResponse(
                                id=str(current_issue_obj.id),
                                external_id=current_issue_obj.external_id,
                                key=current_issue_obj.key,
                                organization="",
                                project="",
                                url=current_issue_obj.external_url or "",
                                created_at=current_issue_obj.created_at,
                                updated_at=current_issue_obj.updated_at,
                                title=current_issue_obj.title,
                                description=current_issue_obj.description or "",
                                status=current_issue_obj.status or "",
                                priority=current_issue_obj.priority or "",
                                author="",
                                assignees=[],
                                labels=[],
                                comments=[],
                                project_id=project_id,
                            ),
                            issue2=IssueResponse(
                                id=str(similar_issue_obj.id),
                                external_id=similar_issue_obj.external_id,
                                key=similar_issue_obj.key,
                                organization="",
                                project="",
                                url=similar_issue_obj.external_url or "",
                                created_at=similar_issue_obj.created_at,
                                updated_at=similar_issue_obj.updated_at,
                                title=similar_issue_obj.title,
                                description=similar_issue_obj.description or "",
                                status=similar_issue_obj.status or "",
                                priority=similar_issue_obj.priority or "",
                                author="",
                                assignees=[],
                                labels=[],
                                comments=[],
                                project_id=project_id,
                            ),
                            similarity=score,
                        )
                        all_duplicates_pairs.append(duplicate_pair)
                        reported_pairs.add(pair_key)
                    except Exception as e:
                        logger.error(
                            f"Error creating issue response for duplicate pair: {e}"
                        )
                        continue

    all_duplicates_pairs.sort(key=lambda x: x.similarity, reverse=True)
    paginated_duplicates = all_duplicates_pairs[skip : skip + limit]
    return paginated_duplicates, model.id


def _get_accessible_projects(
    db: Session,
    current_user: Account,
    project_ids: Optional[List[str]],
) -> List[str]:
    """Get the list of accessible project IDs for the given user and project IDs."""
    project_query = (
        db.query(Project)
        .options(joinedload(Project.organization).joinedload(Organization.tracker))
        .join(Project.organization)
        .join(Organization.tracker)
        .filter(Tracker.account_id == current_user.id)
        .filter(Tracker.is_active)
        .filter(Tracker.is_deleted.is_(False))
    )

    if project_ids:
        project_query = project_query.filter(Project.id.in_(project_ids))

    return project_query.all()


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
    skip: int = Query(
        0, ge=0, description="Number of duplicates to skip for pagination."
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
    status: Literal["opened", "closed", "all"] = Query(
        "opened", description="Filter issues by status."
    ),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Finds potential duplicate issues within specified projects.
    """
    accessible_projects = _get_accessible_projects(
        db=db, current_user=current_user, project_ids=project_ids
    )

    paginated_duplicates, model_id_used = _find_issue_duplicates_logic(
        db=db,
        accessible_projects=accessible_projects,
        similarity_threshold=similarity_threshold,
        limit=limit,
        skip=skip,
        limit_per_issue=limit_per_issue,
        status=status,
    )

    return ProjectDuplicatesResponse(
        project_ids=[str(p.id) for p in accessible_projects],
        model_id_used=model_id_used,
        threshold_used=similarity_threshold,
        duplicates=paginated_duplicates,
    )


@router.get("/project-duplicate-stats", response_model=IssueDuplicateStats)
def get_projects_duplicate_stats(
    project_ids: Optional[List[str]] = Query(
        None,
        description="A list of project IDs to filter the statistics by. If not provided, stats for all accessible projects will be returned.",
    ),
    similarity_threshold: float = Query(
        0.95,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for considering issues as duplicates.",
    ),
    status: Optional[str] = Query(None, description="Filter issues by status."),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Get statistics about duplicate issues for specified projects.
    """
    accessible_projects = _get_accessible_projects(
        db=db, current_user=current_user, project_ids=project_ids
    )

    issue_counts = crud_issue.get_issue_counts_per_project(
        db, project_ids=[str(p.id) for p in accessible_projects]
    )

    duplicate_issue_list, _ = _find_issue_duplicates_logic(
        db=db,
        accessible_projects=accessible_projects,
        similarity_threshold=similarity_threshold,
        limit=1000,  # A large enough number to get all duplicates for stats
        skip=0,
        limit_per_issue=100,  # A large enough number
        status=status,
    )

    stats: Dict[str, IssueDuplicateProjectStats] = {
        project.id: IssueDuplicateProjectStats(
            project_id=project.id, project_name=project.name, total=0, duplicates=0
        )
        for project in accessible_projects
    }

    for pid, data in issue_counts.items():
        if pid in stats:
            stats[pid].total = data.get("total", 0)

    # Since a duplicate pair contains two issues, we need to count unique issues involved
    duplicate_issues_per_project = {p.id: set() for p in accessible_projects}
    for pair in duplicate_issue_list:
        duplicate_issues_per_project[pair.issue1.project_id].add(pair.issue1.id)
        duplicate_issues_per_project[pair.issue2.project_id].add(pair.issue2.id)

    for pid, issues in duplicate_issues_per_project.items():
        stats[pid].duplicates = len(issues)

    return IssueDuplicateStats(projects=stats)


MERGE_PROMPT = """
You are an expert software engineering assistant. Your task is to merge two issue reports into a single, comprehensive issue. Analyze the title and description of both issues provided below.

Issue 1 Title: {title1}
Issue 1 Description: {description1}

Issue 2 Title: {title2}
Issue 2 Description: {description2}

Generate a new, merged issue that includes:
1. `merged_title`: A clear and concise title that combines the key information from both issues.
2. `merged_description`: A detailed description that synthesizes the information from both issues, preserving important context, steps to reproduce, and expected outcomes. Structure it logically.
3. `explanation`: A brief explanation of how you combined the issues and why.

Format your response as a single JSON object with the keys "merged_title", "merged_description", and "explanation".
"""

DISAMBIGUATE_PROMPT = """
You are an expert software engineering assistant. Your task is to disambiguate two similar-looking issue reports. They might be distinct bugs, or one might be a subset of the other. Analyze the title and description of both issues provided below.

Issue 1 Title: {title1}
Issue 1 Description: {description1}

Issue 2 Title: {title2}
Issue 2 Description: {description2}

Generate new, distinct titles and descriptions for both issues to make them clearer and easier to track independently. Provide:
1. `disambiguated_title1`: A new, more specific title for Issue 1.
2. `disambiguated_description1`: A revised description for Issue 1, clarifying its unique scope.
3. `disambiguated_title2`: A new, more specific title for Issue 2.
4. `disambiguated_description2`: A revised description for Issue 2, clarifying its unique scope.
5. `explanation`: A brief explanation of the changes you made and the reasoning for the disambiguation.

Format your response as a single JSON object with the keys "disambiguated_title1", "disambiguated_description1", "disambiguated_title2", "disambiguated_description2", and "explanation".
"""


@router.post("/LLM-suggestion", response_model=IssueDuplicateSuggestionResponse)
def get_resolution_suggestion(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
    issue1_id: str = Body(...),
    issue2_id: str = Body(...),
    resolution: str = Body(...),
):
    """Generate a suggestion for resolving a duplicate issue pair."""
    issue1 = crud_issue.get(db, id=issue1_id)
    issue2 = crud_issue.get(db, id=issue2_id)

    if not issue1 or not issue2:
        raise HTTPException(status_code=404, detail="One or both issues not found")

    project = crud_project.get(db, id=issue1.project_id)

    # Authorization check
    organization = crud_organization.get(db, id=project.organization_id)
    if (
        not organization
        or not organization.tracker
        or organization.tracker.account_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    default_model = crud_llm_model.get_default_active_model(db, include_ownerless=True)
    if not default_model:
        logger.error("No default active LLM model configured.")
        raise HTTPException(
            status_code=500, detail="No default active LLM model configured."
        )

    logger.info(f"Using LLM model '{default_model.model_name}'.")

    client = openai.OpenAI()

    try:
        if resolution == "merged":
            prompt = MERGE_PROMPT.format(
                title1=issue1.title,
                description1=issue1.description,
                title2=issue2.title,
                description2=issue2.description,
            )
            llm_response = client.chat.completions.create(
                model=default_model.model_name,
                messages=[{"content": prompt, "role": "user"}],
                response_format={"type": "json_object"},
            )
            suggestion_data = json.loads(llm_response.choices[0].message.content)
            return IssueDuplicateSuggestionResponse(**suggestion_data)

        elif resolution == "disambiguated":
            prompt = DISAMBIGUATE_PROMPT.format(
                title1=issue1.title,
                description1=issue1.description,
                title2=issue2.title,
                description2=issue2.description,
            )
            llm_response = client.chat.completions.create(
                model=default_model.model_name,
                messages=[{"content": prompt, "role": "user"}],
                response_format={"type": "json_object"},
            )
            suggestion_data = json.loads(llm_response.choices[0].message.content)
            return IssueDuplicateSuggestionResponse(**suggestion_data)

        else:
            raise HTTPException(
                status_code=400,
                detail="Suggestions are only available for 'merged' or 'disambiguated' resolutions.",
            )
    except openai.APIError as e:
        logger.error(f"OpenAI API call failed: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate suggestion from LLM."
        )
    except Exception as e:
        logger.error(f"LLM suggestion failed: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate suggestion from LLM."
        )
