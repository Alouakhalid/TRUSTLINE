"""Telemetry ingestion integrity, isolation, and WebSocket subscription tests."""
import json

from fastapi.testclient import TestClient


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "telemetry.db"))
    from backend.api import app as module
    module.store.configure(str(tmp_path / "telemetry.db"))
    client = TestClient(module.app)
    users = {}
    for username, role, astro in (("astro", "ASTRONAUT", "AST-001"), ("medic", "MEDICAL_OFFICER", None)):
        payload = {"username": username, "password": "a-very-strong-password", "role": role}
        if astro:
            payload["astronaut_id"] = astro
        client.post("/auth/register", json=payload)
        users[role] = client.post("/auth/login", json={"username": username, "password": "a-very-strong-password"}).json()["access_token"]
    return module, client, users


def _packet(packet_id, seq, ts, astro="AST-001", sensor="ECG", channels=None):
    channels = channels if channels is not None else [[0.1, 0.2, 0.3]]
    from backend.services.telemetry import compute_crc32
    return {
        "packet_id": packet_id, "sequence_number": seq, "astronaut_id": astro,
        "session_id": "SESSION-T1", "timestamp_epoch_ms": ts, "sensor_type": sensor,
        "sample_rate_hz": 250.0, "channels_data": channels,
        "checksum_crc32": compute_crc32(sensor, seq, ts, channels),
    }


def test_ingest_verifies_checksum_and_rejects_corruption(monkeypatch, tmp_path):
    module, client, users = _setup(monkeypatch, tmp_path)
    headers = {"Authorization": f"Bearer {users['ASTRONAUT']}"}
    good = _packet("PKT-1", 0, 1000)
    response = client.post("/telemetry/packets", headers=headers, json={"astronaut_id": "AST-001", "packets": [good]})
    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] == 1 and body["checksum_failures"] == 0
    assert body["results"][0]["checksum_ok"] is True

    corrupted = _packet("PKT-2", 1, 2000)
    corrupted["checksum_crc32"] = 12345  # tampered frame
    response = client.post("/telemetry/packets", headers=headers, json={"astronaut_id": "AST-001", "packets": [corrupted]})
    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] == 1 and body["checksum_failures"] == 1  # stored but flagged, timestamps preserved
    latest = client.get("/telemetry/latest/AST-001", params={"sensor_type": "ECG"}, headers=headers).json()
    assert latest[0]["checksum_ok"] is False and latest[0]["timestamp_epoch_ms"] == 2000


def test_duplicates_gaps_and_out_of_order_are_flagged(monkeypatch, tmp_path):
    module, client, users = _setup(monkeypatch, tmp_path)
    headers = {"Authorization": f"Bearer {users['ASTRONAUT']}"}
    client.post("/telemetry/packets", headers=headers, json={"astronaut_id": "AST-001", "packets": [_packet("PKT-1", 0, 1000)]})
    dup = client.post("/telemetry/packets", headers=headers, json={"astronaut_id": "AST-001", "packets": [_packet("PKT-1", 0, 1000)]}).json()
    assert dup["duplicates"] == 1 and dup["accepted"] == 0
    gap = client.post("/telemetry/packets", headers=headers, json={"astronaut_id": "AST-001", "packets": [_packet("PKT-9", 5, 5000)]}).json()
    assert gap["gaps"] == 1 and gap["results"][0]["state"] == "GAP"
    stale = client.post("/telemetry/packets", headers=headers, json={"astronaut_id": "AST-001", "packets": [_packet("PKT-3", 2, 3000)]}).json()
    assert stale["out_of_order"] == 1 and stale["results"][0]["state"] == "OUT_OF_ORDER"
    listing = client.get("/telemetry/history/AST-001", headers=headers).json()
    assert len(listing) == 3  # out-of-order frames are preserved, not discarded


def test_astronaut_isolation_for_ingest_and_reads(monkeypatch, tmp_path):
    module, client, users = _setup(monkeypatch, tmp_path)
    astro = {"Authorization": f"Bearer {users['ASTRONAUT']}"}
    medic = {"Authorization": f"Bearer {users['MEDICAL_OFFICER']}"}
    assert client.post("/telemetry/packets", headers=astro, json={"astronaut_id": "AST-002", "packets": [_packet("PKT-X", 0, 1000, astro="AST-002")]}).status_code == 403
    client.post("/telemetry/packets", headers=medic, json={"astronaut_id": "AST-002", "packets": [_packet("PKT-X", 0, 1000, astro="AST-002")]})
    assert client.get("/telemetry/latest/AST-002", headers=astro).status_code == 403
    assert client.get("/telemetry/history/AST-002", headers=astro).status_code == 403
    assert client.get("/telemetry/latest/AST-002", headers=medic).status_code == 200  # privileged cross-astro review
    bogus = client.get("/telemetry/latest/AST-001", params={"sensor_type": "TELEPATHY"}, headers=astro)
    assert bogus.status_code == 400


def test_demo_telemetry_is_isolated(monkeypatch, tmp_path):
    module, client, users = _setup(monkeypatch, tmp_path)
    astro = {"Authorization": f"Bearer {users['ASTRONAUT']}"}
    demo = {**astro, "X-Trustline-Mode": "demo"}
    client.post("/telemetry/packets", headers=demo, json={"astronaut_id": "AST-001", "packets": [_packet("PKT-DEMO", 0, 1000)]})
    assert client.get("/telemetry/latest/AST-001", headers=astro).json() == []
    demo_latest = client.get("/telemetry/latest/AST-001", headers=demo).json()
    assert demo_latest[0]["packet_id"] == "PKT-DEMO" and demo_latest[0]["is_demo"] is True


def test_websocket_subscription_broadcast_and_auth(monkeypatch, tmp_path):
    module, client, users = _setup(monkeypatch, tmp_path)
    astro_token = users["ASTRONAUT"]
    with client.websocket_connect(f"/ws/telemetry/AST-001?token={astro_token}") as ws:
        ws.send_text("ping")
        assert json.loads(ws.receive_text()) == {"type": "pong"}
        command = {"command": "ingest", "packets": [_packet("PKT-WS-1", 0, 1000)]}
        ws.send_text(json.dumps(command))
        report = json.loads(ws.receive_text())
        assert report["type"] == "ingest_report" and report["accepted"] == 1
        broadcast = json.loads(ws.receive_text())
        assert broadcast["type"] == "telemetry_packet"
        assert broadcast["packet_id"] == "PKT-WS-1" and broadcast["sequence_state"] == "OK"
        assert broadcast["channels_data"] == [[0.1, 0.2, 0.3]]

    # no token -> rejected
    with __import__("pytest").raises(Exception):
        with client.websocket_connect("/ws/telemetry/AST-001"):
            pass
    # astronaut cannot subscribe to another astronaut's feed
    with __import__("pytest").raises(Exception):
        with client.websocket_connect(f"/ws/telemetry/AST-002?token={astro_token}"):
            pass
    # garbage frame gets an explicit error, not a silent close
    with client.websocket_connect(f"/ws/telemetry/AST-001?token={astro_token}") as ws:
        ws.send_text("not-json")
        assert json.loads(ws.receive_text())["type"] == "error"
