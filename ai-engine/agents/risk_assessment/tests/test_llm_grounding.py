"""Unit tests for Risk Assessment LLM claim grounding validation and deterministic fallback."""
import pytest
from unittest.mock import MagicMock, patch
from groq import APITimeoutError, RateLimitError
from risk_assessment.schemas.risk_rules import RiskLevel, EscalationState
from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
from risk_assessment.services.llm_interpretation_service import LLMInterpretationService

def test_01_valid_grounded_synthesis():
    """Verify scientifically cautious clinical synthesis text passes grounding audit."""
    valid_text = (
        "Multi-agent risk assessment for Astronaut AST-001 indicates moderate resting tachycardia. "
        "Heart rate is measured at 112 bpm with valid ECG signal integrity. "
        "Flight Surgeon review is recommended in accordance with NASA-STD-3001."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=valid_text,
        overall_risk=RiskLevel.MODERATE,
        escalation_state=EscalationState.REVIEW_REQUIRED,
        mission_day_supplied=False
    )
    assert is_valid is True
    assert len(violations) == 0

def test_02_rejection_of_forbidden_clinical_diagnoses():
    """Verify diagnosis leap claims like myocardial infarction or pneumonia are rejected."""
    unsupported_text = (
        "The patient is experiencing an acute myocardial infarction and should be diagnosed with heart failure."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=unsupported_text,
        overall_risk=RiskLevel.CRITICAL,
        escalation_state=EscalationState.ESCALATION_REQUIRED,
        mission_day_supplied=False
    )
    assert is_valid is False
    assert any("myocardial infarction" in v for v in violations)
    assert any("diagnosed with" in v for v in violations)

def test_03_rejection_of_ungrounded_causal_attributions():
    """Verify ungrounded speculative causal leaps regarding fluid redistribution are rejected."""
    causal_text = (
        "Cephalad fluid redistribution caused the observed tachycardia during orbital adaptation."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=causal_text,
        overall_risk=RiskLevel.MODERATE,
        escalation_state=EscalationState.REVIEW_REQUIRED,
        mission_day_supplied=False
    )
    assert is_valid is False
    assert any("cephalad fluid redistribution caused" in v for v in violations)

def test_04_rejection_of_hallucinated_mission_day():
    """Verify hallucination of mission days is rejected when mission context is unsupplied."""
    hallucinated_text = (
        "Astronaut health profile observed on mission day 24 demonstrates stable circadian rhythms."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=hallucinated_text,
        overall_risk=RiskLevel.LOW,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        mission_day_supplied=False
    )
    assert is_valid is False
    assert any("mission day" in v.lower() for v in violations)

def test_05_rejection_of_contradictory_risk_claims():
    """Verify synthesis claiming low risk is rejected when deterministic risk is CRITICAL."""
    contradictory_text = (
        "The astronaut presents nominal health with low risk and no medical concerns."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=contradictory_text,
        overall_risk=RiskLevel.CRITICAL,
        escalation_state=EscalationState.ESCALATION_REQUIRED,
        mission_day_supplied=False
    )
    assert is_valid is False
    assert any("contradicts deterministic overall risk" in v for v in violations)

def test_06_rejection_of_contradictory_escalation_claims():
    """Verify synthesis claiming no escalation is rejected when ESCALATION_REQUIRED is active."""
    contradictory_text = (
        "Parameter deviations noted, but routine monitoring only with no escalation required."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=contradictory_text,
        overall_risk=RiskLevel.CRITICAL,
        escalation_state=EscalationState.ESCALATION_REQUIRED,
        mission_day_supplied=False
    )
    assert is_valid is False
    assert any("contradicts mandatory ESCALATION_REQUIRED" in v for v in violations)

def test_07_deterministic_fallback_when_unavailable():
    """Verify deterministic 3-paragraph fallback is returned when Groq client is unavailable."""
    service = LLMInterpretationService(api_key="")
    text, status = service.generate_explanation(
        astronaut_id="AST-001",
        session_id="S-001",
        overall_risk=RiskLevel.MODERATE,
        overall_confidence="HIGH",
        escalation_state=EscalationState.REVIEW_REQUIRED,
        escalation_reason="Resting heart rate elevated",
        domain_summaries=[],
        concerns=[{"title": "Moderate Tachycardia"}],
        protective_factors=["No acute symptoms reported."],
        uncertainties=["Mission day context unsupplied."],
        missing_info=[]
    )
    assert status == "LLM_UNAVAILABLE"
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    assert len(paragraphs) == 3
    assert "AST-001" in text
    assert "MODERATE" in text
    assert "REVIEW_REQUIRED" in text

def test_08_deterministic_fallback_on_api_timeout():
    """Verify fallback is returned when API timeout occurs."""
    service = LLMInterpretationService(api_key="gsk-mock-key")
    with patch.object(service._client.chat.completions, "create") as mock_create:
        mock_create.side_effect = APITimeoutError(request=MagicMock())
        text, status = service.generate_explanation(
            astronaut_id="AST-001",
            session_id="S-001",
            overall_risk=RiskLevel.LOW,
            overall_confidence="HIGH",
            escalation_state=EscalationState.NO_TRIGGER_DETECTED,
            escalation_reason="Nominal telemetry",
            domain_summaries=[],
            concerns=[],
            protective_factors=[],
            uncertainties=[],
            missing_info=[]
        )
        assert status == "LLM_TIMEOUT"
        assert len(text.split("\n\n")) == 3

def test_09_grounding_failure_triggers_fallback():
    """Verify that if LLM returns a hallucinated diagnosis, fallback text is returned with LLM_GROUNDING_FAILED."""
    service = LLMInterpretationService(api_key="gsk-mock-key")
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content="Astronaut has a severe myocardial infarction."))
    ]
    with patch.object(service._client.chat.completions, "create", return_value=mock_resp):
        text, status = service.generate_explanation(
            astronaut_id="AST-001",
            session_id="S-001",
            overall_risk=RiskLevel.CRITICAL,
            overall_confidence="HIGH",
            escalation_state=EscalationState.ESCALATION_REQUIRED,
            escalation_reason="Red-line chest pain",
            domain_summaries=[],
            concerns=[],
            protective_factors=[],
            uncertainties=[],
            missing_info=[]
        )
        assert status == "LLM_GROUNDING_FAILED"
        assert "myocardial infarction" not in text
        assert "CRITICAL" in text
