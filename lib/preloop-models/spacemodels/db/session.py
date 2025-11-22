"""Database session management."""

import os
from typing import AsyncGenerator, Generator, Optional
from contextlib import asynccontextmanager

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from .vector_types import check_pgvector_extension, install_pgvector_extension

# Global engine instance to be reused across the application
_engine = None
_session_factory = None
_async_engine = None
_async_session_factory = None


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


def get_async_engine(database_url: Optional[str] = None) -> AsyncEngine:
    """Create or retrieve async SQLAlchemy engine for PostgreSQL with pgvector."""
    global _async_engine

    # Return cached engine if it exists
    if _async_engine is not None:
        return _async_engine

    url = database_url or os.getenv("DATABASE_URL")

    if not url:
        raise Exception("DATABASE_URL not in env")

    # Convert psycopg to asyncpg for async operations
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://")

    try:
        # Configure connection pool with proper limits and recycling
        _async_engine = create_async_engine(
            url,
            pool_size=10,  # Maximum number of connections to keep in the pool
            max_overflow=20,  # Maximum number of connections that can be created beyond pool_size
            pool_pre_ping=True,  # Test connections before using them to detect stale connections
            pool_recycle=3600,  # Recycle connections after 1 hour to prevent stale connections
            echo=False,  # Set to True for SQL query debugging
        )

        logger.debug(f"Connected to async database using {url}")
        return _async_engine
    except (ImportError, SQLAlchemyError) as e:
        logger.error(f"Async database connection failed: {e}")
        _async_engine = None  # Reset on failure
        raise Exception(f"Async database connection failed: {e}")


def get_async_session_factory(
    engine: Optional[AsyncEngine] = None,
) -> async_sessionmaker:
    """Get or create async session factory for database."""
    global _async_session_factory, _async_engine

    # Return cached session factory if it exists
    if _async_session_factory is not None and engine is None:
        return _async_session_factory

    # Use provided engine or get the global engine
    engine = engine or get_async_engine()

    # Create and cache the session factory
    _async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return _async_session_factory


@asynccontextmanager
async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session context manager.

    Usage:
        async with get_async_db_session() as db:
            result = await db.execute(query)
    """
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
