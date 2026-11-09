"""Unit tests for the Risk Assessment escalation state machine and action dispatcher."""
import pytest
from datetime import datetime
from risk_assessment.schemas.evidence import (
    RiskDomain,
    EvidenceSourceType,
    EvidenceValidity,
    NormalizedEvidenceItem
)
from risk_assessment.schemas.risk_rules import (
    RiskLevel,
    EscalationState,
    EscalationDestination,
    TriggeredRuleDetail
)
from risk_assessment.schemas.risk_input import RiskAssessmentInput
from risk_assessment.services.escalation_service import RiskEscalationService
from risk_assessment.agent.agent import RiskAssessmentAgent

def _make_triggered_rule(
    rule_id: str,
    name: str,
    domain: RiskDomain,
    level: RiskLevel,
    state: EscalationState,
    rationale: str
) -> TriggeredRuleDetail:
    """Helper building a TriggeredRuleDetail."""
    return TriggeredRuleDetail(
        rule_id=rule_id,
        rule_name=name,
        domain=domain,
        risk_level=level,
        supporting_evidence_ids=["EV-001"],
        rationale=rationale,
        suggested_escalation=state,
        rule_source="TEST-PROTOCOL"
    )

def test_01_escalation_state_no_trigger_detected():
    """Verify nominal state outputs NO_TRIGGER_DETECTED with astronaut self-monitoring."""
    esc_details, actions = RiskEscalationService.determine_escalation(
        triggered_rules=[],
        overall_risk=RiskLevel.LOW,
        evidence_items=[]
    )
    assert esc_details.state == EscalationState.NO_TRIGGER_DETECTED
    assert esc_details.required is False
    assert esc_details.destination == EscalationDestination.ASTRONAUT_SELF_MONITORING
    assert esc_details.urgency_level == "NOMINAL"
    assert len(actions) == 1
    assert actions[0].priority == "ROUTINE"

def test_02_escalation_state_insufficient_data():
    """Verify INSUFFICIENT_DATA risk yields INSUFFICIENT_DATA escalation with sensor recalibration action."""
    esc_details, actions = RiskEscalationService.determine_escalation(
        triggered_rules=[],
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        evidence_items=[]
    )
    assert esc_details.state == EscalationState.INSUFFICIENT_DATA
    assert esc_details.required is False
    assert esc_details.destination == EscalationDestination.FLIGHT_SURGEON
    assert esc_details.urgency_level == "ELEVATED"
    assert len(actions) == 1
    assert actions[0].action_type == "RECALIBRATION"
    assert actions[0].priority == "URGENT"

def test_03_escalation_state_assessment_failed():
    """Verify pipeline failure produces ASSESSMENT_FAILED state via agent safety handling."""
    agent = RiskAssessmentAgent()
    invalid_input = RiskAssessmentInput(
        astronaut_id="",
        session_id="S-001"
    )
    out = agent.assess(invalid_input)
    assert out.escalation.state == EscalationState.ASSESSMENT_FAILED
    assert "Input validation failed" in out.escalation.reason
    assert out.overall_risk == RiskLevel.UNKNOWN

def test_04_escalation_state_review_required():
    """Verify REVIEW_REQUIRED rule outputs REVIEW_REQUIRED state with Flight Surgeon destination."""
    rule = _make_triggered_rule(
        "RR-RESP-TACHYPNEA",
        "Resting Tachypnea",
        RiskDomain.RESPIRATORY,
        RiskLevel.MODERATE,
        EscalationState.REVIEW_REQUIRED,
        "Respiration rate elevated"
    )
    esc_details, actions = RiskEscalationService.determine_escalation(
        triggered_rules=[rule],
        overall_risk=RiskLevel.MODERATE,
        evidence_items=[]
    )
    assert esc_details.state == EscalationState.REVIEW_REQUIRED
    assert esc_details.required is False
    assert esc_details.urgency_level == "ELEVATED"
    assert esc_details.destination == EscalationDestination.FLIGHT_SURGEON
    assert len(actions) == 1
    assert actions[0].priority == "ROUTINE"

def test_05_escalation_state_escalation_recommended():
    """Verify ESCALATION_RECOMMENDED rule outputs ESCALATION_RECOMMENDED state with urgent Flight Surgeon alert."""
    rule = _make_triggered_rule(
        "RR-RESP-DYSPNEA-ALERT",
        "Respiratory Distress",
        RiskDomain.RESPIRATORY,
        RiskLevel.HIGH,
        EscalationState.ESCALATION_RECOMMENDED,
        "Subjective dyspnea reported"
    )
    esc_details, actions = RiskEscalationService.determine_escalation(
        triggered_rules=[rule],
        overall_risk=RiskLevel.HIGH,
        evidence_items=[]
    )
    assert esc_details.state == EscalationState.ESCALATION_RECOMMENDED
    assert esc_details.required is False
    assert esc_details.urgency_level == "URGENT"
    assert esc_details.destination == EscalationDestination.FLIGHT_SURGEON
    assert len(actions) == 1
    assert actions[0].priority == "URGENT"

def test_06_redline_chest_pain_escalation_required():
    """Verify acute severe chest pain triggers mandatory ESCALATION_REQUIRED and EMERGENCY_MEDICAL_RESPONSE."""
    rule = _make_triggered_rule(
        "RR-EMERG-CHEST-PAIN",
        "Acute Severe Chest Pain",
        RiskDomain.CARDIOVASCULAR,
        RiskLevel.CRITICAL,
        EscalationState.ESCALATION_REQUIRED,
        "Crushing chest sensation reported"
    )
    esc_details, actions = RiskEscalationService.determine_escalation(
        triggered_rules=[rule],
        overall_risk=RiskLevel.CRITICAL,
        evidence_items=[]
    )
    assert esc_details.state == EscalationState.ESCALATION_REQUIRED
    assert esc_details.required is True
    assert esc_details.urgency_level == "CRITICAL"
    assert esc_details.destination == EscalationDestination.EMERGENCY_MEDICAL_RESPONSE
    assert len(actions) == 1
    assert actions[0].priority == "CRITICAL"
    assert actions[0].action_type == "CMRS_DEPLOYMENT"

def test_07_extreme_tachycardia_escalation_required():
    """Verify resting heart rate exceeding 160 bpm triggers mandatory red-line escalation."""
    rule = _make_triggered_rule(
        "RR-CARDIO-TACHY-EXTREME",
        "Extreme Resting Tachycardia",
        RiskDomain.CARDIOVASCULAR,
        RiskLevel.CRITICAL,
        EscalationState.ESCALATION_REQUIRED,
        "Heart rate 165.0 bpm exceeds critical threshold 160.0 bpm"
    )
    esc_details, actions = RiskEscalationService.determine_escalation(
        triggered_rules=[rule],
        overall_risk=RiskLevel.CRITICAL,
        evidence_items=[]
    )
    assert esc_details.state == EscalationState.ESCALATION_REQUIRED
    assert esc_details.required is True
    assert esc_details.destination == EscalationDestination.EMERGENCY_MEDICAL_RESPONSE

def test_08_elevated_co2_environmental_escalation():
    """Verify elevated cabin CO2 triggers REVIEW_REQUIRED escalation with MISSION_CONTROL destination."""
    rule = _make_triggered_rule(
        "RR-ENV-CABIN-CO2-ELEVATED",
        "Elevated Atmospheric CO2",
        RiskDomain.RESPIRATORY,
        RiskLevel.MODERATE,
        EscalationState.REVIEW_REQUIRED,
        "Cabin CO2 exceeds 0.70%"
    )
    esc_details, actions = RiskEscalationService.determine_escalation(
        triggered_rules=[rule],
        overall_risk=RiskLevel.MODERATE,
        evidence_items=[]
    )
    assert esc_details.state == EscalationState.REVIEW_REQUIRED
    assert esc_details.required is False
    assert esc_details.destination == EscalationDestination.FLIGHT_SURGEON
