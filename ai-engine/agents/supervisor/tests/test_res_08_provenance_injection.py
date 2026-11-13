"""Tests verifying strict provenance validation and quarantine for unprovenanced evidence items (RES-08)."""
import pytest
from supervisor.services.evidence_registry_service import EvidenceRegistryService
from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
from risk_assessment.schemas.risk_rules import RiskLevel, EscalationState

def test_01_missing_provenance_string_is_quarantined():
    """Verify evidence items with empty provenance string are actively quarantined."""
    state = {
        "sensor_quality_result": {},
        "personal_health_result": {"core_features": {"hr_mean_bpm": 70.0}},
        "injected_evidence": [
            {
                "evidence_id": "EV-INJ-EMPTY-PROV",
                "source_agent": "personal_health_agent",
                "domain": "CARDIOVASCULAR",
                "metric_name": "heart_rate_mean",
                "observed_value": 70.0,
                "validity_status": "VALID",
                "provenance": ""
            }
        ]
    }
    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    item = next((i for i in registry if i.evidence_id == "EV-INJ-EMPTY-PROV"), None)
    assert item is not None
    assert item.is_quarantined is True
    assert item.validity_status == "INVALID"
    assert "provenance audit failure" in item.quarantine_reason.lower()

def test_02_unknown_source_agent_is_quarantined():
    """Verify evidence items with source_agent UNKNOWN are actively quarantined."""
    state = {
        "sensor_quality_result": {},
        "personal_health_result": {},
        "injected_evidence": [
            {
                "evidence_id": "EV-INJ-UNKNOWN-AGENT",
                "source_agent": "UNKNOWN",
                "domain": "CARDIOVASCULAR",
                "metric_name": "unknown_signal",
                "observed_value": 42.0,
                "validity_status": "VALID",
                "provenance": "Some provenance"
            }
        ]
    }
    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    item = next((i for i in registry if i.evidence_id == "EV-INJ-UNKNOWN-AGENT"), None)
    assert item is not None
    assert item.is_quarantined is True
    assert item.validity_status == "INVALID"
    assert "provenance audit failure" in item.quarantine_reason.lower()

def test_03_malformed_provenance_causes_downstream_claim_failure():
    """Verify downstream claims referencing quarantined unprovenanced evidence are rejected."""
    state = {
        "sensor_quality_result": {},
        "personal_health_result": {},
        "injected_evidence": [
            {
                "evidence_id": "EV-INJ-MALFORMED",
                "source_agent": "UNKNOWN",
                "domain": "CARDIOVASCULAR",
                "metric_name": "heart_rate_mean",
                "observed_value": 72.0,
                "validity_status": "VALID",
                "provenance": ""
            }
        ]
    }
    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    synthesis = "Nominal cardiovascular status is confirmed by EV-INJ-MALFORMED."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=synthesis,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        evidence_items=[i.model_dump() for i in registry]
    )
    assert not is_valid
    assert any("quarantined" in v.lower() or "invalid" in v.lower() for v in violations)

def test_04_fully_provenanced_evidence_remains_valid():
    """Verify evidence items with complete provenance pass audit without quarantine."""
    state = {
        "sensor_quality_result": {},
        "personal_health_result": {},
        "injected_evidence": [
            {
                "evidence_id": "EV-INJ-VALID",
                "source_agent": "personal_health_agent",
                "domain": "CARDIOVASCULAR",
                "metric_name": "heart_rate_mean",
                "observed_value": 72.0,
                "validity_status": "VALID",
                "provenance": "Personal Health Agent Valid ECG Trace"
            }
        ]
    }
    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    item = next((i for i in registry if i.evidence_id == "EV-INJ-VALID"), None)
    assert item is not None
    assert item.is_quarantined is False
    assert item.validity_status == "VALID"
