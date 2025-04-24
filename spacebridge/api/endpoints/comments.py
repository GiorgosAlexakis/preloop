"""Endpoints for managing issue comments."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from spacebridge.api.auth import get_current_active_user  # Import user dependency
from spacebridge.api.endpoints.issues import get_tracker_client
from spacebridge.schemas.comment import CommentCreate, CommentList, CommentResponse
from spacebridge.trackers.base import IssueComment as TrackerComment
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.account import Account  # Import Account model for type hint

logger = logging.getLogger(__name__)
router = APIRouter()


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
    current_user: Account = Depends(get_current_active_user),  # Add user dependency
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
    current_user: Account = Depends(get_current_active_user),  # Add user dependency
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
