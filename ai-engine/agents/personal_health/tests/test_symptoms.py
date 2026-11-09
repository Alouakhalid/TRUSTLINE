"""Unit tests for multi-modal symptom extraction across English and Arabic."""
import pytest
from personal_health.services.symptom_service import SymptomService
from personal_health.schemas.symptom_event import InputChannel, SymptomCategory, SymptomSeverity

def test_english_symptom_extraction():
    """Verify English text symptom processing."""
    svc = SymptomService()
    event, clar = svc.process_text_symptom(
        text="I am feeling severe chest pain and dizziness since 20 minutes ago",
        astronaut_id="AST-001",
        session_id="SES-001"
    )
    assert event is not None
    assert event.symptom_category in (SymptomCategory.CARDIORESPIRATORY, SymptomCategory.NEUROLOGICAL)
    assert event.severity in (SymptomSeverity.SEVERE, SymptomSeverity.CRITICAL)
    assert event.input_channel == InputChannel.CHAT_TEXT

def test_arabic_symptom_extraction():
    """Verify Arabic symptom extraction."""
    svc = SymptomService()
    event, clar = svc.process_text_symptom(
        text="أشعر بصداع خفيف وإرهاق ذهني بعد العمل في المحطة",
        astronaut_id="AST-002",
        session_id="SES-002"
    )
    assert event is not None
    assert event.symptom_category in (SymptomCategory.NEUROLOGICAL, SymptomCategory.GENERAL)
    assert event.severity == SymptomSeverity.MILD

def test_structured_symptom_processing():
    """Verify structured form symptom processing."""
    svc = SymptomService()
    payload = {
        "symptom_category": "GASTROINTESTINAL",
        "symptom_type": "nausea",
        "severity": "MODERATE",
        "description": "Transient motion-induced nausea"
    }
    event = svc.process_structured_symptom(
        data=payload,
        astronaut_id="AST-001",
        session_id="SES-001"
    )
    assert event.symptom_category == SymptomCategory.GASTROINTESTINAL
    assert event.severity == SymptomSeverity.MODERATE
    assert event.input_channel == InputChannel.STRUCTURED_FORM
