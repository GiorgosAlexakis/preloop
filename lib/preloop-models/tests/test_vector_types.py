"""Tests for the vector types module."""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect

from spacemodels.db.vector_types import (
    PGVECTOR_AVAILABLE,
    VectorType,
    check_pgvector_extension,
    cosine_distance,
    euclidean_distance,
    install_pgvector_extension,
)


def test_cosine_distance():
    """Test cosine distance calculation."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    v3 = [1.0, 1.0, 0.0]

    # Orthogonal vectors have distance of 1
    assert cosine_distance(v1, v2) == 1.0

    # Same vector has distance of 0
    assert cosine_distance(v1, v1) == 0.0

    # 45-degree angle has distance of 1-cos(45°) = 1-0.7071 ≈ 0.2929
    distance = cosine_distance(v1, v3)
    assert 0.29 < distance < 0.30


def test_euclidean_distance():
    """Test euclidean distance calculation."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    v3 = [1.0, 1.0, 0.0]

    # Distance between orthogonal unit vectors should be sqrt(2)
    assert abs(euclidean_distance(v1, v2) - np.sqrt(2)) < 1e-10

    # Distance between same vector should be 0
    assert euclidean_distance(v1, v1) == 0.0

    # Distance between v1 and v3 should be 1.0
    assert abs(euclidean_distance(v1, v3) - 1.0) < 1e-10


def test_vector_type_initialization():
    """Test VectorType initialization."""
    vector_type = VectorType(dimensions=512)
    assert vector_type.dimensions == 512


@pytest.mark.skipif(not PGVECTOR_AVAILABLE, reason="pgvector not available")
def test_vector_type_postgresql_dialect():
    """Test VectorType with PostgreSQL dialect."""
    vector_type = VectorType(dimensions=512)
    dialect = postgresql_dialect()

    # Should use pgvector.sqlalchemy.Vector (imported as Vector) for PostgreSQL
    # Patch the imported name within the module under test
    with patch("spacemodels.db.vector_types.Vector") as mock_vector:
        # Call the method but we don't need to use the result
        _ = vector_type.load_dialect_impl(dialect)

        # Verify the mock (representing the imported Vector class) was called
        mock_vector.assert_called_once_with(512)


def test_vector_type_sqlite_dialect():
    """Test VectorType with SQLite dialect."""
    vector_type = VectorType(dimensions=512)
    dialect = sqlite_dialect()

    # Implementation for SQLite should be JSONB or JSON
    # The actual property might be implementation-specific, so just verify it's not None
    assert vector_type.load_dialect_impl(dialect) is not None


def test_process_bind_param_postgresql():
    """Test process_bind_param with PostgreSQL."""
    vector_type = VectorType(dimensions=512)
    dialect = MagicMock()
    dialect.name = "postgresql"

    # Test with some vector data
    test_vector = [0.1, 0.2, 0.3]

    # With pgvector available, should return as is
    # Without pgvector, should JSON-encode
    with patch("spacemodels.db.vector_types.PGVECTOR_AVAILABLE", PGVECTOR_AVAILABLE):
        result = vector_type.process_bind_param(test_vector, dialect)
        if PGVECTOR_AVAILABLE:
            assert result == test_vector
        else:
            assert isinstance(result, str)
            assert json.loads(result) == test_vector


def test_process_bind_param_sqlite():
    """Test process_bind_param with SQLite."""
    vector_type = VectorType(dimensions=512)
    dialect = MagicMock()
    dialect.name = "sqlite"

    # Test with some vector data
    test_vector = [0.1, 0.2, 0.3]

    result = vector_type.process_bind_param(test_vector, dialect)
    # Should JSON-encode for SQLite
    assert isinstance(result, str)
    assert json.loads(result) == test_vector


def test_process_result_value_postgresql():
    """Test process_result_value with PostgreSQL."""
    vector_type = VectorType(dimensions=512)
    dialect = MagicMock()
    dialect.name = "postgresql"

    with patch("spacemodels.db.vector_types.PGVECTOR_AVAILABLE", PGVECTOR_AVAILABLE):
        if PGVECTOR_AVAILABLE:
            # Test with numpy array (as pgvector would return)
            test_array = np.array([0.1, 0.2, 0.3])
            result = vector_type.process_result_value(test_array, dialect)
            assert isinstance(result, list)
            assert result == test_array.tolist()
        else:
            # Without pgvector, test with JSON string
            test_json = json.dumps([0.1, 0.2, 0.3])
            result = vector_type.process_result_value(test_json, dialect)
            assert result == [0.1, 0.2, 0.3]


def test_process_result_value_sqlite():
    """Test process_result_value with SQLite."""
    vector_type = VectorType(dimensions=512)
    dialect = MagicMock()
    dialect.name = "sqlite"

    # SQLite would store it as JSON string
    test_json = json.dumps([0.1, 0.2, 0.3])

    result = vector_type.process_result_value(test_json, dialect)
    assert result == [0.1, 0.2, 0.3]


def test_check_pgvector_extension():
    """Test check_pgvector_extension function."""
    mock_engine = MagicMock()
    mock_connection = mock_engine.connect.return_value.__enter__.return_value
    mock_connection.execute.return_value.scalar.return_value = True

    if PGVECTOR_AVAILABLE:
        assert check_pgvector_extension(mock_engine) is True
        mock_connection.execute.assert_called_once()
    else:
        assert check_pgvector_extension(mock_engine) is False


def test_install_pgvector_extension():
    """Test install_pgvector_extension function."""
    mock_engine = MagicMock()
    mock_connection = mock_engine.connect.return_value.__enter__.return_value

    if PGVECTOR_AVAILABLE:
        assert install_pgvector_extension(mock_engine) is True
        mock_connection.execute.assert_called_once()
        mock_connection.commit.assert_called_once()
    else:
        assert install_pgvector_extension(mock_engine) is False


def test_python_type():
    """Test python_type property."""
    vector_type = VectorType(dimensions=512)
    assert vector_type.python_type is list
