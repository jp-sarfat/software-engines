"""
Persistent memory backed by SQLite.

Qyvella's long-term brain.  Conversations, messages, things she's
learned about her user, and her own reflections survive across restarts.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "qyvella.db"
_local = threading.local()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_conn(db_path: Path) -> sqlite3.Connection:
    """Thread-local SQLite connection with WAL mode."""
    key = str(db_path)
    conn: Optional[sqlite3.Connection] = getattr(_local, key, None)
    if conn is None:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        setattr(_local, key, conn)
    return conn


class MemoryStore:
    """
    Persistent store for everything Qyvella remembers.

    Tables
    ------
    conversations  – chat sessions
    messages       – individual messages inside a conversation
    memories       – long-term extracted facts (user preferences, project info, etc.)
    learnings      – things Qyvella has learned that shape her behaviour
    reflections    – her own self-reflections
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._cursor() as cur:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT DEFAULT '',
                    started_at  TEXT NOT NULL,
                    ended_at    TEXT,
                    summary     TEXT DEFAULT '',
                    mood        TEXT DEFAULT 'neutral',
                    message_count INTEGER DEFAULT 0,
                    total_tokens  INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                    role            TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                    content         TEXT NOT NULL,
                    emotion         TEXT DEFAULT 'neutral',
                    tokens          INTEGER DEFAULT 0,
                    created_at      TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    category    TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    confidence  REAL DEFAULT 1.0,
                    source      TEXT DEFAULT '',
                    access_count INTEGER DEFAULT 0,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    UNIQUE(category, key)
                );

                CREATE TABLE IF NOT EXISTS learnings (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    importance  REAL DEFAULT 0.5,
                    times_used  INTEGER DEFAULT 0,
                    active      INTEGER DEFAULT 1,
                    created_at  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reflections (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt      TEXT NOT NULL,
                    response    TEXT NOT NULL,
                    insights    TEXT DEFAULT '[]',
                    created_at  TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_mem_cat  ON memories(category);
            """)

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def start_conversation(self, title: str = "") -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (title, started_at) VALUES (?, ?)",
                (title, _now()),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def end_conversation(self, conv_id: int, summary: str = "") -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE conversations SET ended_at=?, summary=? WHERE id=?",
                (_now(), summary, conv_id),
            )

    def get_active_conversation(self) -> Optional[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM conversations WHERE ended_at IS NULL "
                "ORDER BY started_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_conversation(self, conv_id: int) -> Optional[dict]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM conversations WHERE id=?", (conv_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_conversations(self, limit: int = 20) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM conversations ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    def update_conversation_stats(self, conv_id: int, tokens: int = 0) -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE conversations SET message_count = "
                "(SELECT COUNT(*) FROM messages WHERE conversation_id=?), "
                "total_tokens = total_tokens + ? WHERE id=?",
                (conv_id, tokens, conv_id),
            )

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        emotion: str = "neutral",
        tokens: int = 0,
    ) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO messages (conversation_id, role, content, emotion, tokens, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, role, content, emotion, tokens, _now()),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_messages(
        self, conversation_id: int, limit: int = 50
    ) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM messages WHERE conversation_id=? "
                "ORDER BY created_at DESC LIMIT ?",
                (conversation_id, limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
            rows.reverse()
            return rows

    def get_recent_messages_across_conversations(self, limit: int = 30) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            rows.reverse()
            return rows

    def total_message_count(self) -> int:
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages")
            return cur.fetchone()[0]

    def search_messages(self, query: str, limit: int = 30) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT m.*, c.title as conversation_title "
                "FROM messages m JOIN conversations c ON m.conversation_id = c.id "
                "WHERE m.content LIKE ? ORDER BY m.created_at DESC LIMIT ?",
                (f"%{query}%", limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def search_conversations(self, query: str, limit: int = 20) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT DISTINCT c.* FROM conversations c "
                "LEFT JOIN messages m ON c.id = m.conversation_id "
                "WHERE c.title LIKE ? OR c.summary LIKE ? OR m.content LIKE ? "
                "ORDER BY c.started_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            )
            return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Memories (long-term facts)
    # ------------------------------------------------------------------

    def remember(
        self,
        category: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source: str = "",
    ) -> None:
        now = _now()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO memories (category, key, value, confidence, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(category, key) DO UPDATE SET "
                "value=excluded.value, confidence=excluded.confidence, updated_at=excluded.updated_at",
                (category, key, value, confidence, source, now, now),
            )

    def recall(self, category: Optional[str] = None, limit: int = 30) -> list[dict]:
        with self._cursor() as cur:
            if category:
                cur.execute(
                    "SELECT * FROM memories WHERE category=? ORDER BY updated_at DESC LIMIT ?",
                    (category, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                )
            rows = [dict(r) for r in cur.fetchall()]
            for row in rows:
                with self._cursor() as c2:
                    c2.execute(
                        "UPDATE memories SET access_count = access_count + 1 WHERE id=?",
                        (row["id"],),
                    )
            return rows

    def recall_about_user(self) -> list[dict]:
        return self.recall(category="user")

    def search_memories(self, query: str) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM memories WHERE key LIKE ? OR value LIKE ? "
                "ORDER BY confidence DESC LIMIT 20",
                (f"%{query}%", f"%{query}%"),
            )
            return [dict(r) for r in cur.fetchall()]

    def forget(self, category: str, key: str) -> bool:
        with self._cursor() as cur:
            cur.execute(
                "DELETE FROM memories WHERE category=? AND key=?",
                (category, key),
            )
            return cur.rowcount > 0

    def forget_by_id(self, memory_id: int) -> bool:
        with self._cursor() as cur:
            cur.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            return cur.rowcount > 0

    def export_all(self) -> dict[str, Any]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM memories ORDER BY category, key")
            memories = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT * FROM learnings ORDER BY importance DESC")
            learnings = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT * FROM reflections ORDER BY created_at DESC")
            reflections = [dict(r) for r in cur.fetchall()]
            return {
                "memories": memories,
                "learnings": learnings,
                "reflections": reflections,
                "exported_at": _now(),
            }

    def import_memories(self, data: list[dict]) -> int:
        count = 0
        for item in data:
            cat = item.get("category", "")
            key = item.get("key", "")
            val = item.get("value", "")
            if cat and key and val:
                self.remember(
                    category=cat,
                    key=key,
                    value=val,
                    confidence=item.get("confidence", 1.0),
                    source=item.get("source", "import"),
                )
                count += 1
        return count

    # ------------------------------------------------------------------
    # Learnings
    # ------------------------------------------------------------------

    def add_learning(self, kind: str, content: str, importance: float = 0.5) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO learnings (kind, content, importance, created_at) VALUES (?, ?, ?, ?)",
                (kind, content, importance, _now()),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_active_learnings(self, limit: int = 20) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM learnings WHERE active=1 ORDER BY importance DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_all_learnings(self, limit: int = 50) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM learnings ORDER BY importance DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    def deactivate_learning(self, learning_id: int) -> bool:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE learnings SET active=0 WHERE id=?", (learning_id,)
            )
            return cur.rowcount > 0

    def reactivate_learning(self, learning_id: int) -> bool:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE learnings SET active=1 WHERE id=?", (learning_id,)
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Reflections
    # ------------------------------------------------------------------

    def add_reflection(self, prompt: str, response: str, insights: list[str] | None = None) -> int:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO reflections (prompt, response, insights, created_at) VALUES (?, ?, ?, ?)",
                (prompt, response, json.dumps(insights or []), _now()),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_recent_reflections(self, limit: int = 5) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM reflections ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Stats for consciousness
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM conversations")
            convos = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM messages")
            msgs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM memories")
            mems = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM learnings WHERE active=1")
            learns = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM reflections")
            refs = cur.fetchone()[0]
            return {
                "conversations": convos,
                "messages": msgs,
                "memories": mems,
                "learnings": learns,
                "reflections": refs,
            }
