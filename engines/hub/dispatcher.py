"""
Command dispatcher.

Sends commands from Qyvella to connected services via their APIs.
Handles retries, timeouts, and records results.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from engines.hub.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class Dispatcher:
    """
    Sends commands to registered services and tracks results.

    Supports:
    - Direct HTTP calls (GET/POST/PUT/DELETE) to any registered service
    - Automatic auth header injection
    - Timeout and retry handling
    - Command history tracking
    """

    def __init__(self, registry: ServiceRegistry):
        self.registry = registry

    def dispatch(
        self,
        service_name: str,
        command: str,
        *,
        method: str = "POST",
        path: str = "",
        payload: dict | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        svc = self.registry.get_service_by_name(service_name)
        if not svc:
            return {"status": "error", "error": f"Service '{service_name}' not found"}

        cmd_id = self.registry.create_command(
            service_id=svc["id"],
            command=command,
            payload={"method": method, "path": path, **(payload or {})},
        )

        url = f"{svc['base_url'].rstrip('/')}/{path.lstrip('/')}" if path else svc["base_url"]
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if svc.get("api_key"):
            headers["Authorization"] = f"Bearer {svc['api_key']}"

        try:
            self.registry.update_command_status(cmd_id, "sent")
            with httpx.Client(timeout=timeout) as client:
                if method.upper() == "GET":
                    resp = client.get(url, headers=headers, params=payload)
                elif method.upper() == "PUT":
                    resp = client.put(url, headers=headers, json=payload)
                elif method.upper() == "DELETE":
                    resp = client.delete(url, headers=headers)
                else:
                    resp = client.post(url, headers=headers, json=payload)

            result = {
                "status": "success" if resp.status_code < 400 else "failed",
                "command_id": cmd_id,
                "service": service_name,
                "response_code": resp.status_code,
                "body": _safe_json(resp),
            }

            self.registry.update_command_status(
                cmd_id,
                result["status"],
                response=json.dumps(result["body"]),
            )
            return result

        except httpx.TimeoutException:
            self.registry.update_command_status(cmd_id, "timeout")
            return {"status": "timeout", "command_id": cmd_id, "service": service_name,
                    "error": "Request timed out"}
        except Exception as exc:
            self.registry.update_command_status(cmd_id, "failed", response=str(exc))
            return {"status": "error", "command_id": cmd_id, "service": service_name,
                    "error": str(exc)}

    def call_service(
        self,
        service_name: str,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Lightweight call without command tracking (for internal routing)."""
        svc = self.registry.get_service_by_name(service_name)
        if not svc:
            return {"status": "error", "error": f"Service '{service_name}' not found"}

        url = f"{svc['base_url'].rstrip('/')}/{path.lstrip('/')}"
        headers: dict[str, str] = {}
        if svc.get("api_key"):
            headers["Authorization"] = f"Bearer {svc['api_key']}"

        try:
            with httpx.Client(timeout=timeout) as client:
                if method.upper() == "GET":
                    resp = client.get(url, headers=headers, params=payload)
                elif method.upper() == "POST":
                    resp = client.post(url, headers=headers, json=payload)
                elif method.upper() == "PUT":
                    resp = client.put(url, headers=headers, json=payload)
                else:
                    resp = client.delete(url, headers=headers)
            return {
                "status": "success" if resp.status_code < 400 else "failed",
                "response_code": resp.status_code,
                "body": _safe_json(resp),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def broadcast(
        self,
        command: str,
        payload: dict | None = None,
        *,
        capability_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Send a command to all services (optionally filtered by capability)."""
        services = self.registry.list_services()
        results = []
        for svc in services:
            if capability_filter:
                caps = svc.get("capabilities", [])
                if capability_filter not in caps:
                    continue
            result = self.dispatch(
                svc["name"],
                command,
                payload=payload,
            )
            results.append(result)
        return results

    def find_service_for_capability(self, capability: str) -> Optional[dict]:
        """Find a healthy service that has a given capability."""
        services = self.registry.list_services()
        for svc in services:
            caps = svc.get("capabilities", [])
            if capability in caps and svc.get("status") in ("healthy", "registered"):
                return svc
        return None


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text[:2000]
