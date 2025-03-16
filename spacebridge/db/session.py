"""Database session management for SpaceBridge."""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost/spacebridge"
)

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

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
