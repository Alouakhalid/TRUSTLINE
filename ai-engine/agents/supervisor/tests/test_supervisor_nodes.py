"""Unit tests for individual Supervisor LangGraph node functions."""
import pytest
from datetime import datetime
from supervisor.schemas.state import SupervisorMultiAgentState
from supervisor.workflow.nodes import (
    intake_node,
    input_validation_node,
    evidence_validation_node,
    final_synthesis_node,
    persistence_node,
    final_response_node
)

def test_01_intake_node_initializes_workflow_state():
    """Verify intake_node initializes identifiers and timestamps."""
    initial: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001"
    }
    updates = intake_node(initial)
    assert "workflow_id" in updates
    assert updates["workflow_status"] == "IN_PROGRESS"
    assert updates["current_step"] == "INTAKE"
    assert "intake" in updates["timestamps"]
    assert "supervisor" in updates["agent_execution_status"]

def test_02_input_validation_node_accepts_valid_ids():
    """Verify input_validation_node accepts valid astronaut and session identifiers."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "manifest_path": "data/input/astronaut_health_data.json"
    }
    updates = input_validation_node(state)
    assert updates["current_step"] == "INPUT_VALIDATION"
    assert len(updates["errors"]) == 0
    assert len(updates["missing_data"]) > 0

def test_03_input_validation_node_rejects_missing_astronaut_id():
    """Verify input_validation_node sets failure status when astronaut_id is missing."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "",
        "session_id": "SESSION-001"
    }
    updates = input_validation_node(state)
    assert updates["workflow_status"] == "FAILED"
    assert updates["current_step"] == "INPUT_VALIDATION_FAILED"
    assert any("astronaut_id" in e for e in updates["errors"])

def test_04_input_validation_node_rejects_missing_session_id():
    """Verify input_validation_node sets failure status when session_id is missing."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": ""
    }
    updates = input_validation_node(state)
    assert updates["workflow_status"] == "FAILED"
    assert any("session_id" in e for e in updates["errors"])

def test_05_evidence_validation_node_audits_and_quarantines_invalid_hrv():
    """Verify evidence_validation_node automatically quarantines zero-variability HRV artifacts."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "personal_health_result": {
            "core_features": {
                "hr_mean_bpm": 72.0,
                "hrv_rmssd_ms": 0.0,
                "resp_rate_bpm": 15.0,
                "temp_mean": 34.27,
                "eda_mean": 4.69
            },
            "hrv_diagnostics": {
                "hrv_status": "ZERO_VARIABILITY"
            }
        }
    }
    updates = evidence_validation_node(state)
    registry = updates["evidence_registry"]
    hrv_item = next((item for item in registry if item["evidence_id"] == "EV-PHY-HRV-RMSSD"), None)
    assert hrv_item is not None
    assert hrv_item["is_quarantined"] is True
    assert hrv_item["validity_status"] == "INVALID"
    assert "quarantined" in hrv_item["quarantine_reason"]

def test_06_final_synthesis_node_compiles_assessment_and_response():
    """Verify final_synthesis_node creates unified FinalSupervisorAssessment."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "workflow_id": "WF-TEST-01",
        "timestamps": {"intake": datetime.utcnow().isoformat()},
        "risk_assessment_result": {
            "overall_risk": "INSUFFICIENT_DATA",
            "overall_confidence": "MODERATE",
            "assessment_status": "PARTIALLY_COMPLETED",
            "coverage": {
                "total_domains": 10,
                "evaluated_domains": ["CARDIOVASCULAR", "RESPIRATORY"],
                "unevaluated_domains": ["NEUROLOGICAL"],
                "domain_coverage_ratio": 0.2,
                "coverage_status": "PARTIAL"
            },
            "escalation": {
                "state": "NO_TRIGGER_DETECTED",
                "required": False,
                "urgency_level": "NOMINAL"
            },
            "recommended_actions": [
                {
                    "action_id": "ACT-NOM-001",
                    "description": "Continue routine health telemetry acquisition."
                }
            ]
        }
    }
    updates = final_synthesis_node(state)
    assert "final_assessment" in updates
    assert "final_response" in updates
    assert updates["workflow_status"] == "PARTIALLY_COMPLETED"
    assert updates["current_step"] == "FINAL_SYNTHESIS"
    assert "TRUSTLINE Mission Health Briefing" in updates["final_response"]
    assert "supervisor" in updates["final_assessment"]["agent_execution_statuses"]
    assert updates["final_assessment"]["agent_execution_statuses"]["supervisor"]["execution_time_ms"] >= 0.0

def test_07_persistence_node_writes_output(tmp_path):
    """Verify persistence_node writes JSON artifact and updates state without throwing unhandled exceptions."""
    from supervisor.config.settings import get_supervisor_settings
    cfg = get_supervisor_settings()
    orig = cfg.output_dir
    try:
        cfg.output_dir = tmp_path

        state: SupervisorMultiAgentState = {
            "final_assessment": {
                "assessment_id": "SUP-TEST-P1",
                "astronaut_id": "AST-001",
                "session_id": "SESSION-001",
                "workflow_id": "WF-P1",
                "workflow_completion_status": "COMPLETED",
                "overall_risk": "LOW",
                "escalation_state": "NO_TRIGGER_DETECTED"
            }
        }
        updates = persistence_node(state)
        assert updates["current_step"] == "PERSISTENCE"
        assert (tmp_path / "final_supervisor_assessment.json").exists()
    finally:
        cfg.output_dir = orig

def test_08_final_response_node_records_completed_timestamp():
    """Verify final_response_node updates timestamps with completed step."""
    state: SupervisorMultiAgentState = {
        "timestamps": {"intake": datetime.utcnow().isoformat()}
    }
    updates = final_response_node(state)
    assert updates["current_step"] == "FINAL_RESPONSE"
    assert "completed" in updates["timestamps"]
