"""Durable, idempotent local-to-ground synchronization primitives."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.database.store import SQLiteStore, store, utc_now


class SyncConflict(Exception):
    """Raised when a medical or authoritative record cannot be merged safely."""


class SyncQueue:
    def __init__(self, db: SQLiteStore = store, max_attempts: int = 5) -> None:
        self.db = db
        self.max_attempts = max_attempts

    def enqueue(self, event_id: str, event_type: str, payload: dict[str, Any], is_demo: bool = False) -> dict[str, Any]:
        existing = self.db.one("SELECT * FROM sync_events WHERE id=? AND is_demo=?", (event_id, int(is_demo)))
        if existing:
            return {**dict(existing), "deduplicated": True, "payload": json.loads(existing["payload_json"])}
        now = utc_now()
        self.db.run("INSERT INTO sync_events(id,event_type,payload_json,status,attempts,next_attempt_at,is_demo,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (event_id, event_type, json.dumps(payload, sort_keys=True), "PENDING", 0, now, int(is_demo), now, now))
        return {"id": event_id, "event_type": event_type, "payload": payload, "status": "PENDING", "attempts": 0, "is_demo": is_demo, "deduplicated": False}

    def claim_ready(self, limit: int = 50, is_demo: bool = False) -> list[dict[str, Any]]:
        rows = self.db.many("SELECT * FROM sync_events WHERE status='PENDING' AND is_demo=? AND (next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY created_at LIMIT ?", (int(is_demo), utc_now(), limit))
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def mark_success(self, event_id: str, is_demo: bool = False) -> None:
        self.db.run("UPDATE sync_events SET status='SYNCED', updated_at=? WHERE id=? AND is_demo=?", (utc_now(), event_id, int(is_demo)))

    def mark_failure(self, event_id: str, reason: str, is_demo: bool = False) -> dict[str, Any]:
        row = self.db.one("SELECT attempts FROM sync_events WHERE id=? AND is_demo=?", (event_id, int(is_demo)))
        if row is None:
            raise KeyError(event_id)
        attempts = int(row["attempts"]) + 1
        status = "DEAD_LETTER" if attempts >= self.max_attempts else "PENDING"
        delay = min(3600, 2 ** min(attempts, 10))
        next_attempt = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
        self.db.run("UPDATE sync_events SET status=?, attempts=?, next_attempt_at=?, updated_at=? WHERE id=? AND is_demo=?", (status, attempts, next_attempt, utc_now(), event_id, int(is_demo)))
        return {"id": event_id, "status": status, "attempts": attempts, "next_attempt_at": next_attempt, "reason": reason}

    def resolve_conflict(self, event_id: str, local_version: int, ground_version: int, is_demo: bool = False) -> dict[str, Any]:
        if local_version != ground_version:
            raise SyncConflict(f"version conflict for {event_id}: local={local_version}, ground={ground_version}")
        self.mark_success(event_id, is_demo=is_demo)
        return {"id": event_id, "status": "SYNCED", "resolution": "IDENTICAL_VERSION"}

    def status(self, is_demo: bool = False) -> dict[str, int]:
        rows = self.db.many("SELECT status, COUNT(*) AS count FROM sync_events WHERE is_demo=? GROUP BY status", (int(is_demo),))
        return {row["status"]: int(row["count"]) for row in rows}
