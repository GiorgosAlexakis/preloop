"""Database session management."""

import os
from typing import Generator, Optional

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


def get_engine(database_url: Optional[str] = None):
    """Create SQLAlchemy engine with fallback for testing."""
    url = database_url or os.getenv(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost/spacemodels"
    )

    try:
        engine = create_engine(url)
        # Test the connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"Connected to database using {url}")
        return engine
    except (ImportError, SQLAlchemyError) as e:
        logger.warning(
            f"Database connection failed: {e}. Using SQLite in memory for testing purposes."
        )
        return create_engine("sqlite:///:memory:")


def get_session_factory(engine=None):
    """Get session factory for database."""
    engine = engine or get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """Get a database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
