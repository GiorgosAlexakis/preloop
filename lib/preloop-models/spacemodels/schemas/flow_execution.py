import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


# Base Pydantic model for FlowExecution attributes
class FlowExecutionBase(BaseModel):
    flow_id: uuid.UUID = Field(..., description="Foreign Key to Flows.id")
    trigger_event_id: Optional[str] = Field(
        None,
        description="Identifier for the specific event that triggered this execution",
    )
    trigger_event_details: Optional[Dict[str, Any]] = Field(
        None, description="A snapshot of the payload of the triggering event"
    )
    status: str = Field(
        "PENDING",
        description="Status of the execution (e.g., PENDING, RUNNING, SUCCEEDED, FAILED)",
    )
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the execution started",
    )
    end_time: Optional[datetime] = Field(
        None, description="Timestamp when the execution ended"
    )
    resolved_input_prompt: Optional[str] = Field(
        None, description="The full prompt after placeholder resolution"
    )
    model_output_summary: Optional[str] = Field(
        None,
        description="A concise summary of the AI model's final output or key findings",
    )
    actions_taken_summary: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="A structured log of significant actions performed by the agent",
    )
    mcp_usage_logs: Optional[List[Dict[str, Any]]] = Field(
        None, description="Detailed log of each MCP tool call"
    )
    agent_session_reference: Optional[str] = Field(
        None,
        description="Reference to agent session (e.g., session ID, K8s job ID, container ID, process ID)",
    )
    error_message: Optional[str] = Field(
        None, description="Error message if the execution failed"
    )
    tool_calls_count: Optional[int] = Field(
        0, description="Total number of tool/MCP calls made during execution"
    )
    total_tokens: Optional[int] = Field(
        0, description="Total tokens used (input + output) during execution"
    )
    estimated_cost: Optional[float] = Field(
        0.0, description="Estimated cost in USD for this execution"
    )

    model_config = ConfigDict(from_attributes=True)


# Pydantic model for creating a FlowExecution (API input - likely internal)
class FlowExecutionCreate(FlowExecutionBase):
    pass  # Most fields will be set by the system during creation


# Pydantic model for updating a FlowExecution (API input - likely internal for status changes)
class FlowExecutionUpdate(BaseModel):
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    resolved_input_prompt: Optional[str] = None
    model_output_summary: Optional[str] = None
    actions_taken_summary: Optional[List[Dict[str, Any]]] = None
    mcp_usage_logs: Optional[List[Dict[str, Any]]] = None
    agent_session_reference: Optional[str] = None
    error_message: Optional[str] = None
    tool_calls_count: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost: Optional[float] = None


# Pydantic model for representing a FlowExecution in API responses (includes DB fields)
class FlowExecutionResponse(FlowExecutionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Include flow name for display purposes
    flow_name: Optional[str] = None

    # Example of how to include related data if needed
    # flow: Optional[FlowResponse] = None # Assuming a FlowResponse Pydantic schema exists


# Schema for FlowExecution as stored in DB (identical to Response for now)
class FlowExecutionInDB(FlowExecutionResponse):
    pass


# Pydantic model for sending commands to a flow execution
class FlowExecutionCommand(BaseModel):
    command: str = Field(..., description="Command to send (e.g., 'stop', 'pause')")
    payload: Optional[Dict[str, Any]] = Field(
        None, description="Optional payload for the command"
    )
