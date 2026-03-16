"""
Pydantic models for the Hub engine API.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Service registration
# ------------------------------------------------------------------

class ServiceRegister(BaseModel):
    name: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=1)
    api_key: str = ""
    description: str = ""
    version: str = ""
    capabilities: list[str] = []
    health_endpoint: str = "/health"
    metadata: dict[str, Any] = {}


class ServiceUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    capabilities: Optional[list[str]] = None
    health_endpoint: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ServiceInfo(BaseModel):
    id: int
    name: str
    base_url: str
    description: str = ""
    version: str = ""
    capabilities: list[str] = []
    status: str = "registered"
    last_health_check: Optional[str] = None
    last_healthy: Optional[str] = None
    consecutive_failures: int = 0
    registered_at: str = ""


class ServiceHealth(BaseModel):
    name: str
    status: str
    response_code: Optional[int] = None
    error: Optional[str] = None


# ------------------------------------------------------------------
# Events (inbound from services)
# ------------------------------------------------------------------

class EventPush(BaseModel):
    service_name: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    severity: str = Field(default="info", pattern="^(debug|info|warning|error|critical)$")
    payload: dict[str, Any] = {}


class EventInfo(BaseModel):
    id: int
    service_name: str = ""
    event_type: str
    severity: str = "info"
    payload: dict[str, Any] = {}
    processed: bool = False
    created_at: str = ""


# ------------------------------------------------------------------
# Commands (outbound to services)
# ------------------------------------------------------------------

class CommandRequest(BaseModel):
    service_name: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1)
    method: str = Field(default="POST", pattern="^(GET|POST|PUT|DELETE)$")
    path: str = ""
    payload: dict[str, Any] = {}
    timeout: float = Field(default=30.0, ge=1.0, le=300.0)


class CommandResult(BaseModel):
    status: str
    command_id: Optional[int] = None
    service: str = ""
    response_code: Optional[int] = None
    body: Any = None
    error: Optional[str] = None


class BroadcastRequest(BaseModel):
    command: str = Field(..., min_length=1)
    payload: dict[str, Any] = {}
    capability_filter: Optional[str] = None


# ------------------------------------------------------------------
# Hub status
# ------------------------------------------------------------------

class HubStatus(BaseModel):
    total_services: int = 0
    healthy_services: int = 0
    down_services: int = 0
    total_events: int = 0
    unprocessed_events: int = 0
    total_commands: int = 0
    pending_commands: int = 0
    services: list[ServiceInfo] = []
