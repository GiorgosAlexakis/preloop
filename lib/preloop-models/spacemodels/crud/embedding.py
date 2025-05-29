"""CRUD operations for EmbeddingModel and IssueEmbedding models."""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.comment import Comment
from ..models.issue import EmbeddingModel, Issue, IssueEmbedding
from .base import CRUDBase

# Import optional pgvector functionality


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
        """Get all embeddings for an issue (including its content and all its comments), keyed by model name."""
        embeddings = (
            db.query(IssueEmbedding, EmbeddingModel)
            .join(EmbeddingModel)
            .filter(IssueEmbedding.issue_id == issue_id)
            .all()
        )

        return {model.name: embedding for embedding, model in embeddings}

    def get_for_issue_content(
        self, db: Session, *, issue_id: str
    ) -> Dict[str, IssueEmbedding]:
        """Get embeddings specifically for an issue's main content (not comments), keyed by model name."""
        embeddings = (
            db.query(IssueEmbedding, EmbeddingModel)
            .join(EmbeddingModel)
            .filter(
                IssueEmbedding.issue_id == issue_id, IssueEmbedding.comment_id.is_(None)
            )
            .all()
        )
        return {model.name: embedding for embedding, model in embeddings}

    def get_for_comment(
        self, db: Session, *, comment_id: str
    ) -> Dict[str, IssueEmbedding]:
        """Get all embeddings for a specific comment, keyed by model name."""
        embeddings = (
            db.query(IssueEmbedding, EmbeddingModel)
            .join(EmbeddingModel)
            .filter(IssueEmbedding.comment_id == comment_id)
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
        comment_id: Optional[str] = None,
        force_update: bool = False,
        api_key: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Create embeddings for an issue's content or a specific comment using all active embedding models.

        This implementation supports real embedding generation with OpenAI or other providers
        when an API key is provided, or falls back to random vectors for testing.

        Args:
            db: Database session
            issue_id: ID of the issue to associate with the embedding
            comment_id: Optional ID of the comment to create embeddings for. If None, creates for issue content.
            force_update: Whether to update existing embeddings
            api_key: Optional API key for embedding providers

        Returns:
            Dictionary mapping model names to status ("created", "updated", "already_exists", "error")
        """
        text_to_embed: str
        source_entity_description: str

        if comment_id:
            comment = db.get(Comment, comment_id)
            if not comment:
                raise ValueError(f"Comment with ID {comment_id} not found")
            if comment.issue_id != issue_id:
                # Or handle as a different kind of error, depending on desired strictness
                raise ValueError(
                    f"Comment {comment_id} does not belong to issue {issue_id}"
                )
            text_to_embed = comment.body
            source_entity_description = f"comment {comment_id}"
        else:
            issue = db.get(Issue, issue_id)
            if not issue:
                raise ValueError(f"Issue with ID {issue_id} not found")
            text_to_embed = f"{issue.title}: {issue.description or ''}"
            source_entity_description = f"issue {issue_id} content"

        if not text_to_embed.strip():
            return {
                model.name: "skipped_empty_text"
                for model in db.query(EmbeddingModel)
                .filter(EmbeddingModel.is_active.is_(True))
                .all()
            }

        # Get active embedding models
        embedding_models = (
            db.query(EmbeddingModel).filter(EmbeddingModel.is_active.is_(True)).all()
        )

        results = {}
        for model in embedding_models:
            # Check if embedding already exists
            query = db.query(IssueEmbedding).filter(
                IssueEmbedding.issue_id == issue_id,
                IssueEmbedding.embedding_model_id == model.id,
            )
            if comment_id:
                query = query.filter(IssueEmbedding.comment_id == comment_id)
            else:
                query = query.filter(IssueEmbedding.comment_id.is_(None))

            existing = query.first()

            if existing and not force_update:
                results[model.name] = f"already_exists_for_{source_entity_description}"
                continue

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
                        "source": source_entity_description,
                        "text_processed": text_to_embed[:100] + "..."
                        if len(text_to_embed) > 100
                        else text_to_embed,
                    }
                    db.add(existing)
                    results[model.name] = f"updated_for_{source_entity_description}"
                else:
                    new_embedding = IssueEmbedding(
                        id=self.model.generate_id(),
                        issue_id=issue_id,
                        comment_id=comment_id,  # Pass comment_id
                        embedding_model_id=model.id,
                        embedding=embedding_vector,
                        meta_data={
                            "source": source_entity_description,
                            "text_processed": text_to_embed[:100] + "..."
                            if len(text_to_embed) > 100
                            else text_to_embed,
                        },
                    )
                    db.add(new_embedding)
                    results[model.name] = f"created_for_{source_entity_description}"
            except Exception as e:
                results[model.name] = f"error_for_{source_entity_description}: {str(e)}"

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
        distance_type: str = "cosine",  # or "euclidean" - Note: distance_type is not used in this SQL version
        tracker_ids: Optional[List[str]] = None,
        project_ids: Optional[List[str]] = None,
        status: Optional[str] = None,
        labels: Optional[List[str]] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        last_updated_before: Optional[datetime] = None,
        last_updated_after: Optional[datetime] = None,
        embedding_type: Optional[
            str
        ] = None,  # New parameter: "issue", "comment", or None
    ) -> List[Tuple[Issue, float]]:
        """
        Search for similar issues based on vector similarity using raw SQL with pgvector.

        Args:
            db: Database session
            model_id: ID of the embedding model to search within
            query_vector: Vector to search for
            limit: Maximum number of results to return
            distance_type: (Currently unused in this SQL implementation) Distance metric.
            tracker_ids: Optional list of tracker IDs to filter by.
            project_ids: Optional list of project IDs to filter by.
            status: Optional status to filter by.
            labels: Optional list of labels to filter by (must contain all specified labels).
            priority: Optional priority to filter by.
            assignee: Optional assignee (stored in meta_data->>'assignee') to filter by.
            last_updated_before: Optional upper bound for issue updated_at.
            last_updated_after: Optional lower bound for issue updated_at.
            embedding_type: Optional type of embedding to filter by.
                            Can be "issue", "comment", or None (default, no type filter).


        Returns:
            List of (issue, similarity_score) tuples
        """
        params = {
            "model_id": model_id,
            "query_vector": query_vector,
            "limit": limit,
        }
        where_clauses = ["e.embedding_model_id = :model_id"]

        if tracker_ids:
            where_clauses.append("i.tracker_id = ANY(:tracker_ids)")
            params["tracker_ids"] = tracker_ids
        if project_ids:
            where_clauses.append("i.project_id = ANY(:project_ids)")
            params["project_ids"] = project_ids
        if status:
            where_clauses.append("i.status = :status")
            params["status"] = status
        if priority:
            where_clauses.append("i.priority = :priority")
            params["priority"] = priority
        if labels:
            # Assuming labels are stored as a JSON array in meta_data['labels']
            # Use JSONB containment operator @>
            where_clauses.append("i.meta_data->'labels' @> CAST(:labels AS JSONB)")
            params["labels"] = json.dumps(labels)  # Pass as JSON string
        if assignee:
            # Assuming assignee is stored as text in meta_data['assignee']
            where_clauses.append("i.meta_data->>'assignee' = :assignee")
            params["assignee"] = assignee
        if last_updated_after:
            where_clauses.append("i.updated_at > :last_updated_after")
            params["last_updated_after"] = last_updated_after
        if last_updated_before:
            where_clauses.append("i.updated_at < :last_updated_before")
            params["last_updated_before"] = last_updated_before

        if embedding_type:
            if embedding_type == "issue":
                where_clauses.append("e.comment_id IS NULL")
            elif embedding_type == "comment":
                where_clauses.append("e.comment_id IS NOT NULL")
            # else: no filter or raise error for invalid type

        where_sql = " AND ".join(where_clauses)

        # Construct the raw SQL query dynamically
        sql = f"""
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
                i.key,
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
                {where_sql}
            )
            SELECT * FROM results
            ORDER BY sim DESC
            LIMIT :limit
        """
        query = text(sql)

        # Execute the query
        result = db.execute(query, params)

        # Convert results to Issue objects with similarity scores
        issues_with_scores = []
        result_keys = result.keys()  # Get keys once

        for row in result:
            # Convert row to dictionary efficiently
            issue_dict = dict(zip(result_keys, row, strict=False))

            # Extract similarity score
            similarity = issue_dict.pop("sim")

            # Create Issue object from dictionary
            # Ensure only valid Issue fields are passed
            valid_keys = {k for k in issue_dict if hasattr(Issue, k)}
            issue = Issue(**{k: issue_dict[k] for k in valid_keys})

            # Add to results
            issues_with_scores.append((issue, float(similarity)))

        return issues_with_scores
