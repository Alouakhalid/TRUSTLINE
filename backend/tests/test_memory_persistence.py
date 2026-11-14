from fastapi.testclient import TestClient


def test_memory_persists_and_is_scoped_by_astronaut_and_namespace(monkeypatch, tmp_path):
    db_path = tmp_path / "memory.db"
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(db_path))
    from backend.api import app as module
    module.store.configure(str(db_path))
    client = TestClient(module.app)
    assert client.post("/auth/register", json={"username":"astro","password":"a-very-strong-password","role":"ASTRONAUT","astronaut_id":"AST-001"}).status_code == 201
    assert client.post("/auth/register", json={"username":"medic","password":"a-very-strong-password","role":"MEDICAL_OFFICER"}).status_code == 201
    token = client.post("/auth/login", json={"username":"astro","password":"a-very-strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    medic_token = client.post("/auth/login", json={"username":"medic","password":"a-very-strong-password"}).json()["access_token"]
    medic_headers = {"Authorization": f"Bearer {medic_token}"}
    # Governing rule (master prompt 6.2): unverified information must not be
    # promoted into CONFIRMED memory by non-privileged identities. The officer
    # performs the confirmed write; the astronaut later reads it.
    created = client.post("/memory", headers=medic_headers, json={"astronaut_id":"AST-001","namespace":"PHA","content":"confirmed baseline reference","verification_status":"CONFIRMED","provenance":{"source":"test"},"long_term":True})
    assert created.status_code == 201
    # Astronaut cannot write CONFIRMED memory at all...
    assert client.post("/memory", headers=headers, json={"astronaut_id":"AST-001","namespace":"PHA","content":"self-confirm attempt","verification_status":"CONFIRMED"}).status_code == 403
    # ...and never for another astronaut.
    assert client.post("/memory", headers=headers, json={"astronaut_id":"AST-002","namespace":"PHA","content":"must be blocked"}).status_code == 403
    assert client.get("/memory/AST-001/PHA", headers=headers).json()[0]["content"] == "confirmed baseline reference"
    assert client.get("/memory/AST-001/SQA", headers=headers).json() == []

    # Recreate the application client against the same file to model restart recovery.
    module.store.initialize()
    restarted = TestClient(module.app)
    assert restarted.get("/memory/AST-001/PHA", headers=headers).json()[0]["verification_status"] == "CONFIRMED"
