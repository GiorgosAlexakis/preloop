from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from spacebridge.api.auth.jwt import get_current_active_user
from spacemodels.db.session import get_db_session as get_db
from spacebridge.schemas.embedding import (
    EmbeddingRawDataItem,
    EmbeddingRawResponse,
)
from spacemodels.crud.embedding import CRUDIssueEmbedding
from spacebridge.api.auth import get_current_active_user
from spacemodels.models.account import Account

router = APIRouter()


@router.get(
    "/projects/{project_name}/embeddings",
    response_model=EmbeddingRawResponse,
    summary="Get all issue embeddings for a project",
    tags=["projects", "embeddings"],
)
def get_raw_embeddings(
    project_name: str,
    embedding_model_id: Optional[str] = Query(
        None, description="The ID of the embedding model to use."
    ),
    organization_name: Optional[str] = Query(
        None, description="Filter embeddings by organization name."
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination."),
    limit: int = Query(
        1000, ge=1, le=2000, description="Maximum number of records to return."
    ),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """
    API endpoint to fetch raw embedding vectors for issues, with optional filtering.

    This endpoint is designed to provide data for frontend visualizations like deck.gl.
    """
    crud_embedding = CRUDIssueEmbedding(db)
    raw_data = crud_embedding.get_raw_embeddings(
        db=db,
        embedding_model_id=embedding_model_id,
        project_name=project_name,
        organization_name=organization_name,
        account_id=current_user.id,
        skip=skip,
        limit=limit,
    )

    # Format the data into the response model
    response_data = [
        EmbeddingRawDataItem(issue_id=issue_id, embedding=embedding)
        for issue_id, embedding in raw_data
    ]

    return EmbeddingRawResponse(data=response_data)
