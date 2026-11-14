"""Application services that enforce identity and Demo Mode boundaries."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.database.store import SQLiteStore, store, utc_now


def create_session(db: SQLiteStore, user_id: str, title: str, is_demo: bool, astronaut_id: str | None = None, summary_ref: str | None = None, memory_refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    session_id = db.new_id("CHAT")
    now = utc_now()
    db.run(
        "INSERT INTO chat_sessions(id,user_id,title,status,is_demo,created_at,updated_at,astronaut_id,summary_ref,memory_refs_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (session_id, user_id, title.strip() or "New Chat", "ACTIVE", int(is_demo), now, now, astronaut_id, summary_ref, json.dumps(memory_refs or [])),
    )
    return {
        "id": session_id,
        "user_id": user_id,
        "title": title.strip() or "New Chat",
        "status": "ACTIVE",
        "is_demo": is_demo,
        "created_at": now,
        "updated_at": now,
        "astronaut_id": astronaut_id,
        "summary_ref": summary_ref,
        "memory_refs": memory_refs or [],
    }


SESSION_STATUSES = ("ACTIVE", "ARCHIVED")


def get_session(db: SQLiteStore, session_id: str, user_id: str, is_demo: bool) -> dict[str, Any] | None:
    row = db.one("SELECT * FROM chat_sessions WHERE id=? AND user_id=? AND is_demo=?", (session_id, user_id, int(is_demo)))
    if row is None:
        return None
    return _session_row(row)


def _session_row(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["is_demo"] = bool(item["is_demo"])
    item["memory_refs"] = json.loads(item.pop("memory_refs_json", "[]") or "[]")
    return item


def list_sessions(db: SQLiteStore, user_id: str, is_demo: bool, status_filter: str | None = None, query: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Sessions enriched with message_count and the latest message preview."""
    sql = (
        "SELECT s.*, "
        "(SELECT COUNT(*) FROM chat_messages m WHERE m.session_id = s.id) AS message_count, "
        "(SELECT content FROM chat_messages m2 WHERE m2.session_id = s.id ORDER BY m2.created_at DESC, m2.id DESC LIMIT 1) AS latest_preview "
        "FROM chat_sessions s WHERE s.user_id=? AND s.is_demo=?"
    )
    params: list[Any] = [user_id, int(is_demo)]
    if status_filter is None:
        status_filter = "ACTIVE"  # default listing hides archived sessions
    if status_filter not in ("ACTIVE", "ARCHIVED", "ALL"):
        raise ValueError("unsupported session status filter")
    if status_filter != "ALL":
        sql += " AND s.status=?"
        params.append(status_filter)
    if query:
        sql += " AND LOWER(s.title) LIKE ?"
        params.append(f"%{query.lower()}%")
    sql += " ORDER BY s.updated_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    result = []
    for row in db.many(sql, tuple(params)):
        item = _session_row(row)
        item["message_count"] = int(row["message_count"])
        item["latest_preview"] = row["latest_preview"]
        result.append(item)
    return result


def rename_session(db: SQLiteStore, session_id: str, user_id: str, title: str, is_demo: bool) -> dict[str, Any] | None:
    if not get_session(db, session_id, user_id, is_demo):
        return None
    now = utc_now()
    db.run("UPDATE chat_sessions SET title=?, updated_at=? WHERE id=? AND user_id=? AND is_demo=?", (title.strip() or "New Chat", now, session_id, user_id, int(is_demo)))
    return get_session(db, session_id, user_id, is_demo)


def set_session_status(db: SQLiteStore, session_id: str, user_id: str, new_status: str, is_demo: bool) -> dict[str, Any] | None:
    if new_status not in SESSION_STATUSES:
        raise ValueError("unsupported session status")
    if not get_session(db, session_id, user_id, is_demo):
        return None
    db.run("UPDATE chat_sessions SET status=?, updated_at=? WHERE id=? AND user_id=? AND is_demo=?", (new_status, utc_now(), session_id, user_id, int(is_demo)))
    return get_session(db, session_id, user_id, is_demo)


def delete_session(db: SQLiteStore, session_id: str, user_id: str, is_demo: bool) -> bool:
    if not get_session(db, session_id, user_id, is_demo):
        return False
    db.run("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
    db.run("DELETE FROM chat_sessions WHERE id=? AND user_id=? AND is_demo=?", (session_id, user_id, int(is_demo)))
    return True


def append_message(db: SQLiteStore, session_id: str, sender: str, content: str, agent: str | None, status: str, citations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    now = utc_now()
    message_id = db.new_id("MSG")
    db.run("INSERT INTO chat_messages(id,session_id,sender,content,agent,processing_status,citations_json,created_at) VALUES(?,?,?,?,?,?,?,?)", (message_id, session_id, sender, content, agent, status, json.dumps(citations or []), now))
    db.run("UPDATE chat_sessions SET updated_at=? WHERE id=?", (now, session_id))
    return {"id": message_id, "session_id": session_id, "sender": sender, "content": content, "agent": agent, "processing_status": status, "citations": citations or [], "created_at": now}


def session_messages(db: SQLiteStore, session_id: str) -> list[dict[str, Any]]:
    rows = db.many("SELECT * FROM chat_messages WHERE session_id=? ORDER BY created_at", (session_id,))
    result = []
    for row in rows:
        item = dict(row)
        item["citations"] = json.loads(item.pop("citations_json"))
        result.append(item)
    return result


def put_memory(db: SQLiteStore, astronaut_id: str, namespace: str, content: str, verification_status: str, provenance: dict[str, Any], long_term: bool, is_demo: bool, ttl_hours: int | None = None) -> dict[str, Any]:
    allowed = {"CONFIRMED", "PENDING", "REJECTED", "QUARANTINED", "HISTORICAL", "LIVE"}
    if verification_status not in allowed:
        raise ValueError("unsupported verification status")
    now = utc_now()
    memory_id = db.new_id("MEM")
    expires = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat() if ttl_hours else None
    db.run("INSERT INTO agent_memories(id,astronaut_id,namespace,content,verification_status,provenance_json,expires_at,is_long_term,is_demo,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (memory_id, astronaut_id, namespace, content, verification_status, json.dumps(provenance), expires, int(long_term), int(is_demo), now, now))
    return {"id": memory_id, "astronaut_id": astronaut_id, "namespace": namespace, "content": content, "verification_status": verification_status, "provenance": provenance, "expires_at": expires, "is_long_term": long_term, "is_demo": is_demo, "created_at": now}


def _memory_row(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["provenance"] = json.loads(item.pop("provenance_json"))
    item["is_demo"] = bool(item["is_demo"])
    item["is_long_term"] = bool(item["is_long_term"])
    item["version"] = int(item.get("version", 1))
    return item


def get_memory(db: SQLiteStore, memory_id: str, is_demo: bool) -> dict[str, Any] | None:
    row = db.one("SELECT * FROM agent_memories WHERE id=? AND is_demo=?", (memory_id, int(is_demo)))
    return _memory_row(row) if row else None


def get_memories(db: SQLiteStore, astronaut_id: str, namespace: str, is_demo: bool, verification_status: str | None = None, long_term: bool | None = None, include_expired: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM agent_memories WHERE astronaut_id=? AND namespace=? AND is_demo=?"
    params: list[Any] = [astronaut_id, namespace, int(is_demo)]
    if not include_expired:
        sql += " AND (expires_at IS NULL OR expires_at>?)"
        params.append(utc_now())
    if verification_status is not None:
        if verification_status not in {"CONFIRMED", "PENDING", "REJECTED", "QUARANTINED", "HISTORICAL", "LIVE"}:
            raise ValueError("unsupported verification status")
        sql += " AND verification_status=?"
        params.append(verification_status)
    if long_term is not None:
        sql += " AND is_long_term=?"
        params.append(int(long_term))
    sql += " ORDER BY updated_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return [_memory_row(row) for row in db.many(sql, tuple(params))]


def update_memory(db: SQLiteStore, memory_id: str, is_demo: bool, content: str | None = None, verification_status: str | None = None, long_term: bool | None = None) -> dict[str, Any] | None:
    """Versioned correction. A single atomic UPDATE bumps ``version`` so concurrent
    corrections never silently lose one another."""
    current = get_memory(db, memory_id, is_demo)
    if current is None:
        return None
    if content is None and verification_status is None and long_term is None:
        return current
    fields: list[str] = ["version = version + 1", "updated_at = ?"]
    params: list[Any] = [utc_now()]
    if content is not None:
        fields.append("content = ?")
        params.append(content)
    if verification_status is not None:
        if verification_status not in {"CONFIRMED", "PENDING", "REJECTED", "QUARANTINED", "HISTORICAL", "LIVE"}:
            raise ValueError("unsupported verification status")
        fields.append("verification_status = ?")
        params.append(verification_status)
    if long_term is not None:
        fields.append("is_long_term = ?")
        params.append(int(long_term))
    params.append(memory_id)
    params.append(int(is_demo))
    db.run(f"UPDATE agent_memories SET {', '.join(fields)} WHERE id=? AND is_demo=?", tuple(params))
    return get_memory(db, memory_id, is_demo)


def delete_memory(db: SQLiteStore, memory_id: str, is_demo: bool) -> bool:
    if db.one("SELECT id FROM agent_memories WHERE id=? AND is_demo=?", (memory_id, int(is_demo))) is None:
        return False
    db.run("DELETE FROM agent_memories WHERE id=? AND is_demo=?", (memory_id, int(is_demo)))
    return True
