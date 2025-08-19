import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class FlowBase(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    trigger_event_source: Optional[str] = None
    trigger_event_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    prompt_template: Optional[str] = None
    ai_model_id: Optional[uuid.UUID] = None
    openhands_agent_config: Optional[Dict[str, Any]] = None
    allowed_mcp_servers: Optional[List[str]] = None
    allowed_mcp_tools: Optional[List[Dict[str, Any]]] = None
    is_preset: Optional[bool] = False
    is_enabled: Optional[bool] = True
    account_id: Optional[str] = None


class FlowCreate(FlowBase):
    name: str
    trigger_event_source: str
    trigger_event_type: str
    prompt_template: str
    openhands_agent_config: Dict[str, Any]
    allowed_mcp_servers: List[str] = []
    allowed_mcp_tools: List[Dict[str, Any]] = []


class FlowUpdate(FlowBase):
    pass


class FlowResponse(FlowBase):
    id: uuid.UUID
    account_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
