"""Provider transition recording.

When the system changes provider or connectivity state — sync transport
swaps, offline↔online flips, AI routing mode changes — the transition is
recorded as an auditable event. Recording is change-detected: re-recording an
unchanged state inserts nothing, so the log only contains real transitions.
"""
from __future__ import annotations

import json
from typing import Any

from backend.database.store import SQLiteStore, utc_now

KINDS = {"SYNC_TRANSPORT", "CONNECTIVITY", "AI_ROUTING"}


def record(db: SQLiteStore, kind: str, to_state: str, is_demo: bool = False, from_state: str | None = None, reason: str | None = None) -> dict[str, Any] | None:
    """Record a transition to ``to_state`` unless that is already the latest state.

    Returns the recorded transition, or ``None`` when the state did not change.
    """
    if kind not in KINDS:
        raise ValueError(f"unsupported transition kind {kind}")
    latest = get_latest(db, kind, is_demo)
    if latest is not None and latest["to_state"] == to_state:
        return None
    transition_id = db.new_id("TRA")
    db.run(
        "INSERT INTO provider_transitions(id,kind,from_state,to_state,reason,created_at,is_demo) VALUES(?,?,?,?,?,?,?)",
        (transition_id, kind, from_state or (latest["to_state"] if latest else None), to_state, reason, utc_now(), int(is_demo)),
    )
    return {"id": transition_id, "kind": kind, "from_state": from_state or (latest["to_state"] if latest else None), "to_state": to_state, "reason": reason, "created_at": utc_now(), "is_demo": is_demo}


def get_latest(db: SQLiteStore, kind: str, is_demo: bool = False) -> dict[str, Any] | None:
    row = db.one(
        "SELECT * FROM provider_transitions WHERE kind=? AND is_demo=? ORDER BY created_at DESC, id DESC LIMIT 1",
        (kind, int(is_demo)),
    )
    if row is None:
        return None
    return _row(row)


def list_transitions(db: SQLiteStore, kind: str | None = None, is_demo: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    if kind is not None and kind not in KINDS:
        raise ValueError(f"unsupported transition kind {kind}")
    sql = "SELECT * FROM provider_transitions WHERE is_demo=?"
    params: list[Any] = [int(is_demo)]
    if kind is not None:
        sql += " AND kind=?"
        params.append(kind)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    return [_row(row) for row in db.many(sql, tuple(params))]


def record_connectivity_change(db: SQLiteStore, snapshot: dict[str, Any], is_demo: bool = False) -> dict[str, Any] | None:
    """Record OFFLINE↔ONLINE (or DEGRADED) flips from a connectivity snapshot.

    Local-first rule: the local database is not a link (it works during a
    blackout). OFFLINE means no configured external monitor reports OK;
    ONLINE means every connectivity-class monitor is OK or explicitly
    NOT_CONFIGURED; anything between is DEGRADED.
    """
    connectivity_monitors = ("database", "dns", "network", "ground_link", "cloud_ai", "local_ai")
    reachable = [name for name in connectivity_monitors if snapshot.get(name, {}).get("status") == "OK"]
    external_configured = [
        name for name in ("dns", "network", "ground_link", "cloud_ai", "local_ai")
        if snapshot.get(name, {}).get("status") not in {None, "NOT_CONFIGURED"}
    ]
    if not any(snapshot.get(name, {}).get("status") == "OK" for name in external_configured):
        state = "OFFLINE"
    elif all(snapshot.get(name, {}).get("status") in {"OK", "NOT_CONFIGURED"} for name in connectivity_monitors):
        state = "ONLINE"
    else:
        state = "DEGRADED"
    return record(db, "CONNECTIVITY", state, is_demo=is_demo, reason=json.dumps({"reachable": reachable}))


def _row(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["is_demo"] = bool(item["is_demo"])
    return item
