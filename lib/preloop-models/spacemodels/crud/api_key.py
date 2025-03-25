"""CRUD operations for ApiKey model."""

import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.api_key import ApiKey
from .base import CRUDBase


class CRUDApiKey(CRUDBase[ApiKey]):
    """CRUD operations for API key."""

    def create_with_owner(
        self,
        db: Session,
        *,
        obj_in: Dict[str, Any],
        owner_username: str,
        expires_days: Optional[int] = 365,
    ) -> ApiKey:
        """Create a new API key with owner.

        Args:
            db: Database session
            obj_in: Key data
            owner_username: Username of the key owner
            expires_days: Days until key expiration (None for no expiration)

        Returns:
            Created API key
        """
        obj_in_data = dict(obj_in)
        # Generate a secure key
        key_value = secrets.token_urlsafe(32)

        # Set expiration date if specified
        expires_at = None
        if expires_days is not None:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        db_obj = ApiKey(
            name=obj_in_data.get("name", "API Key"),
            key=key_value,
            created_by=owner_username,
            expires_at=expires_at,
            scopes=obj_in_data.get("scopes", []),
            is_active=True,
        )

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_key(self, db: Session, *, key: str) -> Optional[ApiKey]:
        """Get API key by key string.

        Args:
            db: Database session
            key: The key string to look up

        Returns:
            API key if found
        """
        return db.query(ApiKey).filter(ApiKey.key == key).first()

    def get_active_by_user(
        self, db: Session, *, username: str, skip: int = 0, limit: int = 100
    ) -> List[ApiKey]:
        """Get active API keys for a user.

        Args:
            db: Database session
            username: Username of the key owner
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of active API keys
        """
        return (
            db.query(ApiKey)
            .filter(ApiKey.created_by == username, ApiKey.is_active.is_(True))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_last_used(self, db: Session, *, key_id: Any) -> Optional[ApiKey]:
        """Update the last_used_at field to current timestamp.

        Args:
            db: Database session
            key_id: ID of the key to update

        Returns:
            Updated API key if found
        """
        key_obj = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if key_obj:
            key_obj.last_used_at = datetime.utcnow()
            db.add(key_obj)
            db.commit()
            db.refresh(key_obj)
        return key_obj

    def deactivate(self, db: Session, *, key_id: Any) -> Optional[ApiKey]:
        """Deactivate an API key.

        Args:
            db: Database session
            key_id: ID of the key to deactivate

        Returns:
            Deactivated API key if found
        """
        # Convert string ID to UUID if needed
        key_obj = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if key_obj:
            key_obj.is_active = False
            db.add(key_obj)
            db.commit()
            db.refresh(key_obj)
        return key_obj

    def validate_key(
        self, db: Session, *, key: str, required_scopes: Optional[List[str]] = None
    ) -> Optional[ApiKey]:
        """Validate key and check if it has the required scopes.

        Args:
            db: Database session
            key: Key string to validate
            required_scopes: List of scopes that the key must have

        Returns:
            Valid API key if found and has required scopes, None otherwise
        """
        key_obj = self.get_by_key(db, key=key)

        # Key doesn't exist or is inactive
        if not key_obj or not key_obj.is_active:
            return None

        # Key is expired
        if key_obj.is_expired():
            return None

        # Check scopes if required
        if required_scopes:
            key_scopes = set(key_obj.scopes)
            if not all(scope in key_scopes for scope in required_scopes):
                return None

        # Update last used timestamp
        self.update_last_used(db, key_id=key_obj.id)

        return key_obj
