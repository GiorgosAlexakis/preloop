from typing import List, Optional, Union
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from spacebridge.api.auth import get_current_active_user
from spacebridge.api.common import get_accessible_projects
from spacemodels.db.session import get_db_session as get_db
from spacemodels import models as sm_models
from spacemodels.models.account import Account

from spacemodels.crud import (
    CRUDIssue,
    CRUDOrganization,
    CRUDProject,
    CRUDTracker,
    crud_embedding_model,
    crud_issue_embedding,
)

from spacebridge.schemas.issue import IssueResponse
from spacebridge.schemas.comment import CommentResponse
from spacemodels.models.issue import Issue
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.tracker import Tracker

# Initialize CRUD operations
crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)
crud_issue = CRUDIssue(Issue)
crud_tracker = CRUDTracker(Tracker)

logger = logging.getLogger(__name__)

# Pydantic Schemas for Search


class SearchResultItem(BaseModel):
    item_type: str = Field(
        ...,
        examples=["issue", "comment"],
        description="Type of the search result item: 'issue' or 'comment'.",
    )
    item: Union[IssueResponse, CommentResponse] = Field(
        ..., description="The actual issue or comment object."
    )
    similarity: float = Field(
        ..., description="Similarity score of the item to the query."
    )


class SearchResponse(BaseModel):
    results: List[SearchResultItem]


async def perform_search(
    query: str,
    db: Session,
    current_user: Account,
    embedding_type: Optional[str] = None,
    search_type: str = "fulltext",
    limit: int = 10,
    skip: int = 0,
    sort: Optional[str] = None,
    issue_id: Optional[str] = None,
    project_id: Optional[str] = None,
    project: Optional[str] = None,
    organization_id: Optional[str] = None,
    organization: Optional[str] = None,
    author: Optional[str] = None,
    status: Optional[str] = None,
) -> SearchResponse:
    """
    Perform a similarity search based on query text.
    - **query**: The natural language query.
    - **embedding_type**: 'issue', 'comment', or null (for both).
    - **search_type**: 'similarity' or 'fulltext'.
    - Filters: project_id, limit, etc. Note: issue_id, organization_id, author are not used for similarity search.
    """
    # --- Project and Organization Resolution Logic ---
    # ALWAYS get accessible projects to apply scope rules
    accessible_projects = get_accessible_projects(
        db=db,
        current_user=current_user,
        project_ids=[project_id] if project_id else None,
    )

    # Apply additional filtering based on organization/project name filters
    if organization_id or organization:
        # Filter by organization
        if organization_id:
            accessible_projects = [
                p for p in accessible_projects if p.organization_id == organization_id
            ]
        elif organization:
            accessible_projects = [
                p for p in accessible_projects if p.organization.name == organization
            ]

    if project:
        # Filter by project name
        accessible_projects = [p for p in accessible_projects if p.name == project]

    # Extract project IDs - this now always contains scope-filtered projects
    resolved_project_ids_param = [p.id for p in accessible_projects]

    # --- End of Project and Organization Resolution Logic ---

    if search_type == "similarity":
        # TODO:Check usage limit before proceeding
        # if not billing_service.check_limit(current_user.id, "ai_calls"):
        #     raise HTTPException(
        #         status_code=429,
        #         detail="You have exceeded the AI model call limit for your current plan.",
        #     )

        # 1. Get Active Embedding Model (since model_id is not in signature)
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
        try:
            query_vector = crud_issue_embedding._generate_embedding_vector(query, model)
        except Exception as e:
            logger.error(
                f"Error generating query vector for '{query}': {e}", exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail="Error generating query vector for similarity search.",
            )

        # 3. Call similarity_search from CRUD
        # Only pass parameters supported by CRUD and available in the current signature

        db_results_with_scores = crud_issue_embedding.similarity_search(
            db,
            model_id=model.id,
            query_vector=query_vector,
            limit=limit,
            skip=skip,
            project_ids=resolved_project_ids_param,  # Use the new resolved list
            embedding_type=embedding_type,
            sort=sort,  # Pass sort parameter to the CRUD method
            status=status,
            account_id=current_user.id,
        )

        # Record usage after successful search
        # Usage is now recorded in specific services where AI models are directly used.
        # billing_service.record_usage(current_user.id, "ai_calls")

        # print(resolved_project_ids_param) # Optional: for debugging

    elif search_type == "fulltext":
        raise HTTPException(
            status_code=501,  # Not Implemented
            detail="Full-text search is not implemented on this generic endpoint. Please use specific issue or comment search endpoints.",
        )
    else:
        # This case should ideally be caught by FastAPI's enum validation
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search_type: '{search_type}'. Must be 'similarity' or 'fulltext'.",
        )

    # 4. Transform Results to Pydantic Schemas
    response_items: List[SearchResultItem] = []
    for db_obj, score in db_results_with_scores:
        item_schema: Union[IssueResponse, CommentResponse]
        item_type_str: str

        if isinstance(db_obj, sm_models.Issue):
            issue_project = crud_project.get(
                db, id=db_obj.project_id, account_id=current_user.id
            )  # Still need project for response model
            project_name = issue_project.name if issue_project else None
            project_identifier = (
                issue_project.identifier or issue_project.slug
                if issue_project
                else None
            )
            organization_name = None
            if issue_project:
                issue_org = crud_organization.get(
                    db,
                    id=issue_project.organization_id,
                    account_id=current_user.id,
                )
                if issue_org:
                    organization_name = issue_org.name
            external_url = db_obj.external_url
            metadata_dict = db_obj.meta_data or {}

            item_schema = IssueResponse(
                id=str(db_obj.id),
                project_id=str(db_obj.project_id),
                external_id=db_obj.external_id,
                key=db_obj.key,
                title=db_obj.title,
                description=db_obj.description,
                status=db_obj.status,
                priority=db_obj.priority,
                organization=organization_name,
                project=project_name,
                project_identifier=project_identifier,
                url=external_url or f"https://spacebridge.io/issues/{db_obj.id}",
                created_at=db_obj.created_at,
                updated_at=db_obj.updated_at,
                meta_data=metadata_dict,
                labels=metadata_dict.get("labels", [])
                if isinstance(metadata_dict.get("labels"), list)
                else [],
                assignee=metadata_dict.get("assignee"),
                score=score,
            )
            item_type_str = "issue"
        elif isinstance(db_obj, sm_models.Comment):
            item_schema = CommentResponse(
                id=str(db_obj.id),
                body=db_obj.body,
                author=db_obj.author,
                created_at=db_obj.created_at,
                updated_at=db_obj.updated_at,
                issue_id=str(db_obj.issue_id),
                meta_data=db_obj.meta_data or {},
                score=score,
            )
            item_type_str = "comment"
        else:
            continue

        response_items.append(
            SearchResultItem(
                item_type=item_type_str, item=item_schema, similarity=score
            )
        )

    return SearchResponse(results=response_items)


router = APIRouter()


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Perform Similarity Search",
    description="Performs a similarity search across issues and/or comments based on a query text and an embedding model.",
)
async def search_all(
    query: str = Query(..., description="The text query to search for."),
    embedding_type: Optional[str] = Query(
        None,
        examples=["issue", "comment"],
        description="Type of items to search: 'issue', 'comment', or null for both.",
    ),
    search_type: str = Query(
        "fulltext",
        enum=["fulltext", "similarity"],
        description="Type of search to perform ('fulltext' or 'similarity')",
    ),
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of comments to return"
    ),
    skip: int = Query(0, ge=0, description="Number of results to skip for pagination"),
    sort: Optional[str] = Query(
        None,
        enum=["newest"],
        description="Sort order. 'newest' sorts by creation date descending.",
    ),
    issue_id: Optional[str | None] = Query(
        None, description="Filter comments by a specific issue ID (UUID)"
    ),
    project_id: Optional[str | None] = Query(
        None, description="Filter search results by project ID (UUID)."
    ),
    project: Optional[str | None] = Query(
        None, description="Filter search results by project name."
    ),
    organization_id: Optional[str | None] = Query(
        None, description="Filter search results by organization ID (UUID)."
    ),
    organization: Optional[str | None] = Query(
        None, description="Filter search results by organization name."
    ),
    author: Optional[str | None] = Query(
        None, description="Filter comments by author (username)"
    ),
    status: Optional[str | None] = Query(
        None, description="Filter issues by status ('opened', 'closed', 'all')."
    ),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    return await perform_search(
        query=query,
        db=db,
        current_user=current_user,
        embedding_type=embedding_type,
        search_type=search_type,
        limit=limit,
        skip=skip,
        sort=sort,
        issue_id=issue_id,
        project_id=project_id,
        project=project,
        organization_id=organization_id,
        organization=organization,
        author=author,
        status=status,
    )
