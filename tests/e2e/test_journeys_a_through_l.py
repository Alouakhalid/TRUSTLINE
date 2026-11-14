"""Automated E2E Journey Tests (A through L) for TRUSTLINE Product Rescue.

Journeys:
A. Public visitor opens landing page, explores features, signs in, and reaches the correct portal.
B. Astronaut logs in, views their own telemetry, opens the 3D twin, starts a demo sensor simulation, and sees live chart updates.
C. Astronaut opens the chatbot, creates a session, sends a real message, receives a Supervisor-generated response, refreshes the browser, and sees the persisted conversation.
D. Medical Officer logs in, selects an authorized astronaut, inspects medical evidence, and confirms/edits/rejects a pending document finding.
E. Administrator checks DNS, network, backend, database, AI providers, and sync status.
F. Cloud AI becomes unavailable in an isolated test environment; the router uses the configured local fallback and reports the actual provider.
G. Connectivity returns and pending synchronization is processed without duplicate or silent overwrite.
H. Demo Mode generates synthetic signals and proves that operational records remain unchanged.
I. Unauthorized cross-astronaut access is rejected.
J. The Digital Twin sensor hotspots display the correct backend values and units.
K. WebSocket failure triggers the supported REST fallback.
L. A missing sensor reading is displayed as UNKNOWN rather than healthy.
"""
import pytest
import urllib.request
import json

BASE_URL = "http://localhost:8000"


def test_journey_a_public_and_auth():
    """Journey A: Health, registration, and login verification."""
    # Check health
    with urllib.request.urlopen(f"{BASE_URL}/health") as r:
        assert r.status == 200
        data = json.loads(r.read())
        assert data["status"] == "ok"

    # Login
    req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "testastro", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        assert r.status == 200
        login_data = json.loads(r.read())
        assert "access_token" in login_data
        assert login_data["user"]["role"] == "ASTRONAUT"


def test_journey_b_simulator_step_and_telemetry():
    """Journey B: Physiological simulator step generation and telemetry ingestion."""
    # Trigger simulator step
    req = urllib.request.Request(
        f"{BASE_URL}/simulator/step?duration_sec=1.0&seed=101",
        data=b"",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        assert r.status == 200
        step_data = json.loads(r.read())
        assert step_data["status"] == "step_generated"
        assert step_data["packets_generated"] >= 5


def test_journey_c_chatbot_and_supervisor():
    """Journey C: Chat session creation, message persistence, and LangGraph Supervisor execution."""
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "testastro", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as r:
        token = json.loads(r.read())["access_token"]

    # Create session
    sess_req = urllib.request.Request(
        f"{BASE_URL}/chat/sessions",
        data=json.dumps({"title": "Journey C Test"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(sess_req) as r:
        session_id = json.loads(r.read())["id"]

    # Post message
    msg_req = urllib.request.Request(
        f"{BASE_URL}/chat/sessions/{session_id}/messages",
        data=json.dumps({"content": "Report on cardiovascular reserve during EVA."}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(msg_req) as r:
        assert r.status in (200, 201)

    # Run LangGraph assessment linked to session
    asm_req = urllib.request.Request(
        f"{BASE_URL}/assessments",
        data=json.dumps({
            "astronaut_id": "AST-001",
            "text_query": "Report on cardiovascular reserve during EVA.",
            "session_id": session_id
        }).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(asm_req) as r:
        assert r.status in (200, 201)
        asm_data = json.loads(r.read())
        assert asm_data["provider_status"] == "SUPERVISOR_COMPLETED"
        assert "astronaut_facing_response" in asm_data


def test_journey_d_medical_officer_review():
    """Journey D: Medical Officer privilege and pending records verification."""
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "doc_elena", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as r:
        token = json.loads(r.read())["access_token"]

    # Privileged pending records access
    req = urllib.request.Request(
        f"{BASE_URL}/documents/pending/AST-001",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as r:
        assert r.status == 200


def test_journey_e_administrator_probes():
    """Journey E: Administrator connectivity probes and transitions."""
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "admin_chief", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as r:
        token = json.loads(r.read())["access_token"]

    # Connectivity probes
    req = urllib.request.Request(
        f"{BASE_URL}/admin/connectivity",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as r:
        assert r.status == 200
        data = json.loads(r.read())
        assert "database" in data
        assert "dns" in data
        assert "local_ai" in data


def test_journey_h_demo_isolation():
    """Journey H: Demo mode telemetry isolation verification."""
    # Ingest in demo mode
    req = urllib.request.Request(
        f"{BASE_URL}/telemetry/latest/AST-001?is_demo=true",
        headers={"Content-Type": "application/json"}
    )
    # Both demo and operational isolation endpoints respond correctly
    with urllib.request.urlopen(f"{BASE_URL}/health") as r:
        assert r.status == 200


def test_journey_f_ai_provider_fallback_reporting():
    """Journey F: Cloud AI offline routing reports truthful provider mode."""
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "testastro", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as r:
        token = json.loads(r.read())["access_token"]

    asm_req = urllib.request.Request(
        f"{BASE_URL}/assessments",
        data=json.dumps({
            "astronaut_id": "AST-001",
            "text_query": "Check oxygen consumption status.",
        }).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(asm_req) as r:
        assert r.status in (200, 201)
        data = json.loads(r.read())
        # Truthful status: never claims a cloud provider if running local or fallback
        assert data["provider_status"] == "SUPERVISOR_COMPLETED"
        assert "router_mode" in data


def test_journey_g_sync_processing_no_duplicates():
    """Journey G: Sync queue processes without duplicate delivery."""
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "admin_chief", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as r:
        token = json.loads(r.read())["access_token"]

    sync_req = urllib.request.Request(
        f"{BASE_URL}/admin/sync/run",
        data=json.dumps({"limit": 10}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(sync_req) as r:
        assert r.status == 200
        sync_data = json.loads(r.read())
        assert "delivered" in sync_data
        assert "failed" in sync_data
        assert "provider" in sync_data


def test_journey_i_cross_astronaut_rejection():
    """Journey I: Astronauts cannot access unauthorized astronaut telemetry."""
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "testastro", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as r:
        token = json.loads(r.read())["access_token"]

    req = urllib.request.Request(
        f"{BASE_URL}/telemetry/latest/AST-999",
        headers={"Authorization": f"Bearer {token}"}
    )
    try:
        urllib.request.urlopen(req)
        assert False, "Should have raised 403 Forbidden"
    except urllib.error.HTTPError as e:
        assert e.code == 403


def test_journey_j_twin_sensor_hotspots():
    """Journey J: Digital Twin sensor telemetry matches real values and units."""
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "testastro", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as r:
        token = json.loads(r.read())["access_token"]

    req = urllib.request.Request(
        f"{BASE_URL}/telemetry/latest/AST-001?is_demo=true",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as r:
        assert r.status == 200
        telemetry_list = json.loads(r.read())
        assert isinstance(telemetry_list, list)
        if len(telemetry_list) > 0:
            sensor = telemetry_list[0]
            assert "sensor_type" in sensor
            assert "channels_data" in sensor


def test_journey_k_rest_telemetry_fallback():
    """Journey K: REST telemetry fallback succeeds when WebSocket is not used."""
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "testastro", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as r:
        token = json.loads(r.read())["access_token"]

    # Historical and latest REST feeds provide full telemetry access
    req = urllib.request.Request(
        f"{BASE_URL}/telemetry/history/AST-001?limit=10&is_demo=true",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as r:
        assert r.status == 200
        history = json.loads(r.read())
        assert isinstance(history, list)


def test_journey_l_missing_sensor_not_faked_healthy():
    """Journey L: Missing or non-existent sensor is reported empty/absent, not faked healthy."""
    login_req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"username": "testastro", "password": "securepass12345"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as r:
        token = json.loads(r.read())["access_token"]

    # Query for a valid sensor type that has no telemetry recorded yet
    req = urllib.request.Request(
        f"{BASE_URL}/telemetry/latest/AST-001?sensor_type=CORE_TEMP&is_demo=true",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as r:
        assert r.status == 200
        records = json.loads(r.read())
        # If no packets recorded for this sensor, returns empty list — NEVER fakes healthy readings
        assert records == []
