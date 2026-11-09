"""Stress Test 07: Conflicting agent outputs, authority enforcement, and conflict preservation."""
import pytest
from supervisor.services.evidence_registry_service import EvidenceRegistryService
from personal_health.services.escalation_service import EmergencyEscalationService
from personal_health.schemas.symptom_event import SymptomEvent, SymptomSeverity, SymptomCategory, InputChannel
from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
from risk_assessment.schemas.risk_rules import RiskLevel, EscalationState

def test_01_sqr_marks_ecg_invalid_quarantines_pha_cardiac_telemetry():
    """Verify that when Sensor Quality marks ECG INVALID, the Evidence Registry quarantines derived PHA metrics."""
    state = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "sensor_quality_result": {
            "overall_quality_score": 0.35,
            "sensors": {
                "ECG": {
                    "status": "INVALID",
                    "quality_score": 0.20,
                    "critical_failure": True
                }
            }
        },
        "personal_health_result": {
            "core_features": {
                "hr_mean_bpm": 74.0,
                "hrv_rmssd_ms": 32.0
            },
            "hrv_diagnostics": {
                "hrv_status": "VALID"
            }
        }
    }

    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    hr_item = next((i for i in registry if i.evidence_id == "EV-PHY-HR-MEAN"), None)
    rmssd_item = next((i for i in registry if i.evidence_id == "EV-PHY-HRV-RMSSD"), None)

    assert hr_item is not None
    assert hr_item.is_quarantined is True
    assert hr_item.validity_status == "INVALID"
    assert "quarantined by DSP inspection" in hr_item.quarantine_reason or "Source ECG signal marked INVALID" in hr_item.quarantine_reason

    assert rmssd_item is not None
    assert rmssd_item.is_quarantined is True
    assert rmssd_item.validity_status == "INVALID"

def test_02_symptom_concern_overrides_nominal_telemetry_in_escalation():
    """Verify that an emergency red-line symptom triggers escalation even when vital signs appear nominal."""
    esc_service = EmergencyEscalationService()
    symptoms = [
        SymptomEvent(
            event_id="SYM-CONF-01",
            astronaut_id="AST-001",
            session_id="SESSION-001",
            symptom_type="chest_pain",
            symptom_category=SymptomCategory.CARDIORESPIRATORY,
            severity=SymptomSeverity.CRITICAL,
            description="Crushing retrosternal chest pain with diaphoresis",
            input_channel=InputChannel.CHAT_TEXT,
            original_text_or_transcript="Crushing retrosternal chest pain with diaphoresis"
        )
    ]
    nominal_features = {
        "hr_mean_bpm": 72.0,
        "resp_rate_bpm": 15.0,
        "temp_mean": 36.6
    }
    esc = esc_service.evaluate_immediate_escalation(
        symptoms=symptoms,
        telemetry_features=nominal_features,
        critical_sensors_available=True,
        sensor_quality_valid=True
    )

    assert esc.required is True
    assert esc.urgency_level == "CRITICAL"
    assert "EMERGENCY_CHEST_PAIN" in esc.reason_codes

def test_03_pha_insufficient_evidence_preserves_conflict_against_low_risk():
    """Verify supervisor prevents premature LOW risk when upstream PHA reported insufficient evidence."""
    from supervisor.workflow.nodes import final_synthesis_node

    state = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "workflow_id": "WF-CONF-01",
        "personal_health_result": {
            "assessment_status": "INSUFFICIENT_EVIDENCE",
            "uncertainties": ["ECG signal was corrupted during acquisition"]
        },
        "risk_assessment_result": {
            "overall_risk": "INSUFFICIENT_DATA",
            "overall_confidence": "MODERATE",
            "assessment_status": "PARTIALLY_COMPLETED",
            "coverage": {
                "total_domains": 10,
                "domain_coverage_ratio": 0.4,
                "evaluated_domains": ["CARDIOVASCULAR"],
                "unevaluated_domains": ["RESPIRATORY", "NEUROLOGICAL"]
            },
            "escalation": {
                "state": "NO_TRIGGER_DETECTED",
                "required": False,
                "urgency_level": "NOMINAL"
            }
        }
    }

    updates = final_synthesis_node(state)
    final_assessment = updates["final_assessment"]
    assert final_assessment["overall_risk"] == "INSUFFICIENT_DATA"
    assert final_assessment["workflow_completion_status"] == "PARTIALLY_COMPLETED"
