import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class StandardizedNatsEvent(BaseModel):
    """
    Standardized event schema for publishing to NATS.
    """

    event_id: uuid.UUID = Field(
        default_factory=uuid.uuid4, description="Unique identifier for the event."
    )
    event_source: str = Field(
        ...,
        description="Source of the event (e.g., 'github', 'gitlab', 'jira', 'spacebridge_internal').",
    )
    event_type: str = Field(
        ...,
        description="Type of the event, using dot-separated hierarchical naming (e.g., 'github.push', 'jira.issue_created').",
    )
    tracker_id: Optional[uuid.UUID] = Field(
        None, description="Identifier of the associated tracker, if applicable."
    )
    organization_id: Optional[uuid.UUID] = Field(
        None, description="Identifier of the associated organization, if applicable."
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of when the event was generated (UTC).",
    )
    data: Dict[str, Any] = Field(
        ...,
        description="The core event data, typically the original webhook payload or specific data for internal events.",
    )
    source_event_id: Optional[str] = Field(
        None,
        description="Original event identifier from the source system (e.g., GitHub's delivery ID).",
    )

    model_config = ConfigDict(
        json_encoders={
            # Pydantic v2 automatically handles UUID and datetime serialization to JSON.
            # If custom serialization is needed for other types, it can be added here.
        },
        # Example for Pydantic V1 compatibility if needed (though not recommended with V2):
        # arbitrary_types_allowed = True,
        # from_attributes = True # if using ORM models
    )


# Example Usage (for illustration, not part of the actual file content normally)
if __name__ == "__main__":
    example_payload = {
        "repository": {"name": "spacebridge", "owner": {"login": "spacecode"}},
        "pusher": {"name": "user"},
        "commits": [{"id": "commit_sha", "message": "Test commit"}],
    }

    event = StandardizedNatsEvent(
        event_source="github",
        event_type="github.push",
        tracker_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        data=example_payload,
        source_event_id="github-delivery-12345",
    )

    print(event.model_dump_json(indent=2))

    # Example of how it might be published (conceptual)
    # serialized_event = event.model_dump_json().encode()
    # subject = f"spacebridge.events.{event.event_source}.{event.event_type}"
    # print(f"\nSubject: {subject}")
    # print(f"Payload (bytes): {serialized_event}")
