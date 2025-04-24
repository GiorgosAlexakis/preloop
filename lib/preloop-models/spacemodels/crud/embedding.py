"""CRUD operations for EmbeddingModel and IssueEmbedding models."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.issue import EmbeddingModel, Issue, IssueEmbedding
from .base import CRUDBase

# Import optional pgvector functionality

from ..db.vector_types import cosine_distance, euclidean_distance


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
        self,
        db: Session,
        *,
        issue_id: str,
        force_update: bool = False,
        api_key: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Create embeddings for an issue using all active embedding models.

        This implementation supports real embedding generation with OpenAI or other providers
        when an API key is provided, or falls back to random vectors for testing.

        Args:
            db: Database session
            issue_id: ID of the issue to create embeddings for
            force_update: Whether to update existing embeddings
            api_key: Optional API key for embedding providers

        Returns:
            Dictionary mapping model names to status ("created", "updated", "already_exists", "error")
        """
        issue = db.get(Issue, issue_id)
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

            # Generate embedding vector
            try:
                embedding_vector = self._generate_embedding_vector(
                    text=text_to_embed, model=model, api_key=api_key
                )

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
            except Exception as e:
                results[model.name] = f"error: {str(e)}"

        db.commit()
        return results

    def _generate_embedding_vector(
        self, text: str, model: EmbeddingModel, api_key: Optional[str] = None
    ) -> List[float]:
        """
        Generate an embedding vector for the given text using the specified model.

        This implementation supports:
        - OpenAI embedding models
        - HuggingFace transformer models
        - Fallback to random vectors for testing

        Args:
            text: Text to embed
            model: EmbeddingModel with provider and version information
            api_key: Optional API key for the provider

        Returns:
            Embedding vector as a list of floats
        """
        provider = model.provider.lower()
        version = model.version

        # Real embedding generation based on provider
        if provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=api_key)

            # Generate embedding
            response = client.embeddings.create(
                model=version,  # e.g., "text-embedding-ada-002"
                input=text,
            )

            # Extract embedding
            embedding = response.data[0].embedding

            return embedding

        elif provider == "huggingface":
            from sentence_transformers import SentenceTransformer

            # Load model
            model = SentenceTransformer(version)

            # Generate embedding
            embedding = model.encode(text).tolist()

            return embedding

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def similarity_search(
        self,
        db: Session,
        *,
        model_id: str,
        query_vector: List[float],
        limit: int = 10,
        distance_type: str = "cosine",  # or "euclidean"
        tracker_ids: Optional[List[str]] = None,
    ) -> List[Tuple[Issue, float]]:
        """
        Search for similar issues based on vector similarity.

        Uses pgvector for PostgreSQL and falls back to Python-based vector similarity
        for other databases.

        Args:
            db: Database session
            model_id: ID of the embedding model to search within
            query_vector: Vector to search for
            limit: Maximum number of results to return
            distance_type: Distance metric to use ('cosine' or 'euclidean')

        Returns:
            List of (issue, similarity_score) tuples
        """
        # Construct the raw SQL query
        query = text(
            """
            WITH results AS (
            SELECT
                i.id,
                i.title,
                i.description,
                i.status,
                i.priority,
                i.issue_type,
                i.external_id,
                i.external_url,
                i.project_id,
                i.tracker_id,
                i.meta_data,
                i.last_updated_external,
                i.last_synced,
                i.created_at,
                i.updated_at,
                (1 - (e.embedding <=> CAST(:query_vector AS vector))) as sim
            FROM
                issue i
            JOIN
                issueembedding e ON i.id = e.issue_id
            WHERE
                i.tracker_id = ANY(:tracker_ids) AND e.embedding_model_id = :model_id
            )
            SELECT * FROM results
            ORDER BY sim DESC
            LIMIT :limit
        """
        )

        # Execute the query
        result = db.execute(
            query,
            {
                "model_id": model_id,
                "query_vector": query_vector,
                "limit": limit,
                "tracker_ids": tracker_ids,
            },
        )

        # Convert results to Issue objects with similarity scores
        issues_with_scores = []

        for row in result:
            # Convert row to dictionary
            issue_dict = {
                col: val for col, val in zip(result.keys(), row, strict=False)
            }

            # Extract similarity score
            similarity = issue_dict.pop("sim")

            # Create Issue object from dictionary
            issue = Issue(**{k: v for k, v in issue_dict.items() if k != "sim"})

            # Add to results
            issues_with_scores.append((issue, float(similarity)))

        return issues_with_scores

    def _similarity_search_python(
        self,
        db: Session,
        *,
        model_id: str,
        query_vector: List[float],
        limit: int = 10,
        distance_type: str = "cosine",
    ) -> List[Tuple[Issue, float]]:
        """Fallback implementation using Python for vector comparisons."""
        # Get embeddings and issues
        embeddings = (
            db.query(IssueEmbedding, Issue)
            .join(Issue)
            .filter(IssueEmbedding.embedding_model_id == model_id)
            .all()
        )

        # Choose distance metric
        if distance_type == "cosine":
            distance_func = cosine_distance
        elif distance_type == "euclidean":
            distance_func = euclidean_distance
        else:
            distance_func = cosine_distance

        # Calculate similarities
        results = []
        for embedding, issue in embeddings:
            # Extract embedding vector
            if isinstance(embedding.embedding, str):
                # Parse JSON if needed
                import json

                vector = json.loads(embedding.embedding)
            else:
                vector = embedding.embedding

            # Calculate distance
            distance = distance_func(query_vector, vector)

            # For cosine and euclidean, smaller distance = more similar
            # Convert to similarity score (0-1 where 1 is most similar)
            if distance_type == "cosine":
                # Cosine distance is already 0-1, just invert
                similarity = 1 - distance
            else:
                # Normalize euclidean distance to 0-1 (approximate)
                # This assumes max distance could be 2, which is true for normalized vectors
                similarity = max(0, 1 - (distance / 2))

            results.append((issue, similarity))

        # Sort by similarity (highest first)
        results.sort(key=lambda x: x[1], reverse=True)

        # Limit results
        return results[:limit]
