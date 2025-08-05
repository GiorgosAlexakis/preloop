from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from spacebridge.api.auth import get_current_active_user
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
        "full_text",
        enum=["full_text", "similarity"],
        description="Type of search to perform ('full_text' or 'similarity')",
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
    issue_id: Optional[str] = Query(
        None, description="Filter comments by a specific issue ID (UUID)"
    ),
    project_id: Optional[str] = Query(
        None, description="Filter search results by project ID (UUID)."
    ),
    project: Optional[str] = Query(
        None, description="Filter search results by project name."
    ),
    organization_id: Optional[str] = Query(
        None, description="Filter search results by organization ID (UUID)."
    ),
    organization: Optional[str] = Query(
        None, description="Filter search results by organization name."
    ),
    author: Optional[str] = Query(
        None, description="Filter comments by author (username)"
    ),
    status: Optional[str] = Query(
        None, description="Filter issues by status ('opened', 'closed', 'all')."
    ),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Perform a similarity search based on query text.
    - **query**: The natural language query.
    - **embedding_type**: 'issue', 'comment', or null (for both).
    - **search_type**: 'similarity' or 'full_text'.
    - Filters: project_id, limit, etc. Note: issue_id, organization_id, author are not used for similarity search.
    """
    # --- Project and Organization Resolution Logic ---
    resolved_project_ids_param: Optional[List[str]] = None

    user_trackers = crud_tracker.get_for_account(db, account_id=current_user.id)
    tracker_ids = [t.id for t in user_trackers]

    if project_id or project or organization_id or organization:
        if not tracker_ids:
            # User has no trackers, so any project/org filter yields no results
            resolved_project_ids_param = []
        else:
            actual_organization_id: Optional[str] = None
            org_filter_is_valid = True

            if organization_id:
                org_obj = crud_organization.get(
                    db, id=organization_id, account_id=current_user.id
                )
                if org_obj and org_obj.tracker_id in tracker_ids:
                    actual_organization_id = org_obj.id
                else:
                    org_filter_is_valid = False
            elif organization:
                # Query organizations accessible by the user and filter by name
                user_accessible_orgs = (
                    db.query(sm_models.Organization)
                    .filter(sm_models.Organization.tracker_id.in_(tracker_ids))
                    .all()
                )
                named_org = next(
                    (o for o in user_accessible_orgs if o.name == organization), None
                )
                if named_org:
                    actual_organization_id = named_org.id
                else:
                    org_filter_is_valid = False

            if not org_filter_is_valid:
                resolved_project_ids_param = []  # Org filter failed
            else:
                # Organization filter is valid or was not specified; proceed to resolve project
                if project_id:
                    proj_obj = crud_project.get(
                        db, id=project_id, account_id=current_user.id
                    )
                    if proj_obj and proj_obj.is_active:  # Check active status first
                        # A project is accessible if its organization's tracker is in tracker_ids
                        project_org = crud_organization.get(
                            db,
                            id=proj_obj.organization_id,
                            account_id=current_user.id,
                        )
                        if project_org and project_org.tracker_id in tracker_ids:
                            # Now check if it matches actual_organization_id if that filter is active
                            if (
                                not actual_organization_id
                                or proj_obj.organization_id == actual_organization_id
                            ):
                                resolved_project_ids_param = [proj_obj.id]
                            else:
                                resolved_project_ids_param = []  # Does not match org filter
                        else:
                            resolved_project_ids_param = []  # Tracker not accessible or org not found for project
                    else:
                        resolved_project_ids_param = []  # Project not found or inactive
                elif project:  # Filter by project name
                    query_proj = (
                        db.query(sm_models.Project)
                        .join(sm_models.Organization)
                        .filter(
                            sm_models.Project.name == project,
                            sm_models.Organization.tracker_id.in_(tracker_ids),
                            sm_models.Project.is_active,
                        )
                    )
                    if actual_organization_id:
                        query_proj = query_proj.filter(
                            sm_models.Project.organization_id == actual_organization_id
                        )
                    matched_projects = query_proj.all()
                    resolved_project_ids_param = [p.id for p in matched_projects]
                elif (
                    actual_organization_id
                ):  # Only org filter, no specific project filter
                    query_proj_org = (
                        db.query(sm_models.Project)
                        .join(sm_models.Organization)
                        .filter(
                            sm_models.Project.organization_id == actual_organization_id,
                            sm_models.Organization.tracker_id.in_(tracker_ids),
                            sm_models.Project.is_active,
                        )
                    )
                    matched_projects_in_org = query_proj_org.all()
                    resolved_project_ids_param = [p.id for p in matched_projects_in_org]
                # If no project/org filters were specified at all, resolved_project_ids_param remains None

    # --- End of Project and Organization Resolution Logic ---

    if search_type == "similarity":
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
        )

        # print(resolved_project_ids_param) # Optional: for debugging

    elif search_type == "full_text":
        raise HTTPException(
            status_code=501,  # Not Implemented
            detail="Full-text search is not implemented on this generic endpoint. Please use specific issue or comment search endpoints.",
        )
    else:
        # This case should ideally be caught by FastAPI's enum validation
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search_type: '{search_type}'. Must be 'similarity' or 'full_text'.",
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
