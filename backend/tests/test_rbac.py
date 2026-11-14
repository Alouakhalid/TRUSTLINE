"""RBAC acceptance tests: three roles, explicit deny-by-default admin boundary."""
from fastapi.testclient import TestClient


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "rbac.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "rbac.db"))
    client = TestClient(module.app)
    tokens = {}
    for username, role, astro in (
        ("astro", "ASTRONAUT", "AST-001"),
        ("medic", "MEDICAL_OFFICER", None),
        ("chief", "ADMINISTRATOR", None),
    ):
        payload = {"username": username, "password": "a-very-strong-password", "role": role}
        if astro:
            payload["astronaut_id"] = astro
        assert client.post("/auth/register", json=payload).status_code == 201
        tokens[role] = client.post("/auth/login", json={"username": username, "password": "a-very-strong-password"}).json()["access_token"]
    return module, client, tokens


def test_admin_routes_are_deny_by_default(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    assert client.get("/admin/users").status_code == 401  # unauthenticated
    assert client.get("/admin/users", headers={"Authorization": f"Bearer {tokens['ASTRONAUT']}"}).status_code == 403
    assert client.get("/admin/users", headers={"Authorization": f"Bearer {tokens['MEDICAL_OFFICER']}"}).status_code == 403
    response = client.get("/admin/users", headers={"Authorization": f"Bearer {tokens['ADMINISTRATOR']}"})
    assert response.status_code == 200
    users = response.json()
    assert {u["role"] for u in users} == {"ASTRONAUT", "MEDICAL_OFFICER", "ADMINISTRATOR"}
    assert all("password_hash" not in u for u in users)  # secrets never exposed


def test_role_filter_and_audit_are_admin_only(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    admin = {"Authorization": f"Bearer {tokens['ADMINISTRATOR']}"}
    astro = {"Authorization": f"Bearer {tokens['ASTRONAUT']}"}
    assert client.get("/admin/users", params={"role": "ASTRONAUT"}, headers=admin).json()[0]["username"] == "astro"
    assert client.get("/admin/users", params={"role": "PILOT"}, headers=admin).status_code == 422
    assert client.get("/admin/audit", headers=astro).status_code == 403
    events = client.get("/admin/audit", headers=admin).json()
    assert any(event["action"] == "LOGIN" for event in events)
    assert all(isinstance(event["metadata"], dict) for event in events)


def test_medical_officer_has_no_admin_power_but_is_privileged_for_memory(monkeypatch, tmp_path):
    module, client, tokens = _setup(monkeypatch, tmp_path)
    medic = {"Authorization": f"Bearer {tokens['MEDICAL_OFFICER']}"}
    assert client.get("/admin/users", headers=medic).status_code == 403
    # Privileged memory authority: officer may confirm memory for any astronaut.
    response = client.post("/memory", headers=medic, json={
        "astronaut_id": "AST-001", "namespace": "PHA",
        "content": "Confirmed finding", "verification_status": "CONFIRMED",
        "provenance": {"source": "OFFICER_REVIEW"},
        "long_term": True,
    })
    assert response.status_code == 201
