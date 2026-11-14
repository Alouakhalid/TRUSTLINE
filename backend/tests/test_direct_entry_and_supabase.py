"""Tests for zero-friction Direct Entry, Mission Role Token Switching, and Supabase health reporting."""
import pytest
from fastapi.testclient import TestClient

from backend.api import app as module


@pytest.fixture
def api_client(tmp_path):
    module.store.configure(str(tmp_path / "test_auth.db"))
    return TestClient(module.app)


def test_direct_entry_auto_provisions_astronaut(api_client):
    """Zero-friction direct entry: astronaut session is created and issued without passwords."""
    res = api_client.post("/auth/direct-entry", json={})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    user = data["user"]
    assert user["role"] == "ASTRONAUT"
    # Invariant: Never default unknown to AST-001
    assert user["astronaut_id"] == "AST-002"
    assert user["username"] == "crew_ast-002"

    # Token can immediately access protected astronaut endpoints
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me = api_client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "ASTRONAUT"


def test_role_switcher_tokens_and_rbac(api_client):
    """Mission role switcher issues signed tokens for all 3 roles with correct server-side permissions."""
    # 1. Switch to Medical Officer
    res_doc = api_client.post("/auth/role-token", json={"target_role": "MEDICAL_OFFICER"})
    assert res_doc.status_code == 200
    doc_data = res_doc.json()
    doc_token = doc_data["access_token"]
    assert doc_data["user"]["role"] == "MEDICAL_OFFICER"

    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    # Medical Officer can list memories
    mem_res = api_client.get("/memory/AST-002/PHA", headers=doc_headers)
    assert mem_res.status_code == 200

    # 2. Switch to Administrator
    res_adm = api_client.post("/auth/role-token", json={"target_role": "ADMINISTRATOR"})
    assert res_adm.status_code == 200
    adm_data = res_adm.json()
    adm_token = adm_data["access_token"]
    assert adm_data["user"]["role"] == "ADMINISTRATOR"

    adm_headers = {"Authorization": f"Bearer {adm_token}"}
    # Administrator can access admin connectivity probe
    conn_res = api_client.get("/admin/connectivity", headers=adm_headers)
    assert conn_res.status_code == 200

    # 3. Direct Entry Astronaut cannot access admin connectivity (RBAC enforced)
    res_astro = api_client.post("/auth/direct-entry", json={})
    astro_headers = {"Authorization": f"Bearer {res_astro.json()['access_token']}"}
    bad_res = api_client.get("/admin/connectivity", headers=astro_headers)
    assert bad_res.status_code == 403


def test_supabase_truthful_status_endpoint(api_client):
    """Supabase status endpoint truthfully reports configuration status."""
    res = api_client.get("/supabase/status")
    assert res.status_code == 200
    status = res.json()
    assert "status" in status
    assert "configured" in status
    assert status["status"] in ("UNCONFIGURED", "HEALTHY", "ERROR", "MIGRATION_REQUIRED")
