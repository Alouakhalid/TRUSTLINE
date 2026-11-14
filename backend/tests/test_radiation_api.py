"""Environmental radiation gateway: separate store, NASA limits, RBAC, demo isolation."""
from fastapi.testclient import TestClient


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "rad.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "rad.db"))
    client = TestClient(module.app)
    users = {}
    for username, role, astro in (("astro", "ASTRONAUT", "AST-001"), ("medic", "MEDICAL_OFFICER", None)):
        payload = {"username": username, "password": "a-very-strong-password", "role": role}
        if astro:
            payload["astronaut_id"] = astro
        client.post("/auth/register", json=payload)
        users[role] = client.post("/auth/login", json={"username": username, "password": "a-very-strong-password"}).json()["access_token"]
    return module, client, users


def _packet(packet_id, dose=22.0, ts=1000, alert="NOMINAL", cumulative=1.5):
    return {
        "packet_id": packet_id, "timestamp_epoch_ms": ts,
        "dose_rate_microgy_h": dose, "equivalent_dose_rate_msv_h": dose / 100.0,
        "cumulative_mission_dose_msv": cumulative, "spe_active": False,
        "spe_flux_pfu": 0.0, "shielding_thickness_g_cm2": 10.0, "alert_level": alert,
    }


def test_limits_endpoint_matches_nasa_std(monkeypatch, tmp_path):
    module, client, users = _setup(monkeypatch, tmp_path)
    astro = {"Authorization": f"Bearer {users['ASTRONAUT']}"}
    limits = client.get("/radiation/limits", headers=astro).json()
    assert limits["spe_acute_action_threshold_microgy_h"] == 500.0
    assert limits["blood_forming_organs_30d_msv"] == 250.0
    assert "NASA-STD-3001" in limits["standard"]


def test_ingest_requires_privileged_role_and_stores_verbatim(monkeypatch, tmp_path):
    module, client, users = _setup(monkeypatch, tmp_path)
    astro = {"Authorization": f"Bearer {users['ASTRONAUT']}"}
    medic = {"Authorization": f"Bearer {users['MEDICAL_OFFICER']}"}
    assert client.post("/radiation/packets", headers=astro, json=_packet("RAD-1")).status_code == 403
    response = client.post("/radiation/packets", headers=medic, json=_packet("RAD-1"))
    assert response.status_code == 201 and response.json()["stored"] is True
    # exact duplicate -> reported, never silently overwritten
    duplicate = client.post("/radiation/packets", headers=medic, json=_packet("RAD-1")).json()
    assert duplicate["duplicate"] is True and duplicate["stored"] is False
    # alerts and values preserved
    client.post("/radiation/packets", headers=medic, json=_packet("RAD-2", dose=600.0, ts=2000, alert="WARNING", cumulative=2.5))
    latest = client.get("/radiation/latest", headers=astro).json()
    assert latest["packet"]["packet_id"] == "RAD-2"
    assert latest["packet"]["alert_level"] == "WARNING"
    assert latest["packet"]["dose_rate_microgy_h"] == 600.0
    assert latest["limits"]["spe_acute_action_threshold_microgy_h"] == 500.0
    history = client.get("/radiation/history", headers=astro).json()
    assert {p["packet_id"] for p in history} == {"RAD-1", "RAD-2"}


def test_invalid_packets_rejected(monkeypatch, tmp_path):
    module, client, users = _setup(monkeypatch, tmp_path)
    medic = {"Authorization": f"Bearer {users['MEDICAL_OFFICER']}"}
    negative = _packet("RAD-BAD", dose=-5.0)
    assert client.post("/radiation/packets", headers=medic, json=negative).status_code == 422
    bad_alert = _packet("RAD-BAD2", alert="CATACLYSM")
    assert client.post("/radiation/packets", headers=medic, json=bad_alert).status_code in {422}  # literal-validated


def test_demo_radiation_is_isolated(monkeypatch, tmp_path):
    module, client, users = _setup(monkeypatch, tmp_path)
    medic = {"Authorization": f"Bearer {users['MEDICAL_OFFICER']}"}
    demo = {**medic, "X-Trustline-Mode": "demo"}
    client.post("/radiation/packets", headers=demo, json=_packet("RAD-DEMO", dose=999.0))
    operational = client.get("/radiation/latest", headers=medic).json()
    assert operational["packet"] is None  # demo never leaks into operational view
    demo_latest = client.get("/radiation/latest", headers=demo).json()
    assert demo_latest["packet"]["packet_id"] == "RAD-DEMO" and demo_latest["packet"]["is_demo"] is True
