"""Tests verifying rigorous agent failure semantics and astronaut communication integrity."""
import pytest
from unittest.mock import patch
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.schemas.requests import SupervisorRequest, AstronautInput
from supervisor.schemas.assessment import WorkflowCompletionStatus

@pytest.fixture
def base_request():
    return SupervisorRequest(
        request_id="REQ-FAIL-SEMANTICS-001",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        input_data=AstronautInput(text_query="Status check")
    )

def test_01_risk_assessment_agent_failure_sets_unavailable_and_unknown(base_request):
    """Verify Supervisor sets ASSESSMENT_UNAVAILABLE and UNKNOWN when Risk Assessment Agent fails."""
    runner = SupervisorWorkflowRunner()
    with patch("supervisor.adapters.risk_assessment_adapter.RiskAssessmentAdapter.run", side_effect=RuntimeError("Rule engine crash")):
        result = runner.run_pipeline(base_request)

    fa = result.get("final_assessment") or {}
    assert result.get("workflow_status") == WorkflowCompletionStatus.PARTIALLY_COMPLETED.value
    assert fa.get("escalation_state") == "ASSESSMENT_UNAVAILABLE"
    assert fa.get("overall_risk") == "UNKNOWN"
    assert fa.get("escalation_required") is False

    agent_statuses = fa.get("agent_execution_statuses") or {}
    assert agent_statuses.get("risk_assessment_agent", {}).get("status") == "FAILED"

    resp = result.get("final_response") or ""
    assert "Risk Assessment Engine Unavailable" in resp
    assert "Clinical risk status is UNKNOWN" in resp
    assert "Nominal Telemetry Acquisition - No active emergency triggers" not in resp

def test_02_personal_health_agent_failure_sets_incomplete_and_no_fabricated_vitals(base_request):
    """Verify Supervisor sets ASSESSMENT_INCOMPLETE and does not emit fabricated default vitals when PHA fails."""
    runner = SupervisorWorkflowRunner()
    with patch("supervisor.adapters.personal_health_adapter.PersonalHealthAdapter.run", side_effect=RuntimeError("PHA feature extraction failure")):
        result = runner.run_pipeline(base_request)

    fa = result.get("final_assessment") or {}
    assert result.get("workflow_status") == WorkflowCompletionStatus.PARTIALLY_COMPLETED.value
    assert fa.get("escalation_state") == "ASSESSMENT_INCOMPLETE"
    assert fa.get("overall_risk") == "INSUFFICIENT_DATA"

    agent_statuses = fa.get("agent_execution_statuses") or {}
    assert agent_statuses.get("personal_health_agent", {}).get("status") == "FAILED"

    resp = result.get("final_response") or ""
    assert "Health Assessment Incomplete" in resp
    assert "Physiological feature extraction was not completed" in resp
    assert "Heart rate is 72.0 bpm" not in resp

def test_03_both_subagents_fail_sets_workflow_failed(base_request):
    """Verify Supervisor marks workflow status as FAILED when both health and risk agents fail."""
    runner = SupervisorWorkflowRunner()
    with patch("supervisor.adapters.personal_health_adapter.PersonalHealthAdapter.run", side_effect=RuntimeError("PHA crash")), \
         patch("supervisor.adapters.risk_assessment_adapter.RiskAssessmentAdapter.run", side_effect=RuntimeError("RA crash")):
        result = runner.run_pipeline(base_request)

    fa = result.get("final_assessment") or {}
    assert result.get("workflow_status") == WorkflowCompletionStatus.FAILED.value
    assert fa.get("escalation_state") == "ASSESSMENT_UNAVAILABLE"
    assert fa.get("overall_risk") == "UNKNOWN"

def test_04_nominal_pipeline_execution_sets_no_trigger_detected(base_request):
    """Verify normal execution sets NO_TRIGGER_DETECTED without reassurance distortion."""
    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(base_request)

    fa = result.get("final_assessment") or {}
    assert result.get("workflow_status") in (WorkflowCompletionStatus.COMPLETED.value, WorkflowCompletionStatus.PARTIALLY_COMPLETED.value)
    assert fa.get("escalation_state") == "NO_TRIGGER_DETECTED"
    assert fa.get("overall_risk") in ("INSUFFICIENT_DATA", "LOW", "UNKNOWN")

    resp = result.get("final_response") or ""
    assert "Nominal Telemetry Acquisition" in resp
