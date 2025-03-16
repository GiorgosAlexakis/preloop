"""Health check endpoints."""

from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from spacebridge.db.session import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Health check endpoint."""
    # Verify database connection
    db.execute("SELECT 1")
    
    return {"status": "healthy"}
