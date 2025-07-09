import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base


class ModelConfiguration(Base):
    __tablename__ = "model_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    model_identifier = Column(String, nullable=False, index=True)
    api_endpoint = Column(String, nullable=True)
    api_key_encrypted = Column(String, nullable=True)  # Placeholder for encryption
    encryption_metadata = Column(JSONB, nullable=True)
    model_parameters = Column(JSONB, nullable=True)

    owner_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )  # Assuming a 'users' table
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    is_shareable = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    owner = relationship(
        "User", back_populates="model_configurations"
    )  # Assuming User model has 'model_configurations'
    organization = relationship(
        "Organization", back_populates="model_configurations"
    )  # Assuming Organization model has 'model_configurations'
    flows = relationship(
        "Flow", back_populates="model_configuration"
    )  # Assuming Flow model has 'model_configuration'

    def __repr__(self):
        return f"<ModelConfiguration(id={self.id}, name='{self.name}')>"
