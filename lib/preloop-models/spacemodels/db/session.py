"""Database session management."""

import os
from typing import Generator, Optional

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

# Import pgvector helpers but handle case where it's not installed
try:
    from .vector_types import check_pgvector_extension, install_pgvector_extension

    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False

    # Create stubs for the imported functions
    def check_pgvector_extension(engine):
        return False

    def install_pgvector_extension(engine):
        return False


def get_engine(database_url: Optional[str] = None):
    """Create SQLAlchemy engine for PostgreSQL with pgvector."""
    url = database_url or os.getenv("DATABASE_URL")

    if not url:
        raise Exception("DATABASE_URL not in env")
    is_postgresql = "postgresql" in url

    if not is_postgresql:
        raise Exception(
            "Only PostgreSQL is supported. SQLite fallback has been removed."
        )

    try:
        engine = create_engine(url, isolation_level="AUTOCOMMIT")
        # Test the connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # If PostgreSQL, check for pgvector extension
        if PGVECTOR_AVAILABLE:
            if not check_pgvector_extension(engine):
                try:
                    logger.info("Installing pgvector extension")
                    install_pgvector_extension(engine)
                    logger.info("pgvector extension installed successfully")
                except Exception as e:
                    logger.warning(f"Failed to install pgvector extension: {e}")
                    raise Exception(f"Failed to install pgvector extension: {e}")
            else:
                logger.info("pgvector extension already installed")

        logger.info(f"Connected to database using {url}")
        return engine
    except (ImportError, SQLAlchemyError) as e:
        logger.error(f"Database connection failed: {e}")
        raise Exception(f"Database connection failed: {e}")


def get_session_factory(engine=None):
    """Get session factory for database."""
    engine = engine or get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """Get a database session."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
