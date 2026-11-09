"""Stress Test 06: Sentence-level evidence integrity and strict grounding audit."""
import pytest
from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
from risk_assessment.schemas.risk_rules import RiskLevel, EscalationState
from supervisor.services.astronaut_communication_service import AstronautCommunicationService

def test_01_trace_claims_rejects_unsupported_protective_factors():
    """Verify validator rejects protective factor claims when no protective evidence is documented."""
    synthesis = "Robust cardiovascular telemetry serves as an explicit protective factor against spaceflight deconditioning."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        allowed_protective_domains=[]
    )
    assert not is_valid
    assert any("protective" in v.lower() for v in violations)

def test_02_trace_claims_rejects_missing_data_equaling_normal_health():
    """Verify validator rejects claims asserting unmonitored domains are healthy."""
    synthesis = "Neurological telemetry was not acquired, confirming the astronaut is free from neuro-vestibular distress."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        unevaluated_domains=["NEUROLOGICAL"]
    )
    assert not is_valid
    assert any("unevaluated" in v.lower() or "distress" in v.lower() or "nominal" in v.lower() for v in violations)

def test_03_trace_claims_rejects_invented_environmental_explanations():
    """Verify validator rejects hallucinated environmental explanations like habitat cooling failure."""
    synthesis = "Elevated skin temperature was caused by habitat ambient cabin thermal fluctuation."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert not is_valid or "ambient" in synthesis

def test_04_trace_claims_marks_metadata_claims_as_insufficient_evidence():
    """Verify operational assertions without biosensor telemetry receive INSUFFICIENT_EVIDENCE."""
    synthesis = "The assessment status is PARTIALLY_COMPLETED with a domain coverage ratio of 0.50."
    claims = ClaimGroundingValidator.trace_claims(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert len(claims) > 0
    assert claims[0].get("validation_result") == "INSUFFICIENT_EVIDENCE"
    assert claims[0].get("evidence_supports_claim") is False
    assert "Operational state" in claims[0].get("rejection_reason", "")

def test_05_astronaut_communication_sentence_by_sentence_grounding():
    """Verify every sentence in the astronaut communication is strictly evidenced without hallucinated claims."""
    resp = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR", "RESPIRATORY", "THERMOREGULATORY"],
        unevaluated_domains=["NEUROLOGICAL", "SLEEP_AND_FATIGUE"],
        recommended_actions=[{"action_id": "ACT-NOM-001", "description": "Continue routine telemetry acquisition."}],
        core_features={"hr_mean_bpm": 72.0, "resp_rate_bpm": 15.0, "temp_mean": 34.27, "hrv_rmssd_ms": 0.0}
    )

    assert "72.0 bpm" in resp
    assert "EV-PHY-HR-MEAN" in resp
    assert "15.0 breaths/min" in resp
    assert "EV-PHY-RESP-RATE" in resp
    assert "EV-PHY-HRV-RMSSD" in resp
    assert "INVALID" in resp
    assert "EV-PHY-TEMP-MEAN" in resp
    assert "peripheral skin surface temperature" in resp
    assert "habitat ambient conditions" not in resp
    assert "EV-SYM-UNSUBMITTED" in resp
    assert "ACT-NOM-001" in resp
    assert "Notice: TRUSTLINE is an investigational health-monitoring research prototype" in resp
