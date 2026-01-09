"""Pydantic schemas for AIModel."""

import uuid
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from preloop.models.models.mixins import TimestampMixin


class AIModelBase(BaseModel):
    """Base schema for AIModel, containing common attributes."""

    name: str = Field(..., description="User-defined name for this model configuration")
    description: Optional[str] = Field(None, description="Optional description")
    provider_name: str = Field(..., description="e.g., 'openai', 'anthropic'")
    model_identifier: str = Field(
        ..., description="Standardized identifier, e.g., 'gpt-4-turbo'"
    )
    api_endpoint: Optional[str] = Field(
        None, description="URL for the model's API, if not standard"
    )
    api_key: Optional[str] = Field(None, description="API key for the model provider")
    is_default: bool = Field(
        False, description="Indicates if this is the default model for the account"
    )
    model_parameters: Optional[Dict] = Field(
        None,
        description="Optional, for model-specific parameters like temperature, max_tokens",
    )
    meta_data: Optional[Dict] = Field(
        None, description="Optional, for custom fields, labels, etc."
    )


class AIModelCreate(AIModelBase):
    """Schema for creating a new AIModel entry."""

    pass


class AIModelUpdate(BaseModel):
    """Schema for updating an existing AIModel entry. All fields are optional."""

    name: Optional[str] = None
    description: Optional[str] = None
    provider_name: Optional[str] = None
    model_identifier: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    is_default: Optional[bool] = None
    model_parameters: Optional[Dict] = None
    meta_data: Optional[Dict] = None


class AIModelInDBBase(AIModelBase, TimestampMixin):
    """Base schema for AIModel entries as stored in the database."""

    id: uuid.UUID = Field(..., description="Primary key")
    account_id: Optional[uuid.UUID] = Field(
        None, description="Account this model belongs to"
    )

    @field_serializer("account_id")
    def serialize_account_id(self, value: Optional[uuid.UUID]) -> Optional[str]:
        """Serialize UUID to string for JSON response."""
        return str(value) if value is not None else None

    model_config = ConfigDict(from_attributes=True)


class AIModelRead(AIModelInDBBase):
    """Schema for reading AIModel entries, including timestamps."""

    pass
