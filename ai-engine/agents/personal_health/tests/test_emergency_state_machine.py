"""Test suite verifying the deterministic 4-state Emergency Escalation State Machine."""
from datetime import datetime
import pytest

from personal_health.services.escalation_service import EmergencyEscalationService
from personal_health.schemas.assessment import EmergencyAssessmentStatus
from personal_health.schemas.symptom_event import (
    SymptomEvent,
    InputChannel,
    SymptomCategory,
    SymptomSeverity
)

def make_symptom(symptom_type: str, description: str, category: SymptomCategory, severity: SymptomSeverity) -> SymptomEvent:
    """Helper creating a test SymptomEvent."""
    return SymptomEvent(
        event_id="SYM-TEST-001",
        astronaut_id="ASTRO-01",
        session_id="SESS-001",
        symptom_category=category,
        symptom_type=symptom_type,
        description=description,
        severity=severity,
        input_channel=InputChannel.CHAT_TEXT,
        original_text_or_transcript=description,
        event_timestamp=datetime.utcnow()
    )

def test_01_redline_chest_pain_escalation():
    """Verify red-line chest pain triggers ESCALATION_REQUIRED state."""
    svc = EmergencyEscalationService()
    sym = make_symptom("chest_pain", "Severe crushing chest pain", SymptomCategory.CARDIORESPIRATORY, SymptomSeverity.CRITICAL)
    esc = svc.evaluate_immediate_escalation(symptoms=[sym])

    assert esc.status == EmergencyAssessmentStatus.ESCALATION_REQUIRED
    assert esc.required is True
    assert esc.urgency_level == "CRITICAL"
    assert "EMERGENCY_CHEST_PAIN" in esc.reason_codes
    assert len(esc.immediate_actions) > 0

def test_02_redline_respiratory_distress_escalation():
    """Verify red-line respiratory distress triggers ESCALATION_REQUIRED state."""
    svc = EmergencyEscalationService()
    sym = make_symptom("dyspnea", "Astronaut cannot breathe and is gasping", SymptomCategory.CARDIORESPIRATORY, SymptomSeverity.CRITICAL)
    esc = svc.evaluate_immediate_escalation(symptoms=[sym])

    assert esc.status == EmergencyAssessmentStatus.ESCALATION_REQUIRED
    assert esc.required is True
    assert "EMERGENCY_RESPIRATORY_DISTRESS" in esc.reason_codes

def test_03_redline_syncope_escalation():
    """Verify loss of consciousness triggers ESCALATION_REQUIRED state."""
    svc = EmergencyEscalationService()
    sym = make_symptom("syncope", "Astronaut passed out during airlock egress", SymptomCategory.NEUROLOGICAL, SymptomSeverity.CRITICAL)
    esc = svc.evaluate_immediate_escalation(symptoms=[sym])

    assert esc.status == EmergencyAssessmentStatus.ESCALATION_REQUIRED
    assert esc.required is True
    assert "EMERGENCY_LOSS_OF_CONSCIOUSNESS" in esc.reason_codes

def test_04_redline_acute_neurological_escalation():
    """Verify acute neurological symptom triggers ESCALATION_REQUIRED state."""
    svc = EmergencyEscalationService()
    sym = make_symptom("neurological", "Observed facial drooping and slurred speech", SymptomCategory.NEUROLOGICAL, SymptomSeverity.SEVERE)
    esc = svc.evaluate_immediate_escalation(symptoms=[sym])

    assert esc.status == EmergencyAssessmentStatus.ESCALATION_REQUIRED
    assert esc.required is True
    assert "EMERGENCY_ACUTE_NEUROLOGICAL" in esc.reason_codes

def test_05_severe_cardiorespiratory_escalation():
    """Verify severe non-keyword cardiorespiratory symptom triggers escalation."""
    svc = EmergencyEscalationService()
    sym = make_symptom("bronchospasm", "Acute respiratory compromise", SymptomCategory.CARDIORESPIRATORY, SymptomSeverity.CRITICAL)
    esc = svc.evaluate_immediate_escalation(symptoms=[sym])

    assert esc.status == EmergencyAssessmentStatus.ESCALATION_REQUIRED
    assert esc.required is True
    assert "EMERGENCY_CRITICAL_CARDIORESPIRATORY" in esc.reason_codes

def test_06_extreme_tachycardia_escalation():
    """Verify resting heart rate exceeding 160 bpm triggers ESCALATION_REQUIRED."""
    svc = EmergencyEscalationService()
    esc = svc.evaluate_immediate_escalation(
        symptoms=[],
        telemetry_features={"hr_mean_bpm": 174.2}
    )

    assert esc.status == EmergencyAssessmentStatus.ESCALATION_REQUIRED
    assert esc.required is True
    assert "EMERGENCY_EXTREME_TACHYCARDIA" in esc.reason_codes

def test_07_extreme_bradycardia_escalation():
    """Verify resting heart rate below 40 bpm triggers ESCALATION_REQUIRED."""
    svc = EmergencyEscalationService()
    esc = svc.evaluate_immediate_escalation(
        symptoms=[],
        telemetry_features={"hr_mean_bpm": 35.8}
    )

    assert esc.status == EmergencyAssessmentStatus.ESCALATION_REQUIRED
    assert esc.required is True
    assert "EMERGENCY_EXTREME_BRADYCARDIA" in esc.reason_codes

def test_08_insufficient_data_missing_telemetry():
    """Verify omitting telemetry features results in INSUFFICIENT_DATA and preserves uncertainty."""
    svc = EmergencyEscalationService()
    esc = svc.evaluate_immediate_escalation(
        symptoms=[],
        telemetry_features=None
    )

    assert esc.status == EmergencyAssessmentStatus.INSUFFICIENT_DATA
    assert esc.required is False
    assert esc.urgency_level == "INDETERMINATE"
    assert len(esc.data_gaps) > 0
    assert len(esc.uncertainty_notes) > 0

def test_09_insufficient_data_degraded_sensors():
    """Verify quarantined sensors or failed sensor quality gates trigger INSUFFICIENT_DATA."""
    svc = EmergencyEscalationService()
    esc = svc.evaluate_immediate_escalation(
        symptoms=[],
        telemetry_features={"hr_mean_bpm": 72.0},
        critical_sensors_available=False,
        sensor_quality_valid=False
    )

    assert esc.status == EmergencyAssessmentStatus.INSUFFICIENT_DATA
    assert esc.required is False
    assert esc.urgency_level == "INDETERMINATE"
    assert any("quarantined" in g.lower() for g in esc.data_gaps)
    assert any("quality" in g.lower() for g in esc.data_gaps)

def test_10_nominal_no_trigger_detected():
    """Verify complete physiological telemetry with no triggers produces NO_TRIGGER_DETECTED."""
    svc = EmergencyEscalationService()
    esc = svc.evaluate_immediate_escalation(
        symptoms=[],
        telemetry_features={"hr_mean_bpm": 72.0},
        critical_sensors_available=True,
        sensor_quality_valid=True
    )

    assert esc.status == EmergencyAssessmentStatus.NO_TRIGGER_DETECTED
    assert esc.required is False
    assert esc.urgency_level in ("NOMINAL", "NO_EMERGENCY_TRIGGER")
    assert len(esc.reason_codes) == 0
    assert len(esc.triggers) == 0
    assert len(esc.data_gaps) == 0
