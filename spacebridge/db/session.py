"""Database session management for SpaceBridge."""

import logging
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost/spacebridge"
)

# Create SQLAlchemy engine, using SQLite in memory for testing if PostgreSQL is not available
try:
    engine = create_engine(DATABASE_URL)
    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except ImportError:
    logger.warning(
        "PostgreSQL driver not available. Using SQLite in memory for testing purposes."
    )
    engine = create_engine("sqlite:///:memory:")
    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Get a database session.

    Yields:
        Session: A SQLAlchemy session.

    Example:
        ```python
        from spacebridge.db.session import get_db

        def my_function():
            db = next(get_db())
            # Use db session
            db.close()
        ```
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
