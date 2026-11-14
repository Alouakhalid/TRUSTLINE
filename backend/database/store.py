"""Small SQLite persistence boundary for TRUSTLINE application services.

The store is deliberately dependency-light so it works at spacecraft edge and in
local tests. Demo records are isolated by the ``is_demo`` column on every domain
record rather than by a frontend-only toggle.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, path: str | None = None) -> None:
        configured = path or os.getenv("TRUSTLINE_DB_PATH", "data/trustline_app.db")
        self.path = ":memory:" if configured == ":memory:" else str(Path(configured))
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._keeper: sqlite3.Connection | None = None
        self._keeper_path: str | None = None
        if self.path == ":memory:":
            self._keeper = self._connect()
            self._keeper_path = ":memory:"
        self.initialize()

    def configure(self, path: str) -> None:
        """Point the store at a new database and re-apply DDL (test/restart seam).

        A ``:memory:`` database keeps a single keeper connection so the schema
        survives between calls; switching to a file path closes any keeper so
        every connection reads and writes that file.
        """
        self.path = ":memory:" if path == ":memory:" else str(Path(path))
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        if self._keeper is not None and self._keeper_path != self.path:
            self._keeper.close()
            self._keeper = None
            self._keeper_path = None
        if self.path == ":memory:" and self._keeper is None:
            self._keeper = self._connect()
            self._keeper_path = ":memory:"
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._keeper or self._connect()
        try:
            with self._lock:
                yield conn
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if self._keeper is None:
                conn.close()

    def initialize(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT NOT NULL, password_hash TEXT NOT NULL,
            role TEXT NOT NULL, astronaut_id TEXT, is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, UNIQUE(username, is_demo)
        );
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
            status TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, sender TEXT NOT NULL,
            content TEXT NOT NULL, agent TEXT, processing_status TEXT NOT NULL,
            citations_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES chat_sessions(id)
        );
        CREATE TABLE IF NOT EXISTS agent_memories (
            id TEXT PRIMARY KEY, astronaut_id TEXT NOT NULL, namespace TEXT NOT NULL,
            content TEXT NOT NULL, verification_status TEXT NOT NULL,
            provenance_json TEXT NOT NULL DEFAULT '{}', expires_at TEXT,
            is_long_term INTEGER NOT NULL DEFAULT 0, is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sync_events (
            id TEXT PRIMARY KEY, event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
            status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TEXT, is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY, actor_user_id TEXT, action TEXT NOT NULL,
            resource_type TEXT NOT NULL, resource_id TEXT, metadata_json TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS telemetry_packets (
            id TEXT PRIMARY KEY, packet_id TEXT NOT NULL, astronaut_id TEXT NOT NULL,
            session_id TEXT NOT NULL, sensor_type TEXT NOT NULL,
            sequence_number INTEGER NOT NULL, sample_rate_hz REAL NOT NULL,
            channels_json TEXT NOT NULL, checksum_crc32 INTEGER NOT NULL,
            checksum_ok INTEGER NOT NULL, sequence_state TEXT NOT NULL,
            timestamp_epoch_ms INTEGER NOT NULL, hardware_metadata_json TEXT NOT NULL DEFAULT '{}',
            received_at TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0,
            UNIQUE(packet_id, astronaut_id, is_demo)
        );
        CREATE TABLE IF NOT EXISTS radiation_packets (
            id TEXT PRIMARY KEY, packet_id TEXT NOT NULL, timestamp_epoch_ms INTEGER NOT NULL,
            dose_rate_microgy_h REAL NOT NULL, equivalent_dose_rate_msv_h REAL NOT NULL,
            cumulative_mission_dose_msv REAL NOT NULL, spe_active INTEGER NOT NULL DEFAULT 0,
            spe_flux_pfu REAL NOT NULL DEFAULT 0, shielding_thickness_g_cm2 REAL NOT NULL,
            alert_level TEXT NOT NULL, received_at TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0, UNIQUE(packet_id, is_demo)
        );
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY, astronaut_id TEXT NOT NULL, session_id TEXT,
            workflow_id TEXT, completion_status TEXT NOT NULL, overall_risk TEXT NOT NULL,
            overall_confidence TEXT, astronaut_response TEXT NOT NULL, assessment_json TEXT NOT NULL,
            evidence_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS sync_checkpoints (
            id TEXT PRIMARY KEY, partition TEXT NOT NULL,
            last_event_id TEXT, last_success_at TEXT,
            events_processed INTEGER NOT NULL DEFAULT 0,
            delivered_total INTEGER NOT NULL DEFAULT 0, failed_total INTEGER NOT NULL DEFAULT 0,
            provider TEXT, updated_at TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0, UNIQUE(partition, is_demo)
        );
        CREATE TABLE IF NOT EXISTS provider_transitions (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL,
            from_state TEXT, to_state TEXT NOT NULL, reason TEXT,
            created_at TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user_mode ON chat_sessions(user_id, is_demo, updated_at);
        CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_memory_scope ON agent_memories(astronaut_id, namespace, is_demo);
        CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_events(status, is_demo, next_attempt_at);
        CREATE INDEX IF NOT EXISTS idx_telemetry_scope ON telemetry_packets(astronaut_id, sensor_type, timestamp_epoch_ms, is_demo);
        CREATE INDEX IF NOT EXISTS idx_assessments_scope ON assessments(astronaut_id, is_demo, created_at);
        CREATE INDEX IF NOT EXISTS idx_transitions_kind ON provider_transitions(kind, is_demo, created_at);
        """
        with self.connection() as conn:
            conn.executescript(ddl)
            self._migrate(conn)

    @staticmethod
    def _add_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
        """Additive, idempotent column migration (never drops or rewrites data)."""
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """P06 additive migrations: astronaut session binding, memory versioning, user profile."""
        self._add_column(conn, "chat_sessions", "astronaut_id", "TEXT")
        self._add_column(conn, "chat_sessions", "summary_ref", "TEXT")
        self._add_column(conn, "chat_sessions", "memory_refs_json", "TEXT NOT NULL DEFAULT '[]'")
        self._add_column(conn, "agent_memories", "version", "INTEGER NOT NULL DEFAULT 1")
        self._add_column(conn, "users", "is_active", "INTEGER NOT NULL DEFAULT 1")
        self._add_column(conn, "users", "display_name", "TEXT")
        self._add_column(conn, "users", "avatar_path", "TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_astronaut ON chat_sessions(astronaut_id, is_demo)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_status ON agent_memories(verification_status, is_demo)")

    def one(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self.connection() as conn:
            return conn.execute(query, params).fetchone()

    def many(self, query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return list(conn.execute(query, params).fetchall())

    def run(self, query: str, params: tuple[Any, ...] = ()) -> None:
        with self.connection() as conn:
            conn.execute(query, params)

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


store = SQLiteStore()
