"""Sync API exposure: admin-only access, claim/success/failure/resolve semantics."""
from fastapi.testclient import TestClient


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "sync.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "sync.db"))
    client = TestClient(module.app)
    for username, role in (("chief", "ADMINISTRATOR"), ("astro", "ASTRONAUT")):
        payload = {"username": username, "password": "a-very-strong-password", "role": role}
        if role == "ASTRONAUT":
            payload["astronaut_id"] = "AST-001"
        client.post("/auth/register", json=payload)
    tokens = {u: client.post("/auth/login", json={"username": u, "password": "a-very-strong-password"}).json()["access_token"] for u in ("chief", "astro")}
    # seed two sync events directly through the durable queue
    module.sync.enqueue("EVT-1", "TELEMETRY_BATCH", {"points": 120})
    module.sync.enqueue("EVT-2", "MEMORY_SYNC", {"memory": "MEM-1"})
    return module, client, tokens


def test_sync_status_is_admin_only(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    astro = {"Authorization": f"Bearer {tokens['astro']}"}
    admin = {"Authorization": f"Bearer {tokens['chief']}"}
    assert client.get("/admin/sync/status", headers=astro).status_code == 403
    status = client.get("/admin/sync/status", headers=admin).json()
    assert status["counts"] == {"PENDING": 2} and status["is_demo"] is False


def test_claim_mark_success_and_failure_flow(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    admin = {"Authorization": f"Bearer {tokens['chief']}"}
    claimed = client.post("/admin/sync/claim", json={"limit": 10}, headers=admin).json()
    assert [e["id"] for e in claimed] == ["EVT-1", "EVT-2"]
    assert client.post("/admin/sync/EVT-1/success", headers=admin).json()["status"] == "SYNCED"
    failure = client.post("/admin/sync/EVT-2/failure", json={"reason": "ground timeout"}, headers=admin).json()
    assert failure["attempts"] == 1 and failure["status"] == "PENDING"
    status = client.get("/admin/sync/status", headers=admin).json()["counts"]
    assert status == {"PENDING": 1, "SYNCED": 1}
    events = client.get("/admin/sync/events", params={"status_filter": "PENDING"}, headers=admin).json()
    assert events[0]["payload"] == {"memory": "MEM-1"}
    assert client.post("/admin/sync/UNKNOWN/success", headers=admin).status_code == 404


def test_conflict_resolution_never_silently_overwrites(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    admin = {"Authorization": f"Bearer {tokens['chief']}"}
    conflict = client.post("/admin/sync/EVT-1/resolve", params={"local_version": 2, "ground_version": 5}, headers=admin)
    assert conflict.status_code == 409 and "version conflict" in conflict.json()["detail"]
    resolved = client.post("/admin/sync/EVT-1/resolve", params={"local_version": 3, "ground_version": 3}, headers=admin)
    assert resolved.status_code == 200 and resolved.json()["status"] == "SYNCED"
