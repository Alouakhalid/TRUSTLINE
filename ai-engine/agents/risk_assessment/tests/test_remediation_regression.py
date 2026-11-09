"""Comprehensive regression test suite verifying Grounding Validator and Fallback Remediation."""
import pytest
from unittest.mock import MagicMock, patch
from risk_assessment.schemas.evidence import (
    RiskDomain,
    EvidenceSourceType,
    EvidenceValidity,
    NormalizedEvidenceItem
)
from risk_assessment.schemas.risk_rules import (
    RiskLevel,
    RiskConfidence,
    EscalationState,
    EscalationDestination
)
from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
from risk_assessment.services.llm_interpretation_service import LLMInterpretationService
from risk_assessment.services.risk_engine import RiskEngine

def test_scenario_a_negated_symptom_absence_positive():
    """Verify negated symptom absence phrasing is accepted when symptoms were unsubmitted."""
    text = (
        "Multi-agent risk assessment for Astronaut AST-001. "
        "Subjective symptom telemetry was not submitted (DATA_UNAVAILABLE), which represents "
        "a data gap rather than a confirmed absence of symptoms."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        symptoms_explicitly_denied=False
    )
    assert is_valid is True
    assert len(violations) == 0

def test_scenario_a_unnegated_symptom_absence_negative():
    """Verify unnegated symptom absence claim is rejected when symptoms were only unsubmitted."""
    text = (
        "Subjective clinical review completes with confirmed absence of symptoms in flight."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        symptoms_explicitly_denied=False
    )
    assert is_valid is False
    assert any("unconfirmed symptom denial" in v for v in violations)

def test_scenario_b_unevaluated_domain_modal_negation_positive():
    """Verify unevaluated domains with modal negation ('cannot be assumed nominal') are accepted."""
    text = (
        "Objective risk assessment completed. "
        "Unevaluated physiological domains (NEUROLOGICAL, HEMATOLOGIC, IMMUNOLOGICAL, COGNITIVE, GENERAL_PHYSIOLOGICAL) "
        "remain unmonitored and cannot be assumed nominal."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        unevaluated_domains=["neurological", "hematologic", "immunological", "cognitive", "general_physiological"]
    )
    assert is_valid is True
    assert len(violations) == 0

def test_scenario_b_unevaluated_domain_nominal_assertion_negative():
    """Verify asserting an unevaluated domain is nominal is rejected."""
    text = (
        "Mission physiological telemetry audit. "
        "Domain NEUROLOGICAL is nominal and exhibits fully intact neurological stability."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        unevaluated_domains=["neurological"]
    )
    assert is_valid is False
    assert any("unevaluated domain 'neurological'" in v.lower() for v in violations)

def test_scenario_c_evaluated_domains_low_risk_positive():
    """Verify low risk in evaluated domains is permitted when overall composite risk is INSUFFICIENT_DATA."""
    text = (
        "Although telemetry in evaluated physiological domains indicates low risk, "
        "composite overall risk classification is INSUFFICIENT_DATA due to partial sensor coverage."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is True
    assert len(violations) == 0

def test_scenario_c_overall_low_risk_contradiction_negative():
    """Verify claiming overall risk is low is rejected when engine overall risk is INSUFFICIENT_DATA."""
    text = (
        "Monitoring telemetry confirms that Astronaut AST-001 is evaluated at overall low risk."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is False
    assert any("contradicts deterministic overall risk" in v for v in violations)

def test_scenario_d_cardiovascular_inferred_from_respiratory_negative():
    """Verify claiming cardiovascular stability is inferred from respiratory observation is rejected."""
    text = (
        "Resting respiration rate is nominal, which confirms cardiovascular stability."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.LOW,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        allowed_protective_domains=["respiratory"]
    )
    assert is_valid is False
    assert any("infers cardiovascular stability from respiratory-only" in v for v in violations)

def test_scenario_d_respiratory_protective_isolated_positive():
    """Verify respiratory observation stated without cross-domain inference is accepted."""
    text = (
        "Resting respiration rate is 15 bpm within standard reference limits. "
        "Cardiovascular telemetry was not evaluated."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.LOW,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        allowed_protective_domains=["respiratory"]
    )
    assert is_valid is True
    assert len(violations) == 0

def test_scenario_e_protective_vs_nominal_observation_separation():
    """Verify resting respiration rate creates a NOMINAL_OBSERVATION and NOT a PROTECTIVE_FACTOR."""
    engine = RiskEngine()
    items = [
        NormalizedEvidenceItem(
            evidence_id="EV-RESP-01",
            source_agent="personal_health_agent",
            source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
            domain=RiskDomain.RESPIRATORY,
            metric_name="respiratory_rate",
            observed_value=15.0,
            unit="breaths/min",
            validity_status=EvidenceValidity.VALID,
            source_reference="PHA:resp",
            evidence_description="Respiration rate 15.0 bpm"
        )
    ]
    res = engine.evaluate_risks(items)
    assert len(res.nominal_observation_details) == 1
    obs = res.nominal_observation_details[0]
    assert obs.factor_id == "OBS-RESP-WNL-01"
    assert obs.factor_type == "NOMINAL_OBSERVATION"
    assert "15.0" in obs.explanation
    assert len(res.protective_factor_details) == 0
    assert len(res.protective_factors) == 0

def test_scenario_f_missing_subjective_inputs_in_fallback():
    """Verify fallback briefing explicitly reflects that subjective inputs were not submitted."""
    service = LLMInterpretationService(api_key="")
    text, status = service.generate_explanation(
        astronaut_id="AST-001",
        session_id="S-001",
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        overall_confidence="MODERATE",
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        escalation_reason="Nominal telemetry",
        domain_summaries=[],
        concerns=[],
        protective_factors=[],
        uncertainties=["Subjective symptoms were not submitted for this session."],
        missing_info=[],
        symptoms_submitted=False,
        nominal_observations=["Resting respiration rate nominal."]
    )
    assert status == "LLM_UNAVAILABLE"
    assert "subjective symptom data was not submitted" in text
    assert "Domain-specific evaluation reflects validated telemetry and subjective inputs." not in text
    assert "Nominal observations within reference limits" in text

def test_scenario_g_duplicate_uncertainty_and_punctuation_elimination():
    """Verify duplicate uncertainties are purged and punctuation joins do not create '..' or '.; '."""
    service = LLMInterpretationService(api_key="")
    raw_uncertainties = [
        "Subjective symptoms were not submitted for this session; general symptoms domain unevaluated.",
        "Subjective symptoms were not submitted for this session; general symptoms domain unevaluated..",
        "  subjective symptoms were not submitted for this session; general symptoms domain unevaluated.  ",
        "Sensor Quality Agent report not provided."
    ]
    text, _ = service.generate_explanation(
        astronaut_id="AST-001",
        session_id="S-001",
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        overall_confidence="MODERATE",
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        escalation_reason="Nominal",
        domain_summaries=[],
        concerns=[],
        protective_factors=[],
        uncertainties=raw_uncertainties,
        symptoms_submitted=False
    )
    assert ".." not in text
    assert ".; " not in text
    assert text.count("general symptoms domain unevaluated") == 1

def test_scenario_h_fallback_self_validation():
    """Verify deterministic fallback produced by service passes ClaimGroundingValidator self-validation."""
    service = LLMInterpretationService(api_key="")
    text, _ = service.generate_explanation(
        astronaut_id="AST-001",
        session_id="S-001",
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        overall_confidence="MODERATE",
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        escalation_reason="No trigger",
        domain_summaries=[],
        concerns=[],
        protective_factors=[],
        uncertainties=["Coverage partial."],
        assessment_status="PARTIALLY_COMPLETED",
        coverage_ratio=0.50,
        unevaluated_domains=["neurological", "hematologic", "immunological"],
        symptoms_submitted=False
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        assessment_status="PARTIALLY_COMPLETED",
        unevaluated_domains=["neurological", "hematologic", "immunological"]
    )
    assert is_valid is True
    assert len(violations) == 0

def test_scenario_i_corrupted_fallback_triggers_minimal_safe():
    """Verify fallback self-validation failure triggers minimal safe summary."""
    service = LLMInterpretationService(api_key="")
    with patch("risk_assessment.services.claim_grounding_validator.ClaimGroundingValidator.validate_synthesis", return_value=(False, ["Simulated violation"])):
        fallback_text = service._build_deterministic_fallback(
            astronaut_id="AST-001",
            session_id="S-001",
            overall_risk=RiskLevel.LOW,
            overall_confidence="HIGH",
            escalation_state=EscalationState.NO_TRIGGER_DETECTED,
            escalation_reason="Nominal",
            concerns=[],
            protective_factors=[],
            uncertainties=[]
        )
        assert "Automated deterministic summary generated" in fallback_text
        assert "AST-001" in fallback_text

def test_scenario_j_escalation_and_evidence_integrity_protections():
    """Verify existing red-line triggers produce ESCALATION_REQUIRED and invalid HRV is excluded."""
    engine = RiskEngine()
    items = [
        NormalizedEvidenceItem(
            evidence_id="EV-CHEST-PAIN",
            source_agent="personal_health_agent",
            source_type=EvidenceSourceType.REPORTED_SYMPTOM,
            domain=RiskDomain.CARDIOVASCULAR,
            metric_name="symptom_chest_pain",
            observed_value="SEVERE",
            validity_status=EvidenceValidity.VALID,
            source_reference="Symptom:chest_pain",
            evidence_description="Acute crushing substernal chest pain"
        ),
        NormalizedEvidenceItem(
            evidence_id="EV-HRV-INVALID",
            source_agent="personal_health_agent",
            source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
            domain=RiskDomain.CARDIOVASCULAR,
            metric_name="hrv_rmssd",
            observed_value=0.0,
            validity_status=EvidenceValidity.INVALID,
            source_reference="PHA:hrv",
            evidence_description="Zero RMSSD artifact",
            is_eligible_for_risk=False
        )
    ]
    res = engine.evaluate_risks(items)
    assert res.overall_risk == RiskLevel.CRITICAL
    assert any(r.rule_id == "RR-EMERG-CHEST-PAIN" for r in res.triggered_rules)
    assert not any("EV-HRV-INVALID" in pf.supporting_evidence_ids for pf in res.nominal_observation_details)
    assert not any("EV-HRV-INVALID" in pf.supporting_evidence_ids for pf in res.protective_factor_details)

def test_audit_req_1_invalid_evidence_normality_claims_rejected():
    """Verify synthesis claiming all observed variables remained within reference limits is rejected when invalid/degraded telemetry exists."""
    text = (
        "In evaluated domains, CARDIOVASCULAR and RESPIRATORY were classified as LOW risk, "
        "indicating that observed variables remained within established reference limits."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is False
    assert any("improperly claims all physiological variables are nominal" in v for v in violations)

def test_audit_req_2_degraded_telemetry_overclaims_rejected():
    """Verify synthesis claiming degraded telemetry is fully reliable is rejected."""
    text = (
        "Thermoregulatory telemetry was evaluated. The degraded telemetry is fully reliable for clinical diagnosis."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is False
    assert any("asserts degraded telemetry is fully reliable" in v for v in violations)

def test_audit_req_3_missing_symptoms_vs_negative_symptoms():
    """Verify unsubmitted symptoms cannot be asserted as confirmed absence of symptoms or reported no symptoms."""
    text_unconfirmed = "Crew health status: Astronaut reported no symptoms during this monitoring pass."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text_unconfirmed,
        overall_risk=RiskLevel.LOW,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        symptoms_explicitly_denied=False
    )
    assert is_valid is False
    assert any("unconfirmed symptom denial" in v for v in violations)

    text_proper_caveat = (
        "Subjective symptoms were not submitted for this session; "
        "absence of reports does not establish clinical absence of symptoms."
    )
    is_valid2, violations2 = ClaimGroundingValidator.validate_synthesis(
        text=text_proper_caveat,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        symptoms_explicitly_denied=False
    )
    assert is_valid2 is True
    assert len(violations2) == 0

def test_audit_req_4_missing_data_cannot_assert_emergency_escalation():
    """Verify missing telemetry cannot assert emergency mandate or immediate operational action when NO_TRIGGER_DETECTED."""
    text = (
        "To resolve the INSUFFICIENT_DATA status and improve risk confidence, "
        "immediate action is required to restore telemetry streams for the missing domains. "
        "Until this data is acquired, the Flight Surgeon should treat the unmonitored domains as high-uncertainty zones requiring enhanced manual monitoring."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is False
    assert any("asserts urgent operational mandate or clinical escalation" in v for v in violations)

def test_audit_req_5_recommendation_grounding_separation():
    """Verify prompt formatting and validator properly enforce DATA_GAP, RECOMMENDED_DATA_COLLECTION, and OPERATIONAL_ESCALATION."""
    from risk_assessment.agent.prompts import build_risk_user_prompt, RISK_ASSESSMENT_SYSTEM_PROMPT
    assert "RECOMMENDATION GROUNDING & ESCALATION SEMANTICS" in RISK_ASSESSMENT_SYSTEM_PROMPT
    assert "DATA_GAP" in RISK_ASSESSMENT_SYSTEM_PROMPT
    assert "ACT-NOM-001" in RISK_ASSESSMENT_SYSTEM_PROMPT
    assert "NO_TRIGGER_DETECTED" in RISK_ASSESSMENT_SYSTEM_PROMPT

    rec_actions = [
        {
            "action_id": "ACT-NOM-001",
            "action_type": "MONITORING",
            "description": "Continue routine health telemetry acquisition.",
            "priority": "ROUTINE",
            "destination": "ASTRONAUT_SELF_MONITORING"
        }
    ]
    prompt = build_risk_user_prompt(
        astronaut_id="AST-001",
        session_id="S-001",
        overall_risk="INSUFFICIENT_DATA",
        overall_confidence="MODERATE",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_reason="Nominal",
        domain_summaries=[],
        concerns=[],
        protective_factors=[],
        uncertainties=[],
        missing_info=["NEUROLOGICAL"],
        recommended_actions=rec_actions
    )
    assert "RECOMMENDED ACTIONS:" in prompt
    assert "ACT-NOM-001" in prompt
    assert "ASTRONAUT_SELF_MONITORING" in prompt

def test_audit_req_6_unverified_reference_identification():
    """Verify nominal observations identify derived clinical references as unverified direct NASA numerical thresholds."""
    engine = RiskEngine()
    items = [
        NormalizedEvidenceItem(
            evidence_id="EV-RESP-RATE",
            source_agent="personal_health_agent",
            source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
            domain=RiskDomain.RESPIRATORY,
            metric_name="respiratory_rate",
            observed_value=15.0,
            validity_status=EvidenceValidity.VALID,
            source_reference="PHA:resp",
            evidence_description="Respiration rate 15.0 bpm",
            is_eligible_for_risk=True
        )
    ]
    res = engine.evaluate_risks(items)
    resp_obs = [obs for obs in res.nominal_observation_details if obs.factor_id == "OBS-RESP-WNL-01"]
    assert len(resp_obs) == 1
    criterion = resp_obs[0].applicable_criterion
    assert "NASA-STD-3001 Volume 1 Revision C [V1 3004]" in criterion
    assert "Harrison's Principles of Internal Medicine" in criterion
    assert "numerical range is a clinical reference, not a direct NASA standard threshold requirement" in criterion

def test_audit_req_7_synthesis_consistency_deterministic_alignment():
    """Verify deterministic fallback aligns strictly with overall risk, domain risk, confidence, escalation, and protective factors."""
    service = LLMInterpretationService(api_key="")
    text, status = service.generate_explanation(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        overall_confidence="MODERATE",
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        escalation_reason="No trigger detected",
        domain_summaries=[{"domain": "CARDIOVASCULAR", "risk_level": "LOW", "confidence": "MODERATE", "explanation": "Nominal"}],
        concerns=[],
        protective_factors=[],
        uncertainties=["Cardiovascular HRV RMSSD is INVALID (ZERO_VARIABILITY)"],
        assessment_status="PARTIALLY_COMPLETED",
        coverage_ratio=0.50,
        unevaluated_domains=["NEUROLOGICAL", "SLEEP_AND_FATIGUE"],
        symptoms_submitted=False,
        nominal_observations=["Resting respiration rate (15.0 breaths/min) verified nominal within standard reference limits."]
    )
    assert "INSUFFICIENT_DATA" in text
    assert "MODERATE" in text
    assert "NO_TRIGGER_DETECTED" in text
    assert "No explicit protective factors documented" in text
    assert "Resting respiration rate" in text
    assert "immediate action is required" not in text
    assert "Flight Surgeon should treat" not in text

def test_release_gate_1_absolute_escalation_statements_rejected():
    """Verify absolute statements claiming emergency or clinical actions are not permitted are rejected."""
    text = (
        "Evaluation completed. Given the NO_TRIGGER_DETECTED escalation state, "
        "emergency actions are not permitted for this astronaut."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.LOW,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is False
    assert any("makes absolute statement claiming emergency or clinical actions are not permitted" in v for v in violations)

def test_release_gate_2_act_nom_001_scope_overclaim_rejected():
    """Verify attributing prospective collection of missing-domain telemetry to ACT-NOM-001 is rejected."""
    text = (
        "The recommended action is [ACT-NOM-001]: continue routine health telemetry acquisition "
        "and initiate prospective data collection for the missing domains (e.g. sleep logs)."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is False
    assert any("improperly attributes prospective collection of missing-domain telemetry to ACT-NOM-001" in v for v in violations)

def test_release_gate_3_machine_readable_trace_generation(tmp_path):
    """Verify ClaimGroundingValidator.trace_claims generates structured machine-readable records."""
    text = (
        "Clinical assessment for AST-001 yields INSUFFICIENT_DATA with MODERATE confidence.\n\n"
        "In CARDIOVASCULAR, HRV RMSSD is INVALID due to ZERO_VARIABILITY. RESPIRATORY is nominal.\n\n"
        "Unevaluated physiological domains remain unmonitored. ACT-NOM-001 directs routine monitoring."
    )
    trace_file = str(tmp_path / "test_trace.json")
    claims = ClaimGroundingValidator.trace_claims(
        text=text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        unevaluated_domains=["NEUROLOGICAL"],
        output_filepath=trace_file
    )
    assert len(claims) >= 3
    assert all("claim_id" in c for c in claims)
    assert all("evidence_ids" in c for c in claims)
    assert all("evidence_validity" in c for c in claims)
    assert all("provenance" in c for c in claims)
    assert all("validation_result" in c for c in claims)
    assert any("EV-PHY-HRV-RMSSD" in c["evidence_ids"] for c in claims)
    import json
    with open(trace_file) as f:
        data = json.load(f)
    assert len(data) == len(claims)
