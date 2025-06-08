"""Tracker schemas for request and response validation."""

from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, ConfigDict

from spacemodels.models.tracker import TrackerType


class TrackerBase(BaseModel):
    """Base model for tracker data."""

    name: str = Field(..., description="User-friendly name for the tracker")
    tracker_type: TrackerType = Field(..., description="Type of the issue tracker")
    url: Optional[HttpUrl] = Field(
        None, description="URL of the tracker instance (required for Jira)"
    )
    is_active: bool = Field(True, description="Whether the tracker is active")
    connection_details: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Tracker-specific connection details"
    )
    meta_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )
    included_project_identifiers: Optional[List[str]] = Field(
        None,
        description="List of project identifiers to include. None means include all.",
    )
    excluded_project_identifiers: Optional[List[str]] = Field(
        None, description="List of project identifiers to exclude."
    )
    include_future_projects: bool = Field(
        True,
        description="Whether to automatically include new projects if no specific inclusions are set.",
    )
    subscribed_events: Optional[List[str]] = Field(
        default_factory=list,
        description="List of specific webhook event names to subscribe to. Empty list implies default/all events based on client logic.",
    )
    jira_webhook_id: Optional[str] = Field(None, description="Stored Jira Webhook ID")
    # jira_webhook_secret is intentionally not in TrackerBase to avoid accidental exposure.
    # It should be handled in specific create/update schemas if needed for input,
    # and never in response schemas.


class TrackerCreate(TrackerBase):
    """Model for creating a new tracker."""

    api_key: str = Field(..., description="API key or token for the tracker")
    # If Jira provides a secret during webhook creation and we need to store it,
    # it could be added here. For now, assuming it's set/updated separately or
    # derived, and not part of initial creation payload directly for the webhook secret itself.
    # jira_webhook_secret: Optional[str] = Field(None, description="Secret for Jira webhook validation")


class TrackerRegisterRequest(BaseModel):
    """Request model for registering a new tracker."""

    name: str = Field(..., description="User-friendly name for the tracker")
    tracker_type: TrackerType = Field(
        ..., description="Type of the issue tracker", alias="type"
    )
    url: Optional[HttpUrl] = Field(
        None, description="URL of the tracker instance (required for Jira)"
    )
    api_key: str = Field(
        ..., description="API key or token for the tracker", alias="token"
    )
    connection_details: Optional[Dict[str, Any]] = Field(
        None, description="Tracker-specific connection details", alias="config"
    )

    # Fields needed for the base tracker model
    is_active: bool = Field(True, description="Whether the tracker is active")
    meta_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )
    included_project_identifiers: Optional[List[str]] = Field(
        None,
        description="List of project identifiers to include. None means include all.",
    )
    excluded_project_identifiers: Optional[List[str]] = Field(
        None, description="List of project identifiers to exclude."
    )
    include_future_projects: bool = Field(
        True,
        description="Whether to automatically include new projects if no specific inclusions are set.",
    )

    model_config = ConfigDict(
        populate_by_name=True,  # Enables the alias functionality
        json_schema_extra={
            "examples": [
                {
                    "name": "GitHub",
                    "type": "github",
                    "url": "",
                    "token": "your_token",
                    "config": None,
                }
            ]
        },
    )

    def __init__(self, **data):
        super().__init__(**data)
        print("Incoming data:", data)


class TrackerUpdate(BaseModel):
    """Model for updating an existing tracker."""

    name: Optional[str] = Field(None, description="New name for the tracker")
    url: Optional[HttpUrl] = Field(None, description="New URL for the tracker instance")
    api_key: Optional[str] = Field(
        None, description="New API key or token for the tracker"
    )
    is_active: Optional[bool] = Field(None, description="New active status")
    connection_details: Optional[Dict[str, Any]] = Field(
        None, description="Updated connection details"
    )
    meta_data: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")
    included_project_identifiers: Optional[List[str]] = Field(
        None, description="Updated list of included project identifiers."
    )
    excluded_project_identifiers: Optional[List[str]] = Field(
        None, description="Updated list of excluded project identifiers."
    )
    include_future_projects: Optional[bool] = Field(
        None, description="Updated setting for including future projects."
    )
    subscribed_events: Optional[List[str]] = Field(
        None,
        description="Updated list of specific webhook event names to subscribe to.",
    )
    jira_webhook_id: Optional[str] = Field(None, description="Updated Jira Webhook ID")
    jira_webhook_secret: Optional[str] = Field(
        None,
        description="Updated Secret for Jira webhook validation (handle with care)",
    )


class TrackerResponse(TrackerBase):
    """Response model for tracker data (excluding sensitive info like api_key)."""

    id: str = Field(..., description="Tracker unique identifier (UUID)")
    account_id: str = Field(..., description="Account ID owning this tracker")
    is_valid: bool = Field(False, description="Whether the connection is validated")
    last_validation: Optional[str] = Field(
        None, description="Timestamp of the last validation attempt"
    )
    validation_message: Optional[str] = Field(
        None, description="Result message from the last validation"
    )
    created: datetime = Field(..., description="Creation timestamp")
    last_updated: datetime = Field(..., description="Last update timestamp")
    # jira_webhook_secret is intentionally omitted from responses for security.
    # jira_webhook_id is already inherited from TrackerBase and will be included.

    model_config = {"from_attributes": True}


class TrackerTestRequest(BaseModel):
    """Model for testing tracker connection and listing projects."""

    tracker_type: TrackerType = Field(..., description="Type of the issue tracker")
    url: Optional[HttpUrl] = Field(None, description="URL of the tracker instance")
    api_key: str = Field(..., description="API key or token for the tracker")
    connection_details: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Tracker-specific connection details"
    )


class ProjectIdentifier(BaseModel):
    id: str
    name: str
    identifier: str
    type: str = "project"


class OrganizationGroup(BaseModel):
    id: str
    name: str
    type: str = "organization"
    children: List[ProjectIdentifier] = Field(default_factory=list)


class TrackerTestResponse(BaseModel):
    """Response model for testing tracker connection."""

    success: bool = Field(..., description="Whether the connection test was successful")
    message: str = Field(..., description="Connection test result message")
    projects: Optional[List[OrganizationGroup]] = Field(
        None,
        description="List of organizations and their projects if connection succeeded",
    )
