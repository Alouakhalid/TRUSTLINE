"""Stress Test 05: Risk Assessment Agent failure modes and safety fallbacks."""
from unittest.mock import patch
import pytest
from supervisor.adapters.risk_assessment_adapter import RiskAssessmentAdapter
from supervisor.schemas.assessment import AgentExecutionState
from supervisor.workflow.graph import SupervisorWorkflowRunner

def test_01_ra_timeout_isolated_cleanly():
    """Verify Risk Assessment timeout is isolated and does not crash the orchestrator."""
    adapter = RiskAssessmentAdapter()

    def _slow_ra(state):
        raise TimeoutError("Risk Assessment timed out during multi-domain evaluation")

    with patch.object(adapter, "run", side_effect=_slow_ra):
        updates, status = adapter.execute_with_telemetry({})

    assert status.status == AgentExecutionState.FAILED
    assert "timed out" in status.error_message.lower()

def test_02_ra_rule_engine_exception_does_not_default_to_low_risk():
    """Verify an uncaught exception in Risk Assessment prevents false nominal LOW risk assignment."""
    runner = SupervisorWorkflowRunner()

    with patch("supervisor.adapters.risk_assessment_adapter.RiskAssessmentAdapter.run", side_effect=ZeroDivisionError("Rule weight denominator zero")):
        result = runner.run_pipeline(initial_state={
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001",
            "sensor_quality_result": {"overall_quality_score": 0.8},
            "personal_health_result": {"core_features": {"hr_mean_bpm": 72.0}}
        })

    agent_statuses = result.get("agent_execution_status") or {}
    ra_status = agent_statuses.get("risk_assessment_agent", {})
    assert ra_status.get("status") == "FAILED"
    assert "Rule weight denominator zero" in ra_status.get("error_message", "")

    final_assessment = result.get("final_assessment") or {}
    assert final_assessment.get("overall_risk") != "LOW"
    assert final_assessment.get("overall_risk") in ("INSUFFICIENT_DATA", "UNKNOWN", "INDETERMINATE")

def test_03_missing_escalation_fields_safely_handled():
    """Verify malformed escalation payload from RA does not cause unhandled crash in supervisor."""
    runner = SupervisorWorkflowRunner()

    malformed_ra = {
        "assessment_status": "PARTIALLY_COMPLETED",
        "overall_risk": "INSUFFICIENT_DATA",
        "overall_confidence": "LOW",
        "coverage": {
            "total_domains": 10,
            "domain_coverage_ratio": 0.1,
            "evaluated_domains": [],
            "unevaluated_domains": ["CARDIOVASCULAR"]
        },
        "escalation": None,
        "recommended_actions": []
    }

    result = runner.run_pipeline(initial_state={
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "risk_assessment_result": malformed_ra
    })

    assert result.get("current_step") == "FINAL_RESPONSE"
    assert "completed" in result.get("timestamps", {})
    final_assessment = result.get("final_assessment") or {}
    assert final_assessment.get("overall_risk") == "INSUFFICIENT_DATA"

def test_04_claims_referencing_quarantined_evidence_fail_validation():
    """Verify validator rejects assertions claiming health based on quarantined evidence."""
    from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
    from risk_assessment.schemas.risk_rules import RiskLevel, EscalationState

    synthesis_with_invalid_claim = (
        "Astronaut heart rate variability (RMSSD 0.0 ms) confirms robust parasympathetic cardiovascular stability."
    )

    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis_with_invalid_claim,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )

    claims = ClaimGroundingValidator.trace_claims(
        text=synthesis_with_invalid_claim,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )

    assert len(claims) > 0
    clm = claims[0]
    assert clm.get("evidence_validity") == "INVALID"
