"""Pydantic schemas for LLMProvider."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class LLMProviderBase(BaseModel):
    """Base schema for LLMProvider, containing common attributes."""

    provider_name: str
    credentials: Dict[str, Any]
    is_default: Optional[bool] = False


class LLMProviderCreate(LLMProviderBase):
    """Schema for creating a new LLMProvider entry."""

    pass


class LLMProviderUpdate(LLMProviderBase):
    """Schema for updating an existing LLMProvider entry. All fields are optional."""

    provider_name: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


class LLMProviderInDBBase(LLMProviderBase):
    """Base schema for LLMProvider entries as stored in the database."""

    id: str
    account_id: str

    class Config:
        from_attributes = True


class LLMProviderRead(LLMProviderInDBBase):
    """Schema for reading LLMProvider entries, including timestamps."""

    created_at: datetime
    updated_at: datetime
