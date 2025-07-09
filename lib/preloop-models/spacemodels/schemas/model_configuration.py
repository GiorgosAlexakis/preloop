import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


# Base Pydantic model for ModelConfiguration attributes
class ModelConfigurationBase(BaseModel):
    name: str = Field(..., description="User-defined name for this model configuration")
    description: Optional[str] = Field(None, description="Optional description")
    model_identifier: str = Field(
        ...,
        description="Standardized identifier, e.g., 'openai/gpt-4-turbo', 'anthropic/claude-3-opus-20240229'",
    )
    api_endpoint: Optional[str] = Field(
        None, description="URL for the model's API, if not standard"
    )
    # API key will be handled separately for creation/update to allow for encryption logic
    encryption_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional, metadata related to encryption, e.g., KEK ID, algorithm, if not implicit",
    )
    model_parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional, for model-specific parameters like temperature, max_tokens",
    )
    owner_user_id: Optional[uuid.UUID] = Field(
        None, description="Foreign Key to Users.id"
    )
    organization_id: uuid.UUID = Field(
        ..., description="Foreign Key to Organizations.id"
    )
    is_shareable: bool = Field(
        False,
        description="Indicates if this configuration can be used by others in the organization",
    )

    class Config:
        orm_mode = True


# Pydantic model for creating a ModelConfiguration (API input)
class ModelConfigurationCreate(ModelConfigurationBase):
    api_key: Optional[str] = Field(
        None, description="Plaintext API key, will be encrypted before storage"
    )


# Pydantic model for updating a ModelConfiguration (API input)
class ModelConfigurationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_identifier: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = Field(
        None,
        description="Plaintext API key, will be encrypted before storage if provided",
    )
    encryption_metadata: Optional[Dict[str, Any]] = None
    model_parameters: Optional[Dict[str, Any]] = None
    is_shareable: Optional[bool] = None


# Pydantic model for representing a ModelConfiguration in API responses (includes DB fields)
class ModelConfiguration(ModelConfigurationBase):
    id: uuid.UUID
    # api_key_encrypted is intentionally omitted from responses for security
    created_at: datetime
    updated_at: datetime

    # Example of how to include related data if needed, adjust based on actual relationships
    # owner: Optional[User] = None # Assuming a User Pydantic schema exists
    # organization: Organization # Assuming an Organization Pydantic schema exists


# Schema for ModelConfiguration as stored in DB (includes encrypted key)
class ModelConfigurationInDB(ModelConfiguration):
    api_key_encrypted: Optional[str] = Field(
        None, description="Encrypted API key as stored in DB"
    )
