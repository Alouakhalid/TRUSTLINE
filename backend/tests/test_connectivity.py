"""Connectivity monitors: independent states, injected failures, no host-network writes."""
from backend.services import connectivity


def _hermetic(**overrides):
    """Inject every real-network probe so tests never touch the host network."""
    probes = {
        "dns_probe": lambda: None,
        "network_probe": lambda: None,
        "local_probe": lambda: None,
        "cloud_probe": lambda: None,
    }
    probes.update(overrides)
    return probes


def test_database_monitor_reports_ok_and_failure(monkeypatch, tmp_path):
    from backend.api import app as module
    module.store.configure(str(tmp_path / "conn.db"))
    snapshot = connectivity.probe(**_hermetic())
    assert snapshot["database"]["status"] == "OK"
    assert snapshot["dns"]["status"] == "OK" and snapshot["network"]["status"] == "OK" and snapshot["local_ai"]["status"] == "OK"
    assert snapshot["cloud_ai"]["status"] == "OK"  # injected reachable
    assert snapshot["ground_link"]["status"] == "NOT_CONFIGURED"  # truthful third state
    assert snapshot["sync"]["status"] == "OK" and snapshot["ws"]["status"] == "OK"
    assert snapshot["summary"]["offline"] is False

    def broken_db() -> None:
        raise RuntimeError("probe returned no row")

    degraded = connectivity.probe(database_probe=broken_db, **_hermetic())
    assert degraded["database"]["status"] == "UNREACHABLE"
    assert degraded["database"]["error_type"] == "RuntimeError"
    assert "probe returned no row" not in str(degraded)  # exception message never leaked, only the type


def test_dns_failure_is_distinct_from_network_failure():
    def dns_down() -> None:
        raise OSError("resolution failed")

    def network_up() -> None:
        return None

    snapshot = connectivity.probe(
        dns_probe=dns_down,
        network_probe=network_up,
        local_probe=lambda: None,
        cloud_probe=lambda: None,
        database_probe=lambda: None,
    )
    assert snapshot["dns"]["status"] == "UNREACHABLE"
    assert snapshot["dns"]["error_type"] == "OSError"
    assert snapshot["network"]["status"] == "OK"  # independent judgment
    assert "dns" not in snapshot["summary"]["reachable"]
    assert set(snapshot["summary"]["reachable"]) == {"network", "cloud_ai", "local_ai", "database"}


def test_network_failure_is_distinct_from_dns_success():
    def dns_up() -> None:
        return None

    def network_down() -> None:
        raise OSError("connection refused")

    snapshot = connectivity.probe(dns_probe=dns_up, network_probe=network_down, local_probe=lambda: None, cloud_probe=lambda: None, database_probe=lambda: None)
    assert snapshot["dns"]["status"] == "OK"
    assert snapshot["network"]["status"] == "UNREACHABLE"


def test_service_monitors_never_fake_a_link(monkeypatch, tmp_path):
    from backend.api import app as module
    module.store.configure(str(tmp_path / "conn_svc.db"))
    # All real links down, but the internal services are healthy.
    snapshot = connectivity.probe(
        dns_probe=lambda: (_ for _ in ()).throw(OSError("down")),
        network_probe=lambda: (_ for _ in ()).throw(OSError("down")),
        local_probe=lambda: (_ for _ in ()).throw(OSError("down")),
        cloud_probe=lambda: (_ for _ in ()).throw(OSError("down")),
        database_probe=lambda: None,
    )
    assert snapshot["sync"]["status"] == "OK" and snapshot["ws"]["status"] == "OK"
    assert snapshot["summary"]["offline"] is True  # service health never counts as connectivity


def test_sync_monitor_degrades_on_dead_letter(monkeypatch, tmp_path):
    from backend.api import app as module
    module.store.configure(str(tmp_path / "conn_dead.db"))
    module.store.run(
        "INSERT INTO sync_events(id,event_type,payload_json,status,attempts,next_attempt_at,is_demo,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        ("EVT-DEAD", "TEST", "{}", "DEAD_LETTER", 5, "2026-01-01T00:00:00+00:00", 0, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
    )
    snapshot = connectivity.probe(**_hermetic())
    assert snapshot["sync"]["status"] == "DEGRADED"
    assert snapshot["sync"]["dead_letter"] == 1
    demo_snapshot = connectivity.probe(is_demo=True, **_hermetic())
    assert demo_snapshot["sync"]["dead_letter"] == 0  # partition-aware


def test_admin_connectivity_endpoint_records_state_transitions(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "conn_admin.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "conn_admin.db"))
    client = TestClient(module.app)
    client.post("/auth/register", json={"username": "chief", "password": "a-very-strong-password", "role": "ADMINISTRATOR"})
    token = client.post("/auth/login", json={"username": "chief", "password": "a-very-strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    def fake_probe(**kwargs) -> dict:
        return {
            "checked_at": "2026-11-14T00:00:00+00:00",
            "database": {"status": "OK", "latency_ms": 0.4},
            "dns": {"status": "UNREACHABLE", "error_type": "OSError", "latency_ms": 12.0},
            "network": {"status": "OK", "latency_ms": 30.1},
            "local_ai": {"status": "UNREACHABLE", "error_type": "URLError", "latency_ms": 1500.2},
            "sync": {"status": "OK", "pending": 0, "dead_letter": 0},
            "ws": {"status": "OK", "subscribers": 0},
            "summary": {"reachable": ["database", "network"], "offline": False},
        }

    monkeypatch.setattr(module.connectivity, "probe", fake_probe)
    response = client.get("/admin/connectivity", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["dns"]["status"] == "UNREACHABLE" and body["network"]["status"] == "OK"
    assert body["dns"]["status"] != body["network"]["status"]  # never conflated
    assert body["state_transition_recorded"] is True
    assert body["connectivity_state"] == "DEGRADED"
    # Second identical snapshot records nothing (change-detected).
    second = client.get("/admin/connectivity", headers=headers).json()
    assert second["state_transition_recorded"] is False
    # Transitions are inspectable, admin-only, and partition-aware.
    listed = client.get("/admin/transitions", params={"kind": "CONNECTIVITY"}, headers=headers).json()
    assert len(listed) == 1 and listed[0]["to_state"] == "DEGRADED"
    assert client.get("/admin/connectivity").status_code == 401
    assert client.get("/admin/transitions").status_code == 401
