"""Stress Test 03: Symptom intelligence, multilingual input, emergency escalation, and communication."""
import pytest
from personal_health.services.escalation_service import EmergencyEscalationService
from personal_health.services.symptom_service import SymptomService
from personal_health.schemas.symptom_event import SymptomEvent, SymptomSeverity, SymptomCategory, InputChannel
from supervisor.services.astronaut_communication_service import AstronautCommunicationService
from supervisor.services.evidence_registry_service import EvidenceRegistryService

def test_01_no_symptoms_submitted_never_interpreted_as_no_symptoms():
    """Verify unsubmitted symptoms generate EV-SYM-UNSUBMITTED with explicit unassessed status."""
    state = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "personal_health_result": {"symptom_findings": []}
    }
    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    item = next((i for i in registry if i.evidence_id == "EV-SYM-UNSUBMITTED"), None)
    assert item is not None
    assert item.validity_status == "NOT_AVAILABLE"
    assert "unknown symptom status" in item.quarantine_reason

    resp = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR"],
        unevaluated_domains=[],
        recommended_actions=[],
        symptoms_reported=None
    )
    assert "EV-SYM-UNSUBMITTED" in resp
    assert "must not be interpreted as a confirmed clinical absence" in resp

def test_02_explicitly_submitted_severe_chest_pain_triggers_emergency_escalation():
    """Verify red-line symptom severe chest pain triggers immediate emergency escalation."""
    esc_service = EmergencyEscalationService()
    symptoms = [
        SymptomEvent(
            event_id="SYM-001",
            astronaut_id="AST-001",
            session_id="SESSION-001",
            symptom_type="chest_pain",
            symptom_category=SymptomCategory.CARDIORESPIRATORY,
            severity=SymptomSeverity.SEVERE,
            description="Severe crushing chest pain radiating to left shoulder",
            input_channel=InputChannel.CHAT_TEXT,
            original_text_or_transcript="Severe crushing chest pain radiating to left shoulder"
        )
    ]
    esc = esc_service.evaluate_immediate_escalation(symptoms=symptoms)
    assert esc.required is True
    assert esc.urgency_level == "CRITICAL"
    assert "EMERGENCY_CHEST_PAIN" in esc.reason_codes

    resp = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="HIGH",
        escalation_state="ESCALATION_REQUIRED",
        escalation_required=True,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR"],
        unevaluated_domains=[],
        recommended_actions=[],
        symptoms_reported=[s.model_dump() for s in symptoms]
    )
    assert "Priority Medical Notice" in resp
    assert "Crew Medical Officer" in resp or "Flight Surgeon" in resp

def test_03_shortness_of_breath_triggers_escalation():
    """Verify severe shortness of breath triggers cardiorespiratory escalation."""
    esc_service = EmergencyEscalationService()
    symptoms = [
        SymptomEvent(
            event_id="SYM-002",
            astronaut_id="AST-001",
            session_id="SESSION-001",
            symptom_type="shortness_of_breath",
            symptom_category=SymptomCategory.CARDIORESPIRATORY,
            severity=SymptomSeverity.SEVERE,
            description="Severe shortness of breath at rest with air hunger",
            input_channel=InputChannel.CHAT_TEXT,
            original_text_or_transcript="Severe shortness of breath at rest with air hunger"
        )
    ]
    esc = esc_service.evaluate_immediate_escalation(symptoms=symptoms)
    assert esc.required is True
    assert "EMERGENCY_RESPIRATORY_DISTRESS" in esc.reason_codes or "EMERGENCY_CRITICAL_CARDIORESPIRATORY" in esc.reason_codes

def test_04_arabic_red_line_symptom_triggers_escalation():
    """Verify Arabic red-line phrases trigger emergency escalation."""
    esc_service = EmergencyEscalationService()
    symptoms = [
        SymptomEvent(
            event_id="SYM-003",
            astronaut_id="AST-001",
            session_id="SESSION-001",
            symptom_type="chest_pain",
            symptom_category=SymptomCategory.CARDIORESPIRATORY,
            severity=SymptomSeverity.SEVERE,
            description="اشعر بألم شديد ووجع في الصدر مستمر",
            input_channel=InputChannel.CHAT_TEXT,
            original_text_or_transcript="اشعر بألم شديد ووجع في الصدر مستمر"
        )
    ]
    esc = esc_service.evaluate_immediate_escalation(symptoms=symptoms)
    assert esc.required is True
    assert "EMERGENCY_CHEST_PAIN" in esc.reason_codes

def test_05_dizziness_and_headache_handled_without_unauthorized_diagnosis():
    """Verify neurological symptoms are recorded factually without fabricating diagnostic labels."""
    symptoms = [
        {"symptom_type": "dizziness", "severity": "moderate"},
        {"symptom_type": "severe_headache", "severity": "severe"}
    ]
    resp = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="ELEVATED",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR"],
        unevaluated_domains=[],
        recommended_actions=[],
        symptoms_reported=symptoms
    )
    assert "dizziness" in resp
    assert "severe_headache" in resp
    assert "stroke" not in resp.lower()
    assert "myocardial infarction" not in resp.lower()

def test_06_ambiguous_and_malformed_symptom_handling():
    """Verify ambiguous or malformed payloads do not crash the communication service."""
    malformed = [
        {"symptom_type": None, "severity": None},
        {"description": "feeling slightly off balance"}
    ]
    resp = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR"],
        unevaluated_domains=[],
        recommended_actions=[],
        symptoms_reported=malformed
    )
    assert "Reported Symptoms" in resp
    assert len(resp) > 100
