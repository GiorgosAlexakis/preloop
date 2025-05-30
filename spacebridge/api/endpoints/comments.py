"""Endpoints for managing issue comments."""

import logging

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from spacebridge.api.auth import get_current_active_user
from spacebridge.api.endpoints.issues import get_tracker_client
from spacebridge.schemas.comment import CommentCreate, CommentList, CommentResponse
from spacebridge.trackers.base import IssueComment as TrackerComment
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.account import Account
from spacebridge.schemas.comment import CommentSearchResults

from spacemodels.crud import (
    CRUDIssue,
    CRUDOrganization,
    CRUDProject,
    CRUDTracker,
    crud_embedding_model,
    crud_issue_embedding,
)
from spacemodels.models.issue import Issue
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.tracker import Tracker

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize CRUD operations
crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)
crud_issue = CRUDIssue(Issue)
crud_tracker = CRUDTracker(Tracker)

# API Endpoints


@router.get("/issues/{issue_id}/comments", response_model=CommentList)
async def list_issue_comments(
    issue_id: str,
    organization: str = Query(..., description="Organization identifier"),
    project: str = Query(..., description="Project identifier"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of comments to return"
    ),
    offset: int = Query(0, ge=0, description="Number of comments to skip"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> CommentList:
    """Get a list of comments for a specific issue. Requires authentication."""
    try:
        # Get the tracker client, passing current user for auth check
        tracker_client = await get_tracker_client(
            organization, project, db, current_user
        )

        # Get the issue to verify it exists
        issue = await tracker_client.get_issue(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        # Get the comments
        comments = await tracker_client.get_comments(issue_id)

        # Apply pagination
        paginated_comments = comments[offset : offset + limit]

        # Convert tracker comments to API response model
        comment_responses = []
        for comment in paginated_comments:
            comment_responses.append(
                CommentResponse(
                    id=comment.id,
                    issue_id=issue_id,
                    author=comment.author,
                    body=comment.body,
                    created_at=comment.created_at,
                    updated_at=comment.updated_at,
                    metadata=comment.metadata,
                )
            )

        # Return the comment list
        return CommentList(
            items=comment_responses,
            total=len(comments),
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting comments: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting comments: {str(e)}")


@router.post(
    "/issues/{issue_id}/comments", response_model=CommentResponse, status_code=201
)
async def add_issue_comment(
    issue_id: str,
    comment: CommentCreate,
    organization: str = Query(..., description="Organization identifier"),
    project: str = Query(..., description="Project identifier"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> CommentResponse:
    """Add a new comment to a specific issue. Requires authentication."""
    try:
        # Get the tracker client, passing current user for auth check
        tracker_client = await get_tracker_client(
            organization, project, db, current_user
        )

        # Get the issue to verify it exists
        issue = await tracker_client.get_issue(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        # Create the comment
        tracker_comment = TrackerComment(
            body=comment.body,
            metadata=comment.metadata or {},
        )
        created_comment = await tracker_client.add_comment(issue_id, tracker_comment)

        # Convert tracker comment to API response model
        return CommentResponse(
            id=created_comment.id,
            issue_id=issue_id,
            author=created_comment.author,
            body=created_comment.body,
            created_at=created_comment.created_at,
            updated_at=created_comment.updated_at,
            metadata=created_comment.metadata,
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding comment: {str(e)}")


@router.get("/comments/search", response_model=CommentSearchResults)
async def search_comments(
    query: Optional[str] = Query(
        None, description="Search query text for comment body or vector search"
    ),
    search_type: str = Query(
        "full_text",
        enum=["full_text", "similarity"],
        description="Type of search to perform ('full_text' or 'similarity')",
    ),
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of comments to return"
    ),
    issue_id: Optional[str] = Query(
        None, description="Filter comments by a specific issue ID (UUID)"
    ),
    project_id: Optional[str] = Query(
        None, description="Filter comments by parent issue's project ID (UUID)"
    ),
    organization_id: Optional[str] = Query(
        None, description="Filter comments by parent issue's organization ID (UUID)"
    ),
    author_id: Optional[str] = Query(
        None, description="Filter comments by author ID (UUID)"
    ),
    embedding_model_name: Optional[str] = Query(
        None,
        description="Name of the embedding model for similarity search (e.g., 'text-embedding-ada-002')",
    ),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Search for comments using full-text or similarity search.
    Requires authentication and checks user access to related issues/projects.
    """
    user_trackers = crud_tracker.get_for_account(db, account_id=current_user.id)
    accessible_tracker_ids = [t.id for t in user_trackers]

    if not accessible_tracker_ids:
        logger.warning(f"User {current_user.id} has no accessible trackers.")
        return CommentSearchResults(items=[], total=0, query=query or "")

    comments_data: List[CommentResponse] = []
    total_comments = 0

    # Prepare project_ids and organization_ids for CRUD functions
    # similarity_search_comments expects List[str] or None
    resolved_project_ids: Optional[List[str]] = [project_id] if project_id else None
    resolved_organization_ids: Optional[List[str]] = (
        [organization_id] if organization_id else None
    )

    try:
        if search_type == "similarity" and query:
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
            model_id = model.id
            # Generate query vector
            query_vector = crud_issue_embedding._generate_embedding_vector(query, model)
            try:
                query_vector = crud_issue_embedding._generate_embedding_vector(
                    query, model
                )
            except Exception as e:
                logger.error(
                    f"Error generating query vector for '{query}': {e}", exc_info=True
                )
                raise HTTPException(
                    status_code=500,
                    detail="Error generating query vector for similarity search.",
                )

            similar_comments = crud_issue_embedding.similarity_search(
                db,
                model_id=model.id,
                query_vector=query_vector,
                limit=limit,
                project_ids=resolved_project_ids,
                embedding_type="comment",
            )
            total_comments = len(similar_comments)

            for comment_obj, score in similar_comments:
                parent_issue = db.get(Issue, comment_obj.issue_id)
                if (
                    not parent_issue
                    or parent_issue.tracker_id not in accessible_tracker_ids
                ):
                    if not parent_issue:
                        logger.warning(
                            f"Comment {comment_obj.id} links to non-existent issue {comment_obj.issue_id}."
                        )
                    else:
                        logger.warning(
                            f"User {current_user.id} lacks access to tracker for comment {comment_obj.id}."
                        )
                    continue

                parent_project = db.get(Project, parent_issue.project_id)
                if not parent_project:
                    logger.warning(
                        f"Issue {parent_issue.id} links to non-existent project {parent_issue.project_id}."
                    )
                    continue

                created_at_str = (
                    comment_obj.created_at.isoformat()
                    if comment_obj.created_at
                    else None
                )
                updated_at_str = (
                    comment_obj.updated_at.isoformat()
                    if comment_obj.updated_at
                    else None
                )

                comments_data.append(
                    CommentResponse(
                        id=comment_obj.id,
                        body=comment_obj.body,
                        author=comment_obj.author_id or "",
                        created_at=created_at_str,
                        updated_at=updated_at_str,
                        issue_id=comment_obj.issue_id,
                        project_id=parent_issue.project_id,
                        organization_id=parent_project.organization_id,
                        score=score,
                    )
                )

        elif search_type == "full_text":
            # For full-text, crud_comment.search_full_text expects single ID strings or None
            raw_results, count = crud_comment.search_full_text(
                db,
                query_str=query or "",
                limit=limit,
                skip=0,
                issue_id=issue_id,
                project_id=project_id,  # Pass single string or None
                organization_id=organization_id,  # Pass single string or None
                author_id=author_id,
                # TODO: Consider if accessible_tracker_ids needs to be passed to search_full_text for pre-filtering
            )
            total_comments = count

            for comment_obj in raw_results:
                parent_issue = db.get(Issue, comment_obj.issue_id)
                if (
                    not parent_issue
                    or parent_issue.tracker_id not in accessible_tracker_ids
                ):
                    if not parent_issue:
                        logger.warning(
                            f"Comment {comment_obj.id} links to non-existent issue {comment_obj.issue_id}."
                        )
                    else:
                        logger.warning(
                            f"User {current_user.id} lacks access to tracker for comment {comment_obj.id}."
                        )
                    continue

                parent_project = db.get(Project, parent_issue.project_id)
                if not parent_project:
                    logger.warning(
                        f"Issue {parent_issue.id} links to non-existent project {parent_issue.project_id}."
                    )
                    continue

                comments_data.append(
                    CommentResponse(
                        id=comment_obj.id,
                        body=comment_obj.body,
                        author=comment_obj.author_id,
                        created_at=comment_obj.created_at,
                        updated_at=comment_obj.updated_at,
                        issue_id=comment_obj.issue_id,
                        project_id=parent_issue.project_id,
                        organization_id=parent_project.organization_id,
                        score=None,
                    )
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid search_type specified. Must be 'full_text' or 'similarity'.",
            )

        return CommentSearchResults(
            items=comments_data, total=total_comments, query=query or ""
        )

    except HTTPException:  # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        logger.error(
            f"Error searching comments (type: {search_type}, query: '{query}'): {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during comment search: {str(e)}",
        )
