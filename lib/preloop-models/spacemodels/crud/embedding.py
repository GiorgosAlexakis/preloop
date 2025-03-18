"""CRUD operations for EmbeddingModel and IssueEmbedding models."""

import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models.issue import EmbeddingModel, Issue, IssueEmbedding
from .base import CRUDBase


class CRUDEmbeddingModel(CRUDBase[EmbeddingModel]):
    """CRUD operations for EmbeddingModel model."""

    def get_by_name(self, db: Session, *, name: str) -> Optional[EmbeddingModel]:
        """Get embedding model by name."""
        return db.query(EmbeddingModel).filter(EmbeddingModel.name == name).first()

    def get_by_provider_version(
        self, db: Session, *, provider: str, version: str
    ) -> Optional[EmbeddingModel]:
        """Get embedding model by provider and version."""
        return (
            db.query(EmbeddingModel)
            .filter(
                EmbeddingModel.provider == provider, EmbeddingModel.version == version
            )
            .first()
        )

    def get_active(self, db: Session) -> List[EmbeddingModel]:
        """Get all active embedding models."""
        return db.query(EmbeddingModel).filter(EmbeddingModel.is_active.is_(True)).all()


class CRUDIssueEmbedding(CRUDBase[IssueEmbedding]):
    """CRUD operations for IssueEmbedding model."""

    def get_for_issue(self, db: Session, *, issue_id: str) -> Dict[str, IssueEmbedding]:
        """Get all embeddings for an issue, keyed by model name."""
        embeddings = (
            db.query(IssueEmbedding, EmbeddingModel)
            .join(EmbeddingModel)
            .filter(IssueEmbedding.issue_id == issue_id)
            .all()
        )

        return {model.name: embedding for embedding, model in embeddings}

    def get_for_model(
        self, db: Session, *, model_id: str, skip: int = 0, limit: int = 100
    ) -> List[IssueEmbedding]:
        """Get embeddings for a specific model."""
        return (
            db.query(IssueEmbedding)
            .filter(IssueEmbedding.embedding_model_id == model_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_embeddings(
        self, db: Session, *, issue_id: str, force_update: bool = False
    ) -> Dict[str, str]:
        """Create embeddings for an issue using all active embedding models."""
        issue = db.query(Issue).get(issue_id)
        if not issue:
            raise ValueError(f"Issue with ID {issue_id} not found")

        # Get active embedding models
        embedding_models = (
            db.query(EmbeddingModel).filter(EmbeddingModel.is_active.is_(True)).all()
        )

        results = {}
        for model in embedding_models:
            # Check if embedding already exists
            existing = (
                db.query(IssueEmbedding)
                .filter(
                    IssueEmbedding.issue_id == issue_id,
                    IssueEmbedding.embedding_model_id == model.id,
                )
                .first()
            )

            if existing and not force_update:
                results[model.name] = "already_exists"
                continue

            # Generate text to embed (typically title + description)
            text_to_embed = f"{issue.title}: {issue.description or ''}"

            # In a real implementation, this would call the respective API
            # Here we're just creating a placeholder vector
            embedding_vector = [random.random() for _ in range(model.dimensions)]

            # Create or update embedding
            if existing:
                existing.embedding = embedding_vector
                existing.meta_data = {
                    "updated_at": datetime.utcnow().isoformat(),
                    "text_processed": text_to_embed[:100] + "..."
                    if len(text_to_embed) > 100
                    else text_to_embed,
                }
                db.add(existing)
                results[model.name] = "updated"
            else:
                new_embedding = IssueEmbedding(
                    id=self.model.generate_id(),
                    issue_id=issue_id,
                    embedding_model_id=model.id,
                    embedding=embedding_vector,
                    meta_data={
                        "text_processed": text_to_embed[:100] + "..."
                        if len(text_to_embed) > 100
                        else text_to_embed
                    },
                )
                db.add(new_embedding)
                results[model.name] = "created"

        db.commit()
        return results

    def similarity_search(
        self, db: Session, *, model_id: str, query_vector: List[float], limit: int = 10
    ) -> List[Tuple[Issue, float]]:
        """
        Search for similar issues based on vector similarity.

        Note: This is a placeholder for the actual implementation that would
        use either PostgreSQL with pgvector or an external vector database.

        Returns a list of (issue, similarity_score) tuples.
        """
        # This would actually use a database-specific vector similarity search
        # For PostgreSQL + pgvector, it would use:
        # SELECT i.*, 1 - (e.embedding <=> :query_vector) as similarity
        # FROM issue i
        # JOIN issue_embedding e ON i.id = e.issue_id
        # WHERE e.embedding_model_id = :model_id
        # ORDER BY similarity DESC
        # LIMIT :limit

        # Placeholder implementation
        embeddings = (
            db.query(IssueEmbedding, Issue)
            .join(Issue)
            .filter(IssueEmbedding.embedding_model_id == model_id)
            .limit(limit)
            .all()
        )

        # Simulate similarity scores (random values between 0.5 and 1.0)
        results = [(issue, random.uniform(0.5, 1.0)) for embedding, issue in embeddings]

        # Sort by similarity (highest first)
        results.sort(key=lambda x: x[1], reverse=True)

        return results
