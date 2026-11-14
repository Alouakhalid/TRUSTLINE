"""Integration test for physiological simulator, multi-agent evaluation, and telemetry ingestion."""
import pytest
from fastapi.testclient import TestClient

from backend.api import app as module
from backend.services import telemetry


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLINE_DB_PATH", str(tmp_path / "sim_test.db"))
    module.store.configure(str(tmp_path / "sim_test.db"))
    client = TestClient(module.app)
    # Direct entry session for AST-002
    entry_res = client.post("/auth/direct-entry", json={"preferred_role": "ASTRONAUT"})
    assert entry_res.status_code == 200
    token = entry_res.json()["access_token"]
    return client, token


def test_simulator_step_propagates_to_telemetry_and_agents(monkeypatch, tmp_path):
    client, token = _setup(monkeypatch, tmp_path)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Step with EVA Activity
    res = client.post("/simulator/step?scenario=SCENARIO_B_EVA_ACTIVITY&astronaut_id=AST-002&seed=4242")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "step_generated"
    assert data["scenario"] == "SCENARIO_B_EVA_ACTIVITY"
    assert data["astronaut_id"] == "AST-002"
    assert "heart_rate" in data["readings"]
    assert "respiration" in data["readings"]
    # In EVA, HR target is high (typically > 100 bpm)
    assert data["readings"]["heart_rate"] > 90
    assert data["agent_decision"]["overall_risk"] in ["warning", "nominal"]

    # 2. Check that assessment was recorded in database
    asm_res = client.get("/assessments?astronaut_id=AST-002&limit=5", headers=headers)
    assert asm_res.status_code == 200
    assessments = asm_res.json()
    assert len(assessments) >= 1
    latest_asm = assessments[0]
    assert latest_asm["astronaut_id"] == "AST-002"
    assert "SIM-SCENARIO_B_EVA_ACTIVITY" in latest_asm["session_id"]

    # 3. Check latest telemetry endpoint returns fresh packets for AST-002
    tel_res = client.get("/telemetry/latest/AST-002", headers=headers)
    assert tel_res.status_code == 200
    packets = tel_res.json()
    assert len(packets) > 0
    sensor_types = {p["sensor_type"] for p in packets}
    assert "ECG" in sensor_types
    assert "HR" in sensor_types


def test_simulator_random_state_and_fault_injection(monkeypatch, tmp_path):
    client, token = _setup(monkeypatch, tmp_path)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Call random-state endpoint
    rand_res = client.post("/simulator/random-state?astronaut_id=AST-002")
    assert rand_res.status_code == 200
    rand_data = rand_res.json()
    assert rand_data["status"] == "step_generated"
    assert rand_data["astronaut_id"] == "AST-002"
    assert "agent_decision" in rand_data

    # 2. Inject FLATLINE fault
    fault_res = client.post("/simulator/fault", json={"fault_type": "FLATLINE", "target_sensor": "ECG", "severity": 1.0})
    assert fault_res.status_code == 200
    assert fault_res.json()["status"] == "fault_injected"

    # Step again to trigger multi-agent critical alarm
    step_res = client.post("/simulator/step?astronaut_id=AST-002")
    assert step_res.status_code == 200
    step_data = step_res.json()
    assert "FLATLINE" in step_data["agent_decision"]["active_faults"]
    assert step_data["agent_decision"]["overall_risk"] == "critical"
    assert "SQA Critical Alarm" in step_data["agent_decision"]["decision_note"]
