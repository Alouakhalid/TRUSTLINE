"""Semantic evidence traceability negative tests for ClaimGroundingValidator."""
import pytest
from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
from risk_assessment.schemas.risk_rules import RiskLevel, EscalationState

@pytest.fixture
def nominal_evidence_registry():
    return [
        {
            "evidence_id": "EV-SQ-ECG",
            "source_agent": "sensor_quality_agent",
            "domain": "DATA_QUALITY_RELATED",
            "metric_name": "ECG_quality_score",
            "observed_value": 0.95,
            "validity_status": "VALID",
            "is_quarantined": False,
            "provenance": "Sensor Quality Agent DSP Pipeline (ECG)"
        },
        {
            "evidence_id": "EV-PHY-HR-MEAN",
            "source_agent": "personal_health_agent",
            "domain": "CARDIOVASCULAR",
            "metric_name": "heart_rate_mean",
            "observed_value": 72.0,
            "unit": "bpm",
            "validity_status": "VALID",
            "is_quarantined": False,
            "provenance": "Personal Health Agent ECG Core-14 Extraction"
        },
        {
            "evidence_id": "EV-PHY-HRV-RMSSD",
            "source_agent": "personal_health_agent",
            "domain": "CARDIOVASCULAR",
            "metric_name": "hrv_rmssd",
            "observed_value": 0.0,
            "unit": "ms",
            "validity_status": "INVALID",
            "is_quarantined": True,
            "provenance": "Personal Health Agent ECG R-Peak Timing"
        },
        {
            "evidence_id": "EV-PHY-RESP-RATE",
            "source_agent": "personal_health_agent",
            "domain": "RESPIRATORY",
            "metric_name": "respiratory_rate",
            "observed_value": 15.0,
            "unit": "breaths/min",
            "validity_status": "VALID",
            "is_quarantined": False,
            "provenance": "Personal Health Agent Respiration Peak Frequency Analysis"
        },
        {
            "evidence_id": "EV-PHY-TEMP-MEAN",
            "source_agent": "personal_health_agent",
            "domain": "THERMOREGULATORY",
            "metric_name": "temperature_mean",
            "observed_value": 34.27,
            "unit": "°C",
            "validity_status": "DEGRADED",
            "is_quarantined": False,
            "provenance": "Personal Health Agent Thermal Telemetry"
        }
    ]

def test_negative_01_nonexistent_evidence_id_rejected(nominal_evidence_registry):
    """Verify validator actively rejects claims citing an Evidence ID not present in the registry."""
    synthesis = "Continuous monitoring under EV-PHY-NONEXISTENT confirms nominal hemodynamic regulation."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        evidence_items=nominal_evidence_registry
    )
    assert not is_valid
    assert any("non-existent evidence id" in v.lower() for v in violations)

def test_negative_02_vital_numerical_value_mismatch_rejected(nominal_evidence_registry):
    """Verify validator rejects claims stating vital values that contradict empirical evidence."""
    synthesis = "Telemetry confirms a heart rate of 215 bpm within the monitoring window."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        evidence_items=nominal_evidence_registry
    )
    assert not is_valid
    assert any("contradicts empirical evidence value" in v.lower() and "heart rate" in v.lower() for v in violations)

def test_negative_03_contradictory_evidence_claiming_nominal_rejected():
    """Verify validator rejects nominal assertions when empirical evidence shows critical tachycardia."""
    tachy_registry = [
        {
            "evidence_id": "EV-PHY-HR-MEAN",
            "source_agent": "personal_health_agent",
            "domain": "CARDIOVASCULAR",
            "metric_name": "heart_rate_mean",
            "observed_value": 185.0,
            "validity_status": "VALID",
            "is_quarantined": False,
            "provenance": "Personal Health Agent ECG Core-14 Extraction"
        }
    ]
    synthesis = "Cardiac telemetry is nominal with heart rate within established reference limits."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis,
        overall_risk=RiskLevel.HIGH,
        escalation_state=EscalationState.ESCALATION_REQUIRED,
        evidence_items=tachy_registry
    )
    assert not is_valid
    assert any("critical" in v.lower() or "abnormal" in v.lower() or "contradicts" in v.lower() for v in violations)

def test_negative_04_quarantined_evidence_claiming_nominal_rejected(nominal_evidence_registry):
    """Verify validator rejects claims asserting valid or normal status based on quarantined evidence."""
    synthesis = "Normal HRV under EV-PHY-HRV-RMSSD demonstrates intact autonomic cardiovascular regulation."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        evidence_items=nominal_evidence_registry
    )
    assert not is_valid
    assert any("quarantined or invalid" in v.lower() or "zero-variability" in v.lower() for v in violations)

def test_negative_05_unmeasured_vital_sign_assertion_rejected(nominal_evidence_registry):
    """Verify validator rejects assertions claiming specific unmeasured vitals (e.g. blood pressure)."""
    synthesis = "Astronaut blood pressure is 120/80 mmHg reflecting stable cardiovascular tone."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        evidence_items=nominal_evidence_registry
    )
    assert not is_valid
    assert any("unmeasured parameter" in v.lower() and "blood pressure" in v.lower() for v in violations)

def test_negative_06_trace_claims_fails_quarantined_and_mismatched(nominal_evidence_registry):
    """Verify trace_claims marks contradictory and ungrounded claims with validation_result FAIL."""
    synthesis = (
        "Astronaut heart rate is 215 bpm according to monitoring data.\n\n"
        "Heart rate variability under EV-PHY-HRV-RMSSD is nominal."
    )
    claims = ClaimGroundingValidator.trace_claims(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        evidence_items=nominal_evidence_registry
    )
    assert len(claims) == 2
    for claim in claims:
        assert claim["validation_result"] == "FAIL"
        assert claim["evidence_supports_claim"] is False
        assert claim["rejection_reason"] is not None
