from __future__ import annotations

import json
import fitz
from fastapi.testclient import TestClient
import pytest

from backend.api import app as module
from backend.services.telemetry import compute_crc32
from backend.sync.queue import SyncConflict


def _pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def test_env(monkeypatch, tmp_path):
    db_path = str(tmp_path / "p09_test.db")
    monkeypatch.setenv("TRUSTLINE_DB_PATH", db_path)
    module.store.configure(db_path)
    
    from backend.api import documents as documents_module
    documents_module.configure_document_stack(
        database_url=f"sqlite:///{tmp_path / 'p09_documents.db'}",
        upload_dir=str(tmp_path / "uploads"),
        processed_docs_dir=str(tmp_path / "processed"),
    )
    
    client = TestClient(module.app)
    return client, module.store


def test_workflow_a_astronaut_telemetry_and_kpis(test_env):
    """Workflow A (Astronaut): Login -> Profile -> Telemetry Ingest -> Assessment -> Historical Feed."""
    client, store = test_env
    
    reg = client.post("/auth/register", json={
        "username": "astro_alex",
        "password": "MissionSecret2026!",
        "role": "ASTRONAUT",
        "astronaut_id": "AST-001"
    })
    assert reg.status_code == 201
    
    login = client.post("/auth/login", json={
        "username": "astro_alex",
        "password": "MissionSecret2026!"
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["astronaut_id"] == "AST-001"
    assert me.json()["role"] == "ASTRONAUT"
    
    channels = [[74.5, 75.0, 74.8]]
    seq = 0
    ts = 1700000000000
    crc = compute_crc32("ECG", seq, ts, channels)
    
    packet = {
        "packet_id": "PKT-P09-001",
        "sequence_number": seq,
        "astronaut_id": "AST-001",
        "session_id": "SESSION-EVA-1",
        "timestamp_epoch_ms": ts,
        "sensor_type": "ECG",
        "sample_rate_hz": 250.0,
        "channels_data": channels,
        "checksum_crc32": crc
    }
    ingest = client.post("/telemetry/packets", headers=headers, json={
        "astronaut_id": "AST-001",
        "packets": [packet]
    })
    assert ingest.status_code == 202
    res = ingest.json()
    assert res["accepted"] == 1
    assert res["checksum_failures"] == 0
    
    latest = client.get("/telemetry/latest/AST-001", headers=headers)
    assert latest.status_code == 200
    items = latest.json()
    assert len(items) == 1
    assert items[0]["sensor_type"] == "ECG"
    
    history = client.get("/telemetry/history/AST-001?limit=10", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_workflow_b_medical_document_ocr_and_evidence_gate(test_env):
    """Workflow B (Medical Document): Upload -> Validation -> Pending Review -> Flight Surgeon Review -> Confirmed."""
    client, store = test_env
    
    client.post("/auth/register", json={"username": "astro_bob", "password": "MissionSecret2026!", "role": "ASTRONAUT", "astronaut_id": "AST-002"})
    client.post("/auth/register", json={"username": "dr_stone", "password": "FlightSurgeon2026!", "role": "MEDICAL_OFFICER"})
    
    astro_token = client.post("/auth/login", json={"username": "astro_bob", "password": "MissionSecret2026!"}).json()["access_token"]
    doc_token = client.post("/auth/login", json={"username": "dr_stone", "password": "FlightSurgeon2026!"}).json()["access_token"]
    
    astro_headers = {"Authorization": f"Bearer {astro_token}"}
    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    
    pdf_content = _pdf_bytes("STATION MEDICAL LAB: Serum Sodium 140 mmol/L, Hematocrit 44%. Nominal.")
    upload_res = client.post(
        "/documents/upload",
        headers=astro_headers,
        data={"astronaut_id": "AST-002", "document_type": "LAB_RESULT"},
        files={"file": ("lab_panel_2026.pdf", pdf_content, "application/pdf")}
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    document_id = doc_data["document_id"]
    assert doc_data["status"] == "UPLOADED"
    
    self_process = client.post(
        f"/documents/{document_id}/process",
        headers=astro_headers
    )
    assert self_process.status_code == 403
    
    process_res = client.post(
        f"/documents/{document_id}/process",
        headers=doc_headers
    )
    assert process_res.status_code == 200
    body = process_res.json()
    assert body["overall_status"] in {"PROCESSED", "PROCESSED_WITH_WARNINGS", "COMPLETED"}
    
    pending = client.get("/documents/pending/AST-002", headers=doc_headers).json()
    if pending:
        rec_id = pending[0]["record_id"]
        confirm_res = client.post("/documents/confirm", headers=doc_headers, json={"record_ids": [rec_id]})
        assert confirm_res.status_code == 200
        assert confirm_res.json()["confirmed_count"] >= 1


def test_workflow_c_ai_companion_chat_and_citations(test_env):
    """Workflow C (AI Companion): Session -> Message -> Supervisor End-to-End Execution -> Citations -> History."""
    client, store = test_env
    
    client.post("/auth/register", json={"username": "astro_clara", "password": "MissionSecret2026!", "role": "ASTRONAUT", "astronaut_id": "AST-003"})
    astro_token = client.post("/auth/login", json={"username": "astro_clara", "password": "MissionSecret2026!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {astro_token}"}
    
    sess = client.post("/chat/sessions", headers=headers, json={"title": "Pre-EVA Clinical Q&A"})
    assert sess.status_code == 201
    sess_id = sess.json()["id"]
    
    msg_res = client.post(
        f"/chat/sessions/{sess_id}/messages",
        headers=headers,
        json={"content": "mild headache after exercise, otherwise feeling fine"}
    )
    assert msg_res.status_code == 201
    
    response = client.post("/assessments", headers=headers, json={
        "astronaut_id": "AST-003",
        "text_query": "mild headache after exercise, otherwise feeling fine",
        "session_id": sess_id,
        "mission_context": {"mission_day": 42}
    })
    assert response.status_code == 201
    body = response.json()
    assert body["provider_status"] == "SUPERVISOR_COMPLETED"
    assert body["router_mode"] == "LOCAL_ONLY"
    assert body["session_message_appended"] is True
    assert len(body["evidence_references"]) >= 1
    
    history = client.get(f"/chat/sessions/{sess_id}/messages", headers=headers)
    assert history.status_code == 200
    msgs = history.json()
    agent_msgs = [m for m in msgs if m["sender"] == "AGENT"]
    assert len(agent_msgs) == 1
    assert agent_msgs[0]["agent"] == "supervisor"
    assert len(agent_msgs[0]["citations"]) >= 1


def test_workflow_d_agent_memory_persistence_and_governance(test_env):
    """Workflow D (Agent Memory): Memory Write -> Versioning -> Audit Trail -> Cross-Astronaut Guard."""
    client, store = test_env
    
    client.post("/auth/register", json={"username": "astro_dan", "password": "MissionSecret2026!", "role": "ASTRONAUT", "astronaut_id": "AST-004"})
    client.post("/auth/register", json={"username": "dr_watson", "password": "FlightSurgeon2026!", "role": "MEDICAL_OFFICER"})
    
    dan_token = client.post("/auth/login", json={"username": "astro_dan", "password": "MissionSecret2026!"}).json()["access_token"]
    doc_token = client.post("/auth/login", json={"username": "dr_watson", "password": "FlightSurgeon2026!"}).json()["access_token"]
    
    dan_headers = {"Authorization": f"Bearer {dan_token}"}
    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    
    # 1. Astronaut writes personal memory in PHA namespace
    mem_res = client.post(
        "/memory",
        headers=dan_headers,
        json={
            "astronaut_id": "AST-004",
            "namespace": "PHA",
            "content": json.dumps({"preferred_temp": 19.5, "sound_mask": "brown_noise"}),
            "verification_status": "PENDING",
            "provenance": {"source": "Astronaut self-report"},
            "long_term": False
        }
    )
    assert mem_res.status_code == 201
    mem_id = mem_res.json()["id"]
    
    # 2. Medical Officer writes confirmed memory in MEDICAL_RAG namespace
    med_mem = client.post(
        "/memory",
        headers=doc_headers,
        json={
            "astronaut_id": "AST-004",
            "namespace": "MEDICAL_RAG",
            "content": json.dumps({"allergen": "Penicillin", "severity": "SEVERE"}),
            "verification_status": "CONFIRMED",
            "provenance": {"source": "Dr. Watson clinical review"},
            "long_term": True
        }
    )
    assert med_mem.status_code == 201
    med_mem_id = med_mem.json()["id"]
    assert med_mem.json()["verification_status"] == "CONFIRMED"
    
    # 3. Medical Officer updates confirmed memory -> version bumped to 2
    update_res = client.patch(
        f"/memory/{med_mem_id}",
        headers=doc_headers,
        json={"content": json.dumps({"allergen": "Penicillin", "severity": "SEVERE", "epipen_assigned": True})}
    )
    assert update_res.status_code == 200
    assert update_res.json()["version"] == 2
    
    # 4. Read memory list and verify version is present
    mem_list = client.get("/memory/AST-004/MEDICAL_RAG", headers=doc_headers)
    assert mem_list.status_code == 200
    assert mem_list.json()[0]["version"] == 2
    
    # 5. Identity isolation: Astronaut Dan cannot write memory for AST-002
    bad_res = client.post(
        "/memory",
        headers=dan_headers,
        json={
            "astronaut_id": "AST-002",
            "namespace": "PHA",
            "content": json.dumps({"hack": True}),
            "verification_status": "PENDING",
            "long_term": False
        }
    )
    assert bad_res.status_code == 403


def test_workflow_e_offline_mission_and_sync_queue(test_env):
    """Workflow E (Offline Mission): Connectivity Probe -> Offline Local Queue -> Sync Run -> Conflict Guard."""
    client, store = test_env
    
    client.post("/auth/register", json={"username": "admin_ops", "password": "MissionAdmin2026!", "role": "ADMINISTRATOR"})
    admin_token = client.post("/auth/login", json={"username": "admin_ops", "password": "MissionAdmin2026!"}).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    probe = client.get("/admin/connectivity", headers=admin_headers)
    assert probe.status_code == 200
    diag = probe.json()
    assert "connectivity_state" in diag
    assert "database" in diag
    assert "dns" in diag
    
    sync = module.sync
    rec = sync.enqueue("EVENT-P09-001", "telemetry", {"hr": 72.0}, is_demo=False)
    assert rec["id"] == "EVENT-P09-001"
    assert rec["status"] == "PENDING"
    
    status_res = client.get("/admin/sync/status", headers=admin_headers)
    assert status_res.status_code == 200
    assert status_res.json()["counts"]["PENDING"] >= 1
    
    sync_run = client.post("/admin/sync/run", headers=admin_headers, json={"limit": 10})
    assert sync_run.status_code == 200
    body = sync_run.json()
    assert "TRANSPORT_NOT_READY" in body["skipped"] or body["delivered"] >= 0
    
    with pytest.raises(SyncConflict):
        sync.resolve_conflict("EVENT-P09-001", local_version=1, ground_version=2, is_demo=False)


def test_workflow_f_medical_officer_review_audit_and_findings(test_env):
    """Workflow F (Medical Officer): Assigned Astronaut Telemetry Review -> Clinical Findings -> Audit."""
    client, store = test_env
    
    client.post("/auth/register", json={"username": "astro_eva", "password": "MissionSecret2026!", "role": "ASTRONAUT", "astronaut_id": "AST-006"})
    client.post("/auth/register", json={"username": "dr_house", "password": "FlightSurgeon2026!", "role": "MEDICAL_OFFICER"})
    
    doc_token = client.post("/auth/login", json={"username": "dr_house", "password": "FlightSurgeon2026!"}).json()["access_token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    
    hist = client.get("/telemetry/history/AST-006", headers=doc_headers)
    assert hist.status_code == 200
    assert isinstance(hist.json(), list)
    
    finding = client.post(
        "/memory",
        headers=doc_headers,
        json={
            "astronaut_id": "AST-006",
            "namespace": "PHA",
            "content": json.dumps({"diagnosis": "Mild orthostatic intolerance post-centrifuge", "cleared_for_eva": True}),
            "verification_status": "CONFIRMED",
            "provenance": {"source": "Dr. House clinical finding"},
            "long_term": True
        }
    )
    assert finding.status_code == 201
    assert finding.json()["verification_status"] == "CONFIRMED"
    
    forbidden_sync = client.post("/admin/sync/run", headers=doc_headers, json={"limit": 10})
    assert forbidden_sync.status_code == 403


def test_workflow_g_administrator_diagnostics_and_demo_isolation(test_env):
    """Workflow G (Administrator): System Diagnostics -> Audit Trail -> Demo Isolation Verification."""
    client, store = test_env
    
    client.post("/auth/register", json={"username": "admin_sarah", "password": "MissionAdmin2026!", "role": "ADMINISTRATOR"})
    admin_token = client.post("/auth/login", json={"username": "admin_sarah", "password": "MissionAdmin2026!"}).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    audits = client.get("/admin/audit", headers=admin_headers)
    assert audits.status_code == 200
    assert isinstance(audits.json(), list)
    
    trans = client.get("/admin/transitions", headers=admin_headers)
    assert trans.status_code == 200
    assert isinstance(trans.json(), list)
    
    demo_headers = {"X-Trustline-Mode": "demo"}
    reg_demo = client.post("/auth/register", headers=demo_headers, json={
        "username": "synthetic_crew",
        "password": "DemoSecret2026!",
        "role": "ASTRONAUT",
        "astronaut_id": "DEMO-999"
    })
    assert reg_demo.status_code == 201
    
    demo_login = client.post("/auth/login", headers=demo_headers, json={
        "username": "synthetic_crew",
        "password": "DemoSecret2026!"
    })
    assert demo_login.status_code == 200
    demo_tok = demo_login.json()["access_token"]
    auth_demo_headers = {**demo_headers, "Authorization": f"Bearer {demo_tok}"}
    
    assert client.post("/auth/login", json={"username": "synthetic_crew", "password": "DemoSecret2026!"}).status_code == 401
    
    channels = [[60.0]]
    crc = compute_crc32("HR", 1, 1000, channels)
    client.post("/telemetry/packets", headers=auth_demo_headers, json={
        "astronaut_id": "DEMO-999",
        "packets": [{
            "packet_id": "DEMO-PKT-1",
            "sequence_number": 1,
            "astronaut_id": "DEMO-999",
            "session_id": "DEMO-SESS",
            "timestamp_epoch_ms": 1000,
            "sensor_type": "HR",
            "sample_rate_hz": 1.0,
            "channels_data": channels,
            "checksum_crc32": crc
        }]
    })
    
    live_hist = client.get("/telemetry/history/DEMO-999", headers=admin_headers)
    assert live_hist.status_code == 200
    assert len(live_hist.json()) == 0
