"""Audit event recording shared by the mission API and mounted routers."""
from __future__ import annotations

import json
from typing import Any

from backend.database.store import store, utc_now


def record(actor: dict[str, Any], action: str, resource_type: str, resource_id: str | None, is_demo: bool, metadata: dict[str, Any] | None = None) -> None:
    payload = {"role": actor.get("role")}
    if metadata:
        payload.update(metadata)
    store.run(
        "INSERT INTO audit_events(id,actor_user_id,action,resource_type,resource_id,metadata_json,is_demo,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (store.new_id("AUD"), actor.get("sub"), action, resource_type, resource_id, json.dumps(payload), int(is_demo), utc_now()),
    )
