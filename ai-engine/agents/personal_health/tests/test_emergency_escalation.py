"""Unit tests for emergency red-line detection and immediate safety escalation bypass."""
import pytest
from datetime import datetime
from personal_health.services.escalation_service import EmergencyEscalationService
from personal_health.schemas.symptom_event import SymptomEvent, InputChannel, SymptomCategory, SymptomSeverity

def test_chest_pain_emergency_escalation():
    """Verify immediate critical escalation on acute chest pain."""
    svc = EmergencyEscalationService()
    symptom = SymptomEvent(
        event_id="SYM-EMERG-01",
        astronaut_id="AST-001",
        session_id="SES-001",
        symptom_category=SymptomCategory.CARDIORESPIRATORY,
        symptom_type="chest_pain",
        description="Crushing retrosternal chest pain radiating to left arm",
        severity=SymptomSeverity.CRITICAL,
        input_channel=InputChannel.CHAT_TEXT,
        original_text_or_transcript="Severe crushing chest pain",
        event_timestamp=datetime.utcnow()
    )
    escalation = svc.evaluate_immediate_escalation(symptoms=[symptom])
    assert escalation.required is True
    assert escalation.urgency_level == "CRITICAL"
    assert "EMERGENCY_CHEST_PAIN" in escalation.reason_codes
    assert len(escalation.immediate_actions) > 0

def test_extreme_tachycardia_telemetry_escalation():
    """Verify extreme resting tachycardia (>160 bpm) triggers emergency alert."""
    svc = EmergencyEscalationService()
    escalation = svc.evaluate_immediate_escalation(
        symptoms=[],
        telemetry_features={"hr_mean_bpm": 172.5}
    )
    assert escalation.required is True
    assert "EMERGENCY_EXTREME_TACHYCARDIA" in escalation.reason_codes

def test_nominal_telemetry_no_escalation():
    """Verify nominal state does not trigger escalation."""
    svc = EmergencyEscalationService()
    escalation = svc.evaluate_immediate_escalation(
        symptoms=[],
        telemetry_features={"hr_mean_bpm": 70.0}
    )
    assert escalation.required is False
    assert escalation.urgency_level in ("NOMINAL", "NO_EMERGENCY_TRIGGER")
