"""Database session management."""

import os
from typing import Generator, Optional

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .vector_types import check_pgvector_extension, install_pgvector_extension

# Global engine instance to be reused across the application
_engine = None
_session_factory = None


def get_engine(database_url: Optional[str] = None):
    """Create or retrieve SQLAlchemy engine for PostgreSQL with pgvector."""
    global _engine

    # Return cached engine if it exists
    if _engine is not None:
        return _engine

    url = database_url or os.getenv("DATABASE_URL")

    if not url:
        raise Exception("DATABASE_URL not in env")

    try:
        # Configure connection pool with proper limits and recycling
        _engine = create_engine(
            url,
            pool_size=10,  # Maximum number of connections to keep in the pool
            max_overflow=20,  # Maximum number of connections that can be created beyond pool_size
            pool_pre_ping=True,  # Test connections before using them to detect stale connections
            pool_recycle=3600,  # Recycle connections after 1 hour to prevent stale connections
            echo=False,  # Set to True for SQL query debugging
        )

        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        if not check_pgvector_extension(_engine):
            install_pgvector_extension(_engine)

        logger.debug(f"Connected to database using {url}")
        return _engine
    except (ImportError, SQLAlchemyError) as e:
        logger.error(f"Database connection failed: {e}")
        _engine = None  # Reset on failure
        raise Exception(f"Database connection failed: {e}")


def get_session_factory(engine=None):
    """Get or create session factory for database."""
    global _session_factory, _engine

    # Return cached session factory if it exists
    if _session_factory is not None and engine is None:
        return _session_factory

    # Use provided engine or get the global engine
    engine = engine or get_engine()

    # Create and cache the session factory
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _session_factory


def get_db_session() -> Generator[Session, None, None]:
    """Get a database session."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
