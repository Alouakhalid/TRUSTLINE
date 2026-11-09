"""Stress Test 09: Timeout handling, concurrency, and cross-session isolation."""
import concurrent.futures
import copy
import pytest
from unittest.mock import patch
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
from supervisor.config.settings import get_supervisor_settings

def test_01_concurrent_workflows_maintain_state_isolation(tmp_path):
    """Verify concurrent execution of two distinct workflows prevents cross-session leakage."""
    cfg = get_supervisor_settings()
    runner = SupervisorWorkflowRunner()

    state_astro_a = {
        "astronaut_id": "AST-ALPHA",
        "session_id": "SESSION-ALPHA",
        "workflow_id": "WF-ALPHA-100",
        "sensor_quality_result": {
            "overall_quality_score": 0.95,
            "sensors": {"ECG": {"status": "VALID", "quality_score": 0.98}}
        },
        "personal_health_result": {
            "core_features": {"hr_mean_bpm": 65.0, "hrv_rmssd_ms": 42.0}
        },
        "risk_assessment_result": {
            "overall_risk": "INSUFFICIENT_DATA",
            "overall_confidence": "MODERATE",
            "assessment_status": "PARTIALLY_COMPLETED",
            "coverage": {
                "total_domains": 10,
                "domain_coverage_ratio": 0.5,
                "evaluated_domains": ["CARDIOVASCULAR"],
                "unevaluated_domains": []
            },
            "escalation": {"state": "NO_TRIGGER_DETECTED", "required": False}
        }
    }

    state_astro_b = {
        "astronaut_id": "AST-BETA",
        "session_id": "SESSION-BETA",
        "workflow_id": "WF-BETA-200",
        "sensor_quality_result": {
            "overall_quality_score": 0.45,
            "sensors": {"ECG": {"status": "INVALID", "quality_score": 0.30}}
        },
        "personal_health_result": {
            "core_features": {"hr_mean_bpm": 115.0, "hrv_rmssd_ms": 0.0}
        },
        "risk_assessment_result": {
            "overall_risk": "INSUFFICIENT_DATA",
            "overall_confidence": "LOW",
            "assessment_status": "PARTIALLY_COMPLETED",
            "coverage": {
                "total_domains": 10,
                "domain_coverage_ratio": 0.3,
                "evaluated_domains": ["DATA_QUALITY_RELATED"],
                "unevaluated_domains": []
            },
            "escalation": {"state": "NO_TRIGGER_DETECTED", "required": False}
        }
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(runner.run_pipeline, initial_state=state_astro_a)
        future_b = executor.submit(runner.run_pipeline, initial_state=state_astro_b)

        result_a = future_a.result()
        result_b = future_b.result()

    assert result_a["astronaut_id"] == "AST-ALPHA"
    assert result_a["session_id"] == "SESSION-ALPHA"
    assert result_a["workflow_id"] == "WF-ALPHA-100"

    assert result_b["astronaut_id"] == "AST-BETA"
    assert result_b["session_id"] == "SESSION-BETA"
    assert result_b["workflow_id"] == "WF-BETA-200"

    assert result_a["final_assessment"]["astronaut_id"] == "AST-ALPHA"
    assert result_b["final_assessment"]["astronaut_id"] == "AST-BETA"

def test_02_simultaneous_multi_agent_failures_handled_gracefully():
    """Verify workflow degrades safely when both Sensor Quality and PHA fail concurrently."""
    runner = SupervisorWorkflowRunner()

    with patch("supervisor.adapters.sensor_quality_adapter.SensorQualityAdapter.run", side_effect=RuntimeError("SQ Hardware Bus Fault")), \
         patch("supervisor.adapters.personal_health_adapter.PersonalHealthAdapter.run", side_effect=RuntimeError("PHA Memory Allocation Fault")):
        result = runner.run_pipeline(initial_state={
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001"
        })

    agent_statuses = result.get("agent_execution_status") or {}
    assert agent_statuses.get("sensor_quality_agent", {}).get("status") == "FAILED"
    assert agent_statuses.get("personal_health_agent", {}).get("status") == "FAILED"
    assert result.get("workflow_status") in ("PARTIALLY_COMPLETED", "FAILED")
    assert result.get("current_step") == "FINAL_RESPONSE"

def test_03_same_astronaut_multiple_sessions_isolated():
    """Verify successive workflows for same astronaut do not collide."""
    runner = SupervisorWorkflowRunner()

    state_s1 = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "workflow_id": "WF-AST-S1",
        "risk_assessment_result": {"overall_risk": "INSUFFICIENT_DATA"}
    }
    state_s2 = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-002",
        "workflow_id": "WF-AST-S2",
        "risk_assessment_result": {"overall_risk": "INSUFFICIENT_DATA"}
    }

    res_1 = runner.run_pipeline(initial_state=state_s1)
    res_2 = runner.run_pipeline(initial_state=state_s2)

    assert res_1["session_id"] == "SESSION-001"
    assert res_2["session_id"] == "SESSION-002"
    assert res_1["workflow_id"] != res_2["workflow_id"]
