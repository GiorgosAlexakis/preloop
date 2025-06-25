"""Database session management."""

import os
from typing import Generator, Optional

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .vector_types import check_pgvector_extension, install_pgvector_extension


def get_engine(database_url: Optional[str] = None):
    """Create SQLAlchemy engine for PostgreSQL with pgvector."""
    url = database_url or os.getenv("DATABASE_URL")

    if not url:
        raise Exception("DATABASE_URL not in env")

    try:
        engine = create_engine(url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        if not check_pgvector_extension(engine):
            install_pgvector_extension(engine)

        logger.debug(f"Connected to database using {url}")
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
