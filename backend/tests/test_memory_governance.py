"""Memory governance: versioned corrections, deletion, filtering, audit, concurrency."""
import concurrent.futures

from fastapi.testclient import TestClient


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "mem.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "mem.db"))
    client = TestClient(module.app)
    assert client.post("/auth/register", json={"username": "astro", "password": "a-very-strong-password", "role": "ASTRONAUT", "astronaut_id": "AST-001"}).status_code == 201
    assert client.post("/auth/register", json={"username": "medic", "password": "a-very-strong-password", "role": "MEDICAL_OFFICER"}).status_code == 201
    assert client.post("/auth/register", json={"username": "astro2", "password": "a-very-strong-password", "role": "ASTRONAUT", "astronaut_id": "AST-002"}).status_code == 201
    tokens = {}
    for username in ("astro", "medic", "astro2"):
        tokens[username] = client.post("/auth/login", json={"username": username, "password": "a-very-strong-password"}).json()["access_token"]
    return module, client, tokens


def _astro_mem(client, token, content="baseline HR 72 bpm", status="PENDING", astro="AST-001", ns="PHA", long_term=False):
    return client.post("/memory", headers={"Authorization": f"Bearer {token}"}, json={
        "astronaut_id": astro, "namespace": ns, "content": content,
        "verification_status": status, "provenance": {"agent": "PHA"}, "long_term": long_term,
    })


def test_update_bumps_version_and_records_audit(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    memory = _astro_mem(client, tokens["astro"]).json()
    patched = client.patch(f"/memory/{memory['id']}", headers={"Authorization": f"Bearer {tokens['astro']}"}, json={"content": "corrected after SQA review"})
    assert patched.status_code == 200
    body = patched.json()
    assert body["version"] == 2 and body["content"] == "corrected after SQA review"
    assert body["updated_at"] >= body["created_at"]
    # audit history exists for the correction
    audit = client.get("/admin/audit", headers={"Authorization": f"Bearer {tokens['astro']}"})
    assert audit.status_code == 403  # astronaut cannot read the audit log
    # empty patch is a truthful no-op and must not bump the version
    noop = client.patch(f"/memory/{memory['id']}", headers={"Authorization": f"Bearer {tokens['astro']}"}, json={})
    assert noop.status_code == 200 and noop.json()["version"] == 2


def test_confirmed_memory_requires_privileged_role(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    memory = _astro_mem(client, tokens["astro"], status="PENDING").json()
    astro_headers = {"Authorization": f"Bearer {tokens['astro']}"}
    medic_headers = {"Authorization": f"Bearer {tokens['medic']}"}
    # astronaut cannot self-confirm
    assert client.patch(f"/memory/{memory['id']}", headers=astro_headers, json={"verification_status": "CONFIRMED"}).status_code == 403
    # astronaut cannot create CONFIRMED memory directly either
    assert _astro_mem(client, tokens["astro"], content="self-confirmed", status="CONFIRMED").status_code == 403
    # officer confirms it, then astronaut cannot edit or delete the confirmed record
    assert client.patch(f"/memory/{memory['id']}", headers=medic_headers, json={"verification_status": "CONFIRMED"}).status_code == 200
    assert client.patch(f"/memory/{memory['id']}", headers=astro_headers, json={"content": "tamper"}).status_code == 403
    assert client.delete(f"/memory/{memory['id']}", headers=astro_headers).status_code == 403
    # officer may still correct and delete
    assert client.patch(f"/memory/{memory['id']}", headers=medic_headers, json={"content": "officer correction"}).status_code == 200
    assert client.delete(f"/memory/{memory['id']}", headers=medic_headers).status_code == 204


def test_filtering_by_status_and_long_term(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    token = tokens["astro"]
    _astro_mem(client, token, content="live obs", status="LIVE")
    _astro_mem(client, token, content="long term fact", status="PENDING").json()
    confirmed = _astro_mem(client, tokens["medic"], content="confirmed fact", status="CONFIRMED", long_term=False).json()
    client.patch(f"/memory/{confirmed['id']}", headers={"Authorization": f"Bearer {tokens['medic']}"}, json={"long_term": True})
    headers = {"Authorization": f"Bearer {token}"}
    live = client.get("/memory/AST-001/PHA", params={"verification_status": "LIVE"}, headers=headers).json()
    assert len(live) == 1 and live[0]["content"] == "live obs"
    longs = client.get("/memory/AST-001/PHA", params={"long_term": True}, headers=headers).json()
    assert len(longs) == 1 and longs[0]["content"] == "confirmed fact"
    assert client.get("/memory/AST-001/PHA", params={"verification_status": "BOGUS"}, headers=headers).status_code == 400


def test_delete_and_unknown_memory(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    headers = {"Authorization": f"Bearer {tokens['astro']}"}
    memory = _astro_mem(client, tokens["astro"]).json()
    assert client.delete(f"/memory/{memory['id']}", headers=headers).status_code == 204
    assert client.get("/memory/AST-001/PHA", headers=headers).json() == []
    assert client.patch(f"/memory/{memory['id']}", headers=headers, json={"content": "ghost"}).status_code == 404
    assert client.delete(f"/memory/{memory['id']}", headers=headers).status_code == 404


def test_cross_astronaut_write_and_patch_are_blocked(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    astro_headers = {"Authorization": f"Bearer {tokens['astro']}"}
    assert _astro_mem(client, tokens["astro"], astro="AST-002").status_code == 403
    other = _astro_mem(client, tokens["medic"], astro="AST-002").json()
    assert client.patch(f"/memory/{other['id']}", headers=astro_headers, json={"content": "cross-write"}).status_code == 403


def test_concurrent_updates_never_lose_a_version(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    memory = _astro_mem(client, tokens["astro"]).json()
    from backend.services import mission_services

    def correct(index: int) -> None:
        mission_services.update_memory(module.store, memory["id"], False, content=f"correction {index}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(correct, range(10)))
    final = mission_services.get_memory(module.store, memory["id"], False)
    assert final["version"] == 11  # 1 initial + 10 atomic corrections
