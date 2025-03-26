"""SQLAlchemy types for vector storage and UUID handling."""

import json
import uuid
from typing import Any, List, Optional, cast

import numpy as np
from sqlalchemy import String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine.interfaces import Dialect

try:
    from pgvector.sqlalchemy import Vector

    PGVECTOR_AVAILABLE = True
except ImportError:
    Vector = None
    PGVECTOR_AVAILABLE = False


class VectorType(TypeDecorator):
    """
    SQLAlchemy type for vector embeddings with pgvector support.

    This type automatically uses pgvector's Vector type when available,
    and falls back to JSONB for SQLite or other databases.
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, dimensions: int, **kwargs: Any):
        """Initialize the vector type with dimension information."""
        self.dimensions = dimensions
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        """Load the correct implementation based on the dialect."""
        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            # Use pgvector for PostgreSQL
            return dialect.type_descriptor(Vector(self.dimensions))

        # Use JSONB for others (SQLite, MySQL, etc.)
        return dialect.type_descriptor(JSONB())

    def process_bind_param(self, value: Optional[List[float]], dialect: Dialect) -> Any:
        """Convert the vector to the correct format for storage."""
        if value is None:
            return None

        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            # For PostgreSQL with pgvector, return as is (will be handled by pgvector)
            return value

        # For other databases, store as JSON
        return json.dumps(value)

    def process_result_value(
        self, value: Any, dialect: Dialect
    ) -> Optional[List[float]]:
        """Convert the stored value back to a vector."""
        if value is None:
            return None

        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            # For PostgreSQL with pgvector, convert to list if needed
            if isinstance(value, np.ndarray):
                return value.tolist()
            return value

        # For other databases, parse JSON
        if isinstance(value, str):
            return json.loads(value)

        return cast(List[float], value)

    @property
    def python_type(self) -> type:
        """Return the Python type for this SQLAlchemy type."""
        return list


def cosine_distance(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine distance between two vectors."""
    a = np.array(v1)
    b = np.array(v2)
    return 1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def euclidean_distance(v1: List[float], v2: List[float]) -> float:
    """Calculate euclidean distance between two vectors."""
    a = np.array(v1)
    b = np.array(v2)
    return np.linalg.norm(a - b)


def check_pgvector_extension(engine: Any) -> bool:
    """Check if pgvector extension is installed in PostgreSQL."""
    if not PGVECTOR_AVAILABLE:
        return False

    try:
        with engine.connect() as conn:
            result = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            ).scalar()
            return bool(result)
    except Exception:
        return False


def install_pgvector_extension(engine: Any) -> bool:
    """Install pgvector extension in PostgreSQL if not already installed."""
    if not PGVECTOR_AVAILABLE:
        return False

    try:
        with engine.connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()
            return True
    except Exception:
        return False


class SQLiteUUID(TypeDecorator):
    """SQLAlchemy type for UUIDs that works with SQLite.

    PostgreSQL has a native UUID type, but SQLite does not.
    This type uses PostgreSQL's UUID type when using PostgreSQL
    and falls back to String for other databases like SQLite.
    """

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        """Load dialect-specific implementation."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        """Process the value when binding to SQL."""
        if value is None:
            return None

        if dialect.name == "postgresql":
            return value
        else:
            return str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        """Process the value when retrieving from SQL."""
        if value is None:
            return None

        if dialect.name != "postgresql" and isinstance(value, str):
            return uuid.UUID(value)
        return value
