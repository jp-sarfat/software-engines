"""
FastAPI router for the Integration Hub.

This is the central nervous system.  Every external program
registers here, pushes events, and receives commands.

Endpoints:
    --- Hub status ---
    GET  /hub/status                     – full hub dashboard
    GET  /hub/health                     – health check all services

    --- Service management ---
    POST /hub/services/register          – register a new service
    GET  /hub/services                   – list all registered services
    GET  /hub/services/{name}            – get a specific service
    PUT  /hub/services/{name}            – update a service
    DELETE /hub/services/{name}          – unregister a service
    GET  /hub/services/{name}/health     – check health of one service

    --- Events (inbound) ---
    POST /hub/events                     – push an event from a service
    GET  /hub/events                     – list recent events
    GET  /hub/events/unprocessed         – unprocessed events queue
    POST /hub/events/{id}/processed      – mark an event as processed

    --- Commands (outbound) ---
    POST /hub/commands/dispatch          – send a command to a service
    POST /hub/commands/broadcast         – send to all (or filtered) services
    GET  /hub/commands                   – list recent commands
    GET  /hub/commands/{id}              – get a specific command

    --- Routing ---
    POST /hub/route                      – find a service by capability and call it
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from engines.hub.registry import ServiceRegistry
from engines.hub.dispatcher import Dispatcher
from engines.hub.models import (
    BroadcastRequest,
    CommandRequest,
    CommandResult,
    EventInfo,
    EventPush,
    HubStatus,
    ServiceHealth,
    ServiceInfo,
    ServiceRegister,
    ServiceUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hub", tags=["Hub"])

_registry = ServiceRegistry()
_dispatcher = Dispatcher(_registry)


def get_registry() -> ServiceRegistry:
    return _registry


def get_dispatcher() -> Dispatcher:
    return _dispatcher


# ======================================================================
# Hub status
# ======================================================================


@router.get("/status", response_model=HubStatus)
async def hub_status():
    stats = _registry.get_stats()
    services = _registry.list_services()
    return HubStatus(
        **stats,
        services=[
            ServiceInfo(
                id=s["id"],
                name=s["name"],
                base_url=s["base_url"],
                description=s.get("description", ""),
                version=s.get("version", ""),
                capabilities=s.get("capabilities", []),
                status=s.get("status", "unknown"),
                last_health_check=s.get("last_health_check"),
                last_healthy=s.get("last_healthy"),
                consecutive_failures=s.get("consecutive_failures", 0),
                registered_at=s.get("registered_at", ""),
            )
            for s in services
        ],
    )


@router.get("/health")
async def check_all_health():
    results = _registry.check_all_health()
    return {"results": results}


# ======================================================================
# Service management
# ======================================================================


@router.post("/services/register")
async def register_service(req: ServiceRegister):
    result = _registry.register(
        name=req.name,
        base_url=req.base_url,
        api_key=req.api_key,
        description=req.description,
        version=req.version,
        capabilities=req.capabilities,
        health_endpoint=req.health_endpoint,
        metadata=req.metadata,
    )
    return {
        "status": "registered",
        "service_id": result["service_id"],
        "hub_token": result["hub_token"],
        "message": (
            f"Service '{req.name}' registered. "
            f"Use the hub_token to authenticate event pushes."
        ),
    }


@router.get("/services", response_model=list[ServiceInfo])
async def list_services():
    services = _registry.list_services()
    return [
        ServiceInfo(
            id=s["id"],
            name=s["name"],
            base_url=s["base_url"],
            description=s.get("description", ""),
            version=s.get("version", ""),
            capabilities=s.get("capabilities", []),
            status=s.get("status", "unknown"),
            last_health_check=s.get("last_health_check"),
            last_healthy=s.get("last_healthy"),
            consecutive_failures=s.get("consecutive_failures", 0),
            registered_at=s.get("registered_at", ""),
        )
        for s in services
    ]


@router.get("/services/{name}", response_model=ServiceInfo)
async def get_service(name: str):
    svc = _registry.get_service_by_name(name)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    return ServiceInfo(
        id=svc["id"],
        name=svc["name"],
        base_url=svc["base_url"],
        description=svc.get("description", ""),
        version=svc.get("version", ""),
        capabilities=svc.get("capabilities", []),
        status=svc.get("status", "unknown"),
        last_health_check=svc.get("last_health_check"),
        last_healthy=svc.get("last_healthy"),
        consecutive_failures=svc.get("consecutive_failures", 0),
        registered_at=svc.get("registered_at", ""),
    )


@router.put("/services/{name}")
async def update_service(name: str, req: ServiceUpdate):
    svc = _registry.get_service_by_name(name)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    _registry.update_service(name, **req.model_dump(exclude_none=True))
    return {"status": "updated", "service": name}


@router.delete("/services/{name}")
async def unregister_service(name: str):
    if not _registry.unregister(name):
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    return {"status": "unregistered", "service": name}


@router.get("/services/{name}/health", response_model=ServiceHealth)
async def check_service_health(name: str):
    result = _registry.check_health(name)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    return ServiceHealth(**result)


# ======================================================================
# Events (inbound from services)
# ======================================================================


@router.post("/events")
async def push_event(req: EventPush):
    svc = _registry.get_service_by_name(req.service_name)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{req.service_name}' not found")

    event_id = _registry.record_event(
        service_id=svc["id"],
        event_type=req.event_type,
        severity=req.severity,
        payload=req.payload,
    )
    return {"status": "recorded", "event_id": event_id}


@router.get("/events", response_model=list[EventInfo])
async def list_events(
    service_name: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
):
    service_id = None
    if service_name:
        svc = _registry.get_service_by_name(service_name)
        if not svc:
            raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
        service_id = svc["id"]

    events = _registry.get_events(service_id=service_id, event_type=event_type, limit=limit)
    return [
        EventInfo(
            id=e["id"],
            service_name=e.get("service_name", ""),
            event_type=e["event_type"],
            severity=e.get("severity", "info"),
            payload=e.get("payload", {}),
            processed=bool(e.get("processed", 0)),
            created_at=e.get("created_at", ""),
        )
        for e in events
    ]


@router.get("/events/unprocessed", response_model=list[EventInfo])
async def unprocessed_events(limit: int = 50):
    events = _registry.get_unprocessed_events(limit=limit)
    return [
        EventInfo(
            id=e["id"],
            service_name=e.get("service_name", ""),
            event_type=e["event_type"],
            severity=e.get("severity", "info"),
            payload=e.get("payload", {}),
            processed=False,
            created_at=e.get("created_at", ""),
        )
        for e in events
    ]


@router.post("/events/{event_id}/processed")
async def mark_processed(event_id: int):
    if not _registry.mark_event_processed(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "processed", "event_id": event_id}


# ======================================================================
# Commands (outbound to services)
# ======================================================================


@router.post("/commands/dispatch", response_model=CommandResult)
async def dispatch_command(req: CommandRequest):
    result = _dispatcher.dispatch(
        service_name=req.service_name,
        command=req.command,
        method=req.method,
        path=req.path,
        payload=req.payload,
        timeout=req.timeout,
    )
    return CommandResult(**result)


@router.post("/commands/broadcast")
async def broadcast_command(req: BroadcastRequest):
    results = _dispatcher.broadcast(
        command=req.command,
        payload=req.payload,
        capability_filter=req.capability_filter,
    )
    return {"results": [CommandResult(**r) for r in results]}


@router.get("/commands")
async def list_commands(
    service_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    service_id = None
    if service_name:
        svc = _registry.get_service_by_name(service_name)
        if not svc:
            raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
        service_id = svc["id"]
    return _registry.get_commands(service_id=service_id, status=status, limit=limit)


# ======================================================================
# Capability routing
# ======================================================================


@router.post("/route")
async def route_by_capability(
    capability: str,
    path: str = "/",
    method: str = "POST",
    payload: dict | None = None,
):
    svc = _dispatcher.find_service_for_capability(capability)
    if not svc:
        raise HTTPException(
            status_code=404,
            detail=f"No healthy service found with capability '{capability}'",
        )
    result = _dispatcher.dispatch(
        service_name=svc["name"],
        command=f"route:{capability}",
        method=method,
        path=path,
        payload=payload,
    )
    return CommandResult(**result)
