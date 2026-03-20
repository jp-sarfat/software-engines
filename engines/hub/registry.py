"""
Service registry.

Every program that connects to the hub registers itself here.
The registry tracks endpoints, capabilities, health, and metadata.
"""

from __future__ import annotations

import logging
import sqlite3
import json
import threading
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "qyvella.db"
_local = threading.local()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_conn(db_path: Path) -> sqlite3.Connection:
    key = f"hub_{db_path}"
    conn: Optional[sqlite3.Connection] = getattr(_local, key, None)
    if conn is None:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        setattr(_local, key, conn)
    return conn


class ServiceRegistry:
    """
    Tracks all external services connected to the hub.

    Each service has:
    - name, base_url, api_key (for authenticating outbound calls)
    - capabilities (what it can do)
    - health status (last check, consecutive failures)
    - metadata (version, description, any custom fields)
    """

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._init_schema()

    @contextmanager
    def _cursor(self):
        conn = _get_conn(self.db_path)
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_schema(self) -> None:
        with self._cursor() as cur:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS services (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    name            TEXT NOT NULL UNIQUE,
                    base_url        TEXT NOT NULL,
                    api_key         TEXT DEFAULT '',
                    hub_token       TEXT NOT NULL,
                    description     TEXT DEFAULT '',
                    version         TEXT DEFAULT '',
                    capabilities    TEXT DEFAULT '[]',
                    health_endpoint TEXT DEFAULT '/health',
                    status          TEXT DEFAULT 'registered'
                        CHECK(status IN ('registered','healthy','degraded','down','unknown')),
                    last_health_check TEXT,
                    last_healthy    TEXT,
                    consecutive_failures INTEGER DEFAULT 0,
                    metadata        TEXT DEFAULT '{}',
                    registered_at   TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id  INTEGER NOT NULL REFERENCES services(id),
                    event_type  TEXT NOT NULL,
                    severity    TEXT DEFAULT 'info'
                        CHECK(severity IN ('debug','info','warning','error','critical')),
                    payload     TEXT DEFAULT '{}',
                    processed   INTEGER DEFAULT 0,
                    created_at  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS commands (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id      INTEGER NOT NULL REFERENCES services(id),
                    command         TEXT NOT NULL,
                    payload         TEXT DEFAULT '{}',
                    status          TEXT DEFAULT 'pending'
                        CHECK(status IN ('pending','sent','success','failed','timeout')),
                    response        TEXT DEFAULT '',
                    created_at      TEXT NOT NULL,
                    completed_at    TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_events_svc ON events(service_id);
                CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
                CREATE INDEX IF NOT EXISTS idx_commands_svc ON commands(service_id);
                CREATE INDEX IF NOT EXISTS idx_svc_name ON services(name);
            """)

    # ------------------------------------------------------------------
    # Service CRUD
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        base_url: str,
        *,
        api_key: str = "",
        description: str = "",
        version: str = "",
        capabilities: list[str] | None = None,
        health_endpoint: str = "/health",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        hub_token = secrets.token_urlsafe(32)
        now = _now()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO services "
                "(name, base_url, api_key, hub_token, description, version, "
                "capabilities, health_endpoint, metadata, registered_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET "
                "base_url=excluded.base_url, api_key=excluded.api_key, "
                "description=excluded.description, version=excluded.version, "
                "capabilities=excluded.capabilities, health_endpoint=excluded.health_endpoint, "
                "metadata=excluded.metadata, updated_at=excluded.updated_at",
                (
                    name, base_url, api_key, hub_token, description, version,
                    json.dumps(capabilities or []), health_endpoint,
                    json.dumps(metadata or {}), now, now,
                ),
            )
            svc = self.get_service_by_name(name)
            if svc and svc.get("hub_token"):
                hub_token = svc["hub_token"]
            return {"service_id": svc["id"] if svc else cur.lastrowid, "hub_token": hub_token}

    def unregister(self, name: str) -> bool:
        with self._cursor() as cur:
            cur.execute("SELECT id FROM services WHERE name=?", (name,))
            row = cur.fetchone()
            if not row:
                return False
            sid = row[0]
            cur.execute("DELETE FROM commands WHERE service_id=?", (sid,))
            cur.execute("DELETE FROM events WHERE service_id=?", (sid,))
            cur.execute("DELETE FROM services WHERE id=?", (sid,))
            return True

    def get_service(self, service_id: int) -> Optional[dict]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM services WHERE id=?", (service_id,))
            row = cur.fetchone()
            return self._parse_service(row) if row else None

    def get_service_by_name(self, name: str) -> Optional[dict]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM services WHERE name=?", (name,))
            row = cur.fetchone()
            return self._parse_service(row) if row else None

    def list_services(self) -> list[dict]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM services ORDER BY name")
            return [self._parse_service(r) for r in cur.fetchall()]

    def update_service(self, name: str, **kwargs: Any) -> bool:
        allowed = {"base_url", "api_key", "description", "version",
                   "capabilities", "health_endpoint", "metadata"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return False
        if "capabilities" in updates and isinstance(updates["capabilities"], list):
            updates["capabilities"] = json.dumps(updates["capabilities"])
        if "metadata" in updates and isinstance(updates["metadata"], dict):
            updates["metadata"] = json.dumps(updates["metadata"])
        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [name]
        with self._cursor() as cur:
            cur.execute(f"UPDATE services SET {set_clause} WHERE name=?", values)
            return cur.rowcount > 0

    def validate_hub_token(self, name: str, token: str) -> bool:
        svc = self.get_service_by_name(name)
        if not svc:
            return False
        return svc.get("hub_token") == token

    @staticmethod
    def _parse_service(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["capabilities"] = json.loads(d.get("capabilities", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["capabilities"] = []
        try:
            d["metadata"] = json.loads(d.get("metadata", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["metadata"] = {}
        return d

    # ------------------------------------------------------------------
    # Health checking
    # ------------------------------------------------------------------

    def check_health(self, name: str) -> dict[str, Any]:
        svc = self.get_service_by_name(name)
        if not svc:
            return {"status": "not_found", "name": name}

        url = f"{svc['base_url'].rstrip('/')}{svc['health_endpoint']}"
        headers = {}
        if svc.get("api_key"):
            headers["Authorization"] = f"Bearer {svc['api_key']}"

        now = _now()
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url, headers=headers)
            if resp.status_code < 400:
                self._update_health(svc["id"], "healthy", now)
                return {"status": "healthy", "name": name, "response_code": resp.status_code}
            else:
                self._update_health(svc["id"], "degraded", now, increment_failures=True)
                return {"status": "degraded", "name": name, "response_code": resp.status_code}
        except Exception as exc:
            self._update_health(svc["id"], "down", now, increment_failures=True)
            return {"status": "down", "name": name, "error": str(exc)}

    def check_all_health(self) -> list[dict[str, Any]]:
        services = self.list_services()
        results = []
        for svc in services:
            results.append(self.check_health(svc["name"]))
        return results

    def _update_health(
        self,
        service_id: int,
        status: str,
        checked_at: str,
        increment_failures: bool = False,
    ) -> None:
        with self._cursor() as cur:
            if status == "healthy":
                cur.execute(
                    "UPDATE services SET status=?, last_health_check=?, "
                    "last_healthy=?, consecutive_failures=0 WHERE id=?",
                    (status, checked_at, checked_at, service_id),
                )
            elif increment_failures:
                cur.execute(
                    "UPDATE services SET status=?, last_health_check=?, "
                    "consecutive_failures=consecutive_failures+1 WHERE id=?",
                    (status, checked_at, service_id),
                )
            else:
                cur.execute(
                    "UPDATE services SET status=?, last_health_check=? WHERE id=?",
                    (status, checked_at, service_id),
                )

    # ------------------------------------------------------------------
    # Events (inbound from services)
    # ------------------------------------------------------------------

    def record_event(
        self,
        service_id: int,
        event_type: str,
        severity: str = "info",
        payload: dict | None = None,
    ) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO events (service_id, event_type, severity, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (service_id, event_type, severity, json.dumps(payload or {}), _now()),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_events(
        self,
        service_id: Optional[int] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        with self._cursor() as cur:
            query = "SELECT e.*, s.name as service_name FROM events e JOIN services s ON e.service_id=s.id"
            conditions: list[str] = []
            params: list[Any] = []
            if service_id is not None:
                conditions.append("e.service_id=?")
                params.append(service_id)
            if event_type:
                conditions.append("e.event_type=?")
                params.append(event_type)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY e.created_at DESC LIMIT ?"
            params.append(limit)
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for row in rows:
                try:
                    row["payload"] = json.loads(row.get("payload", "{}"))
                except (json.JSONDecodeError, TypeError):
                    row["payload"] = {}
            return rows

    def get_unprocessed_events(self, limit: int = 50) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT e.*, s.name as service_name FROM events e "
                "JOIN services s ON e.service_id=s.id "
                "WHERE e.processed=0 ORDER BY e.created_at ASC LIMIT ?",
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            for row in rows:
                try:
                    row["payload"] = json.loads(row.get("payload", "{}"))
                except (json.JSONDecodeError, TypeError):
                    row["payload"] = {}
            return rows

    def mark_event_processed(self, event_id: int) -> bool:
        with self._cursor() as cur:
            cur.execute("UPDATE events SET processed=1 WHERE id=?", (event_id,))
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Commands (outbound to services)
    # ------------------------------------------------------------------

    def create_command(
        self,
        service_id: int,
        command: str,
        payload: dict | None = None,
    ) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO commands (service_id, command, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (service_id, command, json.dumps(payload or {}), _now()),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def update_command_status(
        self,
        command_id: int,
        status: str,
        response: str = "",
    ) -> bool:
        with self._cursor() as cur:
            completed = _now() if status in ("success", "failed", "timeout") else None
            cur.execute(
                "UPDATE commands SET status=?, response=?, completed_at=? WHERE id=?",
                (status, response, completed, command_id),
            )
            return cur.rowcount > 0

    def get_commands(
        self, service_id: Optional[int] = None, status: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        with self._cursor() as cur:
            query = "SELECT c.*, s.name as service_name FROM commands c JOIN services s ON c.service_id=s.id"
            conditions: list[str] = []
            params: list[Any] = []
            if service_id is not None:
                conditions.append("c.service_id=?")
                params.append(service_id)
            if status:
                conditions.append("c.status=?")
                params.append(status)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY c.created_at DESC LIMIT ?"
            params.append(limit)
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for row in rows:
                try:
                    row["payload"] = json.loads(row.get("payload", "{}"))
                except (json.JSONDecodeError, TypeError):
                    row["payload"] = {}
            return rows

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM services")
            svc_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM services WHERE status='healthy'")
            healthy = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM services WHERE status='down'")
            down = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM events")
            events = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM events WHERE processed=0")
            unprocessed = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM commands")
            commands = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM commands WHERE status='pending'")
            pending_cmds = cur.fetchone()[0]
            return {
                "total_services": svc_count,
                "healthy_services": healthy,
                "down_services": down,
                "total_events": events,
                "unprocessed_events": unprocessed,
                "total_commands": commands,
                "pending_commands": pending_cmds,
            }
