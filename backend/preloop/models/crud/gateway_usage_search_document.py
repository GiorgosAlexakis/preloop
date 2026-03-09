"""CRUD helpers for gateway interaction search corpus rows."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..models.api_usage import ApiUsage
from ..models.gateway_usage_search_document import GatewayUsageSearchDocument
from .base import CRUDBase


class CRUDGatewayUsageSearchDocument(CRUDBase[GatewayUsageSearchDocument]):
    """CRUD operations for `GatewayUsageSearchDocument`."""

    def get_by_api_usage_id(
        self, db: Session, *, api_usage_id: str
    ) -> Optional[GatewayUsageSearchDocument]:
        """Return the corpus row for a specific API usage record."""
        return (
            db.query(GatewayUsageSearchDocument)
            .filter(GatewayUsageSearchDocument.api_usage_id == api_usage_id)
            .first()
        )

    def upsert_for_api_usage(
        self,
        db: Session,
        *,
        api_usage: ApiUsage,
        searchable_text: str,
        meta_data: Optional[Dict[str, Any]] = None,
    ) -> GatewayUsageSearchDocument:
        """Create or update the search corpus row for one gateway interaction."""
        normalized_text = searchable_text.strip()
        content_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
        existing = self.get_by_api_usage_id(db, api_usage_id=str(api_usage.id))

        if existing:
            existing.searchable_text = normalized_text
            existing.content_hash = content_hash
            existing.meta_data = meta_data
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        db_obj = GatewayUsageSearchDocument(
            api_usage_id=api_usage.id,
            searchable_text=normalized_text,
            content_hash=content_hash,
            meta_data=meta_data,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
