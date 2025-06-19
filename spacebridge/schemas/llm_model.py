"""Pydantic schemas for LLMModel."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LLMModelBase(BaseModel):
    """Base schema for LLMModel, containing common attributes."""

    name: str
    provider_name: str
    api_key: str
    api_url: str
    model_name: str
    model_version: Optional[str] = None
    is_default: Optional[bool] = False


class LLMModelCreate(LLMModelBase):
    """Schema for creating a new LLMModel entry."""

    pass


class LLMModelUpdate(LLMModelBase):
    """Schema for updating an existing LLMModel entry. All fields are optional."""

    name: Optional[str] = None
    provider_name: Optional[str] = None
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    is_default: Optional[bool] = None


class LLMModelInDBBase(LLMModelBase):
    """Base schema for LLMModel entries as stored in the database."""

    id: str
    account_id: str

    class Config:
        from_attributes = True


class LLMModelRead(LLMModelInDBBase):
    """Schema for reading LLMModel entries, including timestamps."""

    created_at: datetime
    updated_at: datetime
