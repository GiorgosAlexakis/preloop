import uuid
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.future import select

from spacemodels.models.model_configuration import ModelConfiguration
from spacemodels.schemas.model_configuration import (
    ModelConfigurationCreate,
    ModelConfigurationUpdate,
)


# Placeholder for encryption/decryption utilities
# In a real scenario, this would use a robust library like Fernet or a KMS
def encrypt_api_key(api_key: str) -> str:
    # Replace with actual encryption logic
    if not api_key:
        return ""
    return f"encrypted_{api_key}"


def decrypt_api_key(encrypted_api_key: str) -> str:
    # Replace with actual decryption logic
    if not encrypted_api_key or not encrypted_api_key.startswith("encrypted_"):
        return ""
    return encrypted_api_key.replace("encrypted_", "")


async def get_model_configuration(
    db: Session, model_config_id: uuid.UUID
) -> Optional[ModelConfiguration]:
    """
    Retrieve a model configuration by its ID.
    """
    result = await db.execute(
        select(ModelConfiguration).filter(ModelConfiguration.id == model_config_id)
    )
    return result.scalars().first()


async def get_model_configurations_by_organization(
    db: Session, organization_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[ModelConfiguration]:
    """
    Retrieve model configurations for a specific organization.
    """
    result = await db.execute(
        select(ModelConfiguration)
        .filter(ModelConfiguration.organization_id == organization_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def create_model_configuration(
    db: Session,
    model_config_in: ModelConfigurationCreate,
    owner_user_id: Optional[uuid.UUID] = None,
) -> ModelConfiguration:
    """
    Create a new model configuration.
    """
    encrypted_key = None
    if model_config_in.api_key:
        encrypted_key = encrypt_api_key(model_config_in.api_key)

    db_model_config = ModelConfiguration(
        name=model_config_in.name,
        description=model_config_in.description,
        model_identifier=model_config_in.model_identifier,
        api_endpoint=model_config_in.api_endpoint,
        api_key_encrypted=encrypted_key,
        encryption_metadata=model_config_in.encryption_metadata,
        model_parameters=model_config_in.model_parameters,
        owner_user_id=owner_user_id,  # Set based on authenticated user or system
        organization_id=model_config_in.organization_id,
        is_shareable=model_config_in.is_shareable,
    )
    db.add(db_model_config)
    await db.commit()
    await db.refresh(db_model_config)
    return db_model_config


async def update_model_configuration(
    db: Session,
    model_config: ModelConfiguration,
    model_config_in: ModelConfigurationUpdate,
) -> ModelConfiguration:
    """
    Update an existing model configuration.
    """
    update_data = model_config_in.model_dump(exclude_unset=True)

    if "api_key" in update_data and update_data["api_key"] is not None:
        model_config.api_key_encrypted = encrypt_api_key(update_data["api_key"])
        del update_data["api_key"]  # Remove plain text key from update data

    for field, value in update_data.items():
        setattr(model_config, field, value)

    await db.commit()
    await db.refresh(model_config)
    return model_config


async def delete_model_configuration(
    db: Session, model_config_id: uuid.UUID
) -> Optional[ModelConfiguration]:
    """
    Delete a model configuration.
    """
    db_model_config = await get_model_configuration(db, model_config_id)
    if db_model_config:
        await db.delete(db_model_config)
        await db.commit()
    return db_model_config
