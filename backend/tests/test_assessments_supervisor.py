"""Supervisor assessments through the mission API.

These tests invoke the REAL existing LangGraph Supervisor workflow (the sole
orchestrator) via the backend gateway. Provider routing at the API boundary is
LOCAL_ONLY (the gateway default), so no cloud provider is contacted and no
credentials are spent. Exactly one real invocation runs in this module; every
other test reads persisted state or is rejected before the workflow runs.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def assessment_env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("assessments")
    from backend.api import app as module
    module.store.configure(str(tmp / "assess.db"))
    client = TestClient(module.app)
    users = {}
    for username, role, astro in (
        ("astro1", "ASTRONAUT", "AST-001"),
        ("astro2", "ASTRONAUT", "AST-002"),
        ("medic", "MEDICAL_OFFICER", None),
    ):
        payload = {"username": username, "password": "a-very-strong-password", "role": role}
        if astro:
            payload["astronaut_id"] = astro
        client.post("/auth/register", json=payload)
        users[username] = client.post("/auth/login", json={"username": username, "password": "a-very-strong-password"}).json()["access_token"]
    yield module, client, users


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_supervisor_assessment_end_to_end(assessment_env):
    module, client, users = assessment_env
    astro = _headers(users["astro1"])

    # The astronaut prepares a chat session that will receive the agent reply.
    session = client.post("/chat/sessions", headers=astro, json={"title": "Medical check-in"})
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    assert client.post(
        f"/chat/sessions/{session_id}/messages", headers=astro,
        json={"content": "mild headache after exercise, otherwise feeling fine"},
    ).status_code == 201

    response = client.post("/assessments", headers=astro, json={
        "astronaut_id": "AST-001",
        "text_query": "mild headache after exercise, otherwise feeling fine",
        "session_id": session_id,
        "mission_context": {"mission_day": 42},
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["provider_status"] == "SUPERVISOR_COMPLETED"
    assert body["router_mode"] == "LOCAL_ONLY"  # no cloud provider contacted
    assert "COMPLETED" in str(body["completion_status"]).upper()
    assert len(body["astronaut_facing_response"]) > 0  # real workflow reply, not an echo
    assert body["session_message_appended"] is True
    assert set(body["agent_statuses"].keys()) == {
        "supervisor", "sensor_quality_agent", "personal_health_agent", "medical_rag_agent", "risk_assessment_agent",
    }

    # Evidence registry items carry provenance and are persisted with the record.
    refs = body["evidence_references"]
    assert isinstance(refs, list) and len(refs) >= 1
    for ref in refs:
        assert ref["evidence_id"] and ref["source_agent"]
    detail = client.get(f"/assessments/{body['assessment_id']}", headers=astro).json()
    assert detail["evidence_count"] == len(refs)

    # Workflow C/D wiring: the AGENT reply lands in the session with evidence citations.
    messages = client.get(f"/chat/sessions/{session_id}/messages", headers=astro).json()
    agent_messages = [m for m in messages if m["sender"] == "AGENT"]
    assert len(agent_messages) == 1
    assert agent_messages[0]["agent"] == "supervisor"
    assert agent_messages[0]["processing_status"] == "COMPLETED"
    citation_ids = [c["evidence_id"] for c in agent_messages[0]["citations"]]
    assert citation_ids == [ref["evidence_id"] for ref in refs]

    # A short-term LIVE PHA memory records the assessment with 24h expiry and provenance.
    memories = client.get("/memory/AST-001/PHA", headers=astro).json()
    live = [m for m in memories if m["content"].startswith(f"Assessment {body['assessment_id']}")]
    assert len(live) == 1
    memory = live[0]
    assert memory["verification_status"] == "LIVE"
    assert memory["is_long_term"] is False
    assert memory["provenance"]["assessment_id"] == body["assessment_id"]
    expires = datetime.fromisoformat(memory["expires_at"])
    hours = (expires - datetime.now(timezone.utc)).total_seconds() / 3600
    assert 23.0 <= hours <= 25.0  # ttl_hours=24 honored


def test_assessment_rbac_and_identity_isolation(assessment_env):
    module, client, users = assessment_env
    astro1, astro2, medic = _headers(users["astro1"]), _headers(users["astro2"]), _headers(users["medic"])

    # Astronauts cannot request assessments for another astronaut (no workflow run).
    assert client.post("/assessments", headers=astro1, json={
        "astronaut_id": "AST-002", "text_query": "not my assessment",
    }).status_code == 403

    listing = client.get("/assessments", headers=astro1).json()
    assert len(listing) == 1  # the single real assessment from the e2e test
    assessment_id = listing[0]["id"]

    # Astronaut receives a summary view (no internal workflow payload).
    summary = client.get(f"/assessments/{assessment_id}", headers=astro1)
    assert summary.status_code == 200
    assert "result" not in summary.json() and "agent_statuses" not in summary.json()
    assert summary.json()["astronaut_id"] == "AST-001"

    # Other astronauts are excluded entirely; officers see the full record.
    assert client.get(f"/assessments/{assessment_id}", headers=astro2).status_code == 403
    full = client.get(f"/assessments/{assessment_id}", headers=medic)
    assert full.status_code == 200
    assert "result" in full.json() and full.json()["result"]["provider_status"] == "SUPERVISOR_COMPLETED"

    # Astronaut listing is force-scoped to their own identity.
    assert client.get("/assessments", headers=astro2).json() == []
    # Privileged roles must name the subject explicitly (no implicit fleet dump).
    assert client.get("/assessments", headers=medic).status_code == 400
    assert client.get("/assessments", params={"astronaut_id": "AST-001"}, headers=medic).status_code == 200


def test_demo_assessments_are_isolated(assessment_env):
    """Demo rows live in the is_demo partition; operational reads never see them.

    The demo row here is explicit test fixture data written via the store seam
    (no Supervisor invocation is claimed or consumed for it).
    """
    module, client, users = assessment_env
    demo_row = {
        "provider_status": "SUPERVISOR_COMPLETED", "router_mode": "LOCAL_ONLY",
        "completion_status": "FIXTURE", "overall_risk": "NOMINAL",
        "astronaut_facing_response": "demo fixture response",
    }
    module.store.run(
        "INSERT INTO assessments(id,astronaut_id,session_id,workflow_id,completion_status,overall_risk,overall_confidence,astronaut_response,assessment_json,evidence_count,created_at,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        ("ASM-DEMO-FIXTURE", "AST-001", None, None, "FIXTURE", "NOMINAL", None,
         "demo fixture response", json.dumps(demo_row), 0,
         datetime.now(timezone.utc).isoformat(), 1),
    )
    astro1 = {**_headers(users["astro1"]), "X-Trustline-Mode": "demo"}
    operational = _headers(users["astro1"])

    demo_ids = [a["id"] for a in client.get("/assessments", headers=astro1).json()]
    operational_ids = [a["id"] for a in client.get("/assessments", headers=operational).json()]
    assert "ASM-DEMO-FIXTURE" in demo_ids
    assert "ASM-DEMO-FIXTURE" not in operational_ids
