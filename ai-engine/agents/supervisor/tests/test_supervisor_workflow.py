"""Unit tests for Supervisor LangGraph workflow graph execution and routing."""
import pytest
from supervisor.workflow.router import route_after_validation
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.schemas.requests import SupervisorRequest, AstronautInput

def test_01_router_branches_to_evidence_validation_on_validation_failure():
    """Verify route_after_validation directs to evidence_validation when errors exist."""
    state_failed = {"errors": ["Invalid subject ID"], "workflow_status": "FAILED"}
    assert route_after_validation(state_failed) == "evidence_validation"

    state_ok = {"errors": [], "workflow_status": "IN_PROGRESS"}
    assert route_after_validation(state_ok) == "sensor_quality"

def test_02_workflow_runner_handles_invalid_astronaut_identity():
    """Verify workflow terminates with FAILED status and error logs when astronaut ID is empty."""
    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(initial_state={
        "astronaut_id": "",
        "session_id": "SESSION-001"
    })
    assert result["workflow_status"] == "FAILED"
    assert any("astronaut_id" in e for e in result["errors"])
    assert result["current_step"] == "FINAL_RESPONSE"
    assert "completed" in result["timestamps"]

def test_03_workflow_runner_handles_missing_sensor_data_gracefully():
    """Verify workflow executes without failure when sensor manifest is omitted."""
    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(initial_state={
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001"
    })
    sq_status = result["agent_execution_status"].get("sensor_quality_agent", {})
    assert sq_status.get("status") in ("SKIPPED", "PARTIAL")
    assert result["current_step"] == "FINAL_RESPONSE"
    assert "completed" in result["timestamps"]

def test_04_workflow_runner_handles_upstream_pha_failure():
    """Verify workflow recovers safely when Personal Health agent encounters an unhandled exception."""
    from unittest.mock import patch
    runner = SupervisorWorkflowRunner()

    with patch("supervisor.adapters.personal_health_adapter.PersonalHealthAdapter.run", side_effect=RuntimeError("Simulated PHA crash")):
        result = runner.run_pipeline(initial_state={
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001"
        })
    pha_status = result["agent_execution_status"].get("personal_health_agent", {})
    assert pha_status.get("status") == "FAILED"
    assert "Simulated PHA crash" in pha_status.get("error_message", "")
    assert result["current_step"] == "FINAL_RESPONSE"

def test_05_workflow_runner_handles_upstream_ra_failure():
    """Verify workflow completes with error status when Risk Assessment agent fails."""
    from unittest.mock import patch
    runner = SupervisorWorkflowRunner()

    with patch("supervisor.adapters.risk_assessment_adapter.RiskAssessmentAdapter.run", side_effect=ValueError("Simulated RA rule engine fault")):
        result = runner.run_pipeline(initial_state={
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001"
        })
    ra_status = result["agent_execution_status"].get("risk_assessment_agent", {})
    assert ra_status.get("status") == "FAILED"
    assert "Simulated RA rule engine fault" in ra_status.get("error_message", "")
    assert result["current_step"] == "FINAL_RESPONSE"

def test_06_workflow_runner_handles_persistence_warning():
    """Verify workflow handles database persistence failure without raising an uncaught exception."""
    from unittest.mock import patch
    runner = SupervisorWorkflowRunner()

    with patch("supervisor.services.persistence_service.PersistenceService.save_final_assessment", return_value=(False, "", ["Database locked"])):
        result = runner.run_pipeline(initial_state={
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001"
        })
    assert any("Database locked" in w for w in result["warnings"])
    assert result["current_step"] == "FINAL_RESPONSE"
