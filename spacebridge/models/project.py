"""Project model for SpaceBridge."""

from typing import Dict, List, Optional

from sqlalchemy import Column, ForeignKey, JSON, String
from sqlalchemy.orm import relationship

from spacebridge.db.base import Base


class Project(Base):
    """Project model for SpaceBridge.

    A project belongs to an organization and can be integrated with multiple issue trackers.
    """

    # Primary key
    id = Column(String(36), primary_key=True, index=True)  # UUID

    # Project details
    name = Column(String(255), nullable=False)
    identifier = Column(String(100), nullable=False, index=True)
    description = Column(String(1000), nullable=True)

    # Foreign keys
    organization_id = Column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Project settings stored as JSON
    settings = Column(JSON, nullable=True, default=dict)

    # Issue tracker configurations stored as JSON
    # Structure:
    # {
    #     "jira": {
    #         "url": "https://your-org.atlassian.net",
    #         "project_key": "PROJECT",
    #         # Credentials are stored encrypted
    #         "credentials": "encrypted_credentials_string"
    #     },
    #     "github": {
    #         "repository": "owner/repo",
    #         "credentials": "encrypted_credentials_string"
    #     }
    # }
    tracker_configurations = Column(JSON, nullable=True, default=dict)

    # Relationships
    organization = relationship("Organization", back_populates="projects")

    def __repr__(self) -> str:
        """String representation of the project."""
        return f"<Project {self.name} ({self.identifier}) in {self.organization_id}>"

    @property
    def trackers(self) -> List[str]:
        """Get a list of configured trackers for this project."""
        if not self.tracker_configurations:
            return []
        return list(self.tracker_configurations.keys())
