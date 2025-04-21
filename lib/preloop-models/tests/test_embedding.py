"""Tests for embedding functionality."""

from spacemodels.crud import crud_embedding_model, crud_issue_embedding
from spacemodels.models.issue import IssueEmbedding


def test_create_embedding_model(db_session):
    """Test creating a new embedding model."""
    model_data = {
        "name": "test-embeddings",
        "provider": "openai",
        "version": "text-embedding-ada-002",
        "dimensions": 1536,
        "is_active": True,
        "meta_data": {},
    }

    model = crud_embedding_model.create(db_session, obj_in=model_data)
    assert model.name == model_data["name"]
    assert model.provider == model_data["provider"]
    assert model.dimensions == model_data["dimensions"]
    assert model.is_active is True

    # Verify it was saved in the database
    db_model = crud_embedding_model.get(db_session, id=model.id)
    assert db_model is not None
    assert db_model.id == model.id


def test_create_issue_embedding(db_session, create_issue, create_embedding_model):
    """Test creating an issue embedding."""
    # Create test issue and embedding model
    issue = create_issue()
    model = create_embedding_model()

    # Create embedding for the issue
    result = crud_issue_embedding.create_embeddings(
        db_session, issue_id=issue.id, force_update=False
    )

    # Check result contains the model name with success status
    assert model.name in result
    assert result[model.name] == "created"

    # Verify embedding was created in the database
    embeddings = crud_issue_embedding.get_for_issue(db_session, issue_id=issue.id)
    assert model.name in embeddings

    # Verify the embedding has the correct dimension
    embedding = embeddings[model.name]
    assert len(embedding.embedding) == model.dimensions


def test_similarity_search(db_session, create_issue, create_embedding_model):
    """Test similarity search functionality."""
    # Create embedding model
    model = create_embedding_model(dimensions=4)  # Small dimension for testing

    # Create test issues
    issue1 = create_issue(title="Bug in login feature")
    issue2 = create_issue(title="Feature request: dashboard")
    issue3 = create_issue(title="Login page crashes on mobile")

    # Create fixed embeddings for testing similarity
    embeddings = [
        [1.0, 0.0, 0.0, 0.0],  # issue1
        [0.0, 1.0, 0.0, 0.0],  # issue2
        [0.8, 0.2, 0.0, 0.0],  # issue3 (more similar to issue1)
    ]

    # Manually create embeddings
    for issue, emb in zip([issue1, issue2, issue3], embeddings, strict=False):
        embedding = IssueEmbedding(
            issue_id=issue.id,
            embedding_model_id=model.id,
            embedding=emb,
            meta_data={"test": True},
        )
        db_session.add(embedding)
    db_session.commit()

    # Search with a vector similar to issue1
    query_vector = [0.9, 0.1, 0.0, 0.0]
    results = crud_issue_embedding.similarity_search(
        db_session, model_id=model.id, query_vector=query_vector, distance_type="cosine"
    )

    # Check we got results in the right order (issue1, issue3, issue2)
    assert len(results) == 3
    assert results[0][0].id == issue1.id  # Most similar
    assert results[1][0].id == issue3.id  # Second most similar
    assert results[2][0].id == issue2.id  # Least similar
