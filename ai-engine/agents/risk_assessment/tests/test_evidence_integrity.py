"""Regression tests validating evidence integrity, confidence calibration, and protective factor gating."""
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
    RiskConfidence,
    EscalationState
)
from risk_assessment.services.risk_engine import RiskEngine
from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator

def _build_evidence_item(
    ev_id: str,
    domain: RiskDomain,
    metric: str,
    val: float,
    validity: EvidenceValidity = EvidenceValidity.VALID,
    unit: str = "",
    quality_status: str = "VALID",
    classification: str = "CLINICAL_OBSERVATION",
    is_eligible: bool = True,
    raw_ctx: dict = None
) -> NormalizedEvidenceItem:
    """Helper creating a test NormalizedEvidenceItem instance."""
    return NormalizedEvidenceItem(
        evidence_id=ev_id,
        source_agent="unit_test",
        source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
        domain=domain,
        metric_name=metric,
        observed_value=val,
        unit=unit,
        validity_status=validity,
        quality_status=quality_status,
        evidence_classification=classification,
        is_eligible_for_risk=is_eligible,
        raw_context=raw_ctx or {},
        timestamp=datetime.utcnow(),
        source_reference=f"REF-{ev_id}",
        evidence_description=f"Evidence for {metric}"
    )

def test_01_invalid_hrv_excluded_confidence_recalculated():
    """Verify invalid HRV is excluded from supporting evidence, confidence is capped at MODERATE, and limitation is logged."""
    engine = RiskEngine()
    items = [
        _build_evidence_item(
            "EV-PHY-HR-MEAN",
            RiskDomain.CARDIOVASCULAR,
            "heart_rate_mean",
            72.0,
            EvidenceValidity.VALID,
            "bpm"
        ),
        _build_evidence_item(
            "EV-PHY-HRV-RMSSD",
            RiskDomain.CARDIOVASCULAR,
            "hrv_rmssd",
            0.0,
            EvidenceValidity.INVALID,
            "ms",
            classification="DATA_INTEGRITY_ARTIFACT",
            is_eligible=False,
            raw_ctx={"zero_variability": True}
        ),
        _build_evidence_item(
            "EV-SQ-ECG",
            RiskDomain.DATA_QUALITY_RELATED,
            "ECG_quality_score",
            0.98,
            EvidenceValidity.VALID
        )
    ]

    res = engine.evaluate_risks(items)

    cardio_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.CARDIOVASCULAR)
    assert cardio_dom.risk_level == RiskLevel.LOW
    assert cardio_dom.confidence == RiskConfidence.MODERATE
    assert "EV-PHY-HRV-RMSSD" not in cardio_dom.supporting_evidence_ids
    assert "EV-PHY-HR-MEAN" in cardio_dom.supporting_evidence_ids
    assert any("ZERO_VARIABILITY" in lim for lim in cardio_dom.limitations)
    assert not any("EV-PHY-HRV-RMSSD" in pf.supporting_evidence_ids for pf in res.protective_factor_details)
    assert not any(pf.factor_id == "PROT-CARDIO-01" for pf in res.protective_factor_details)

def test_02_no_submitted_symptoms_unknown_general_domain():
    """Verify unsubmitted symptoms lead to GENERAL_PHYSIOLOGICAL classified as NOT_EVALUATED, UNKNOWN, and UNDETERMINED."""
    engine = RiskEngine()
    items = [
        _build_evidence_item(
            "EV-SYM-UNSUBMITTED",
            RiskDomain.GENERAL_PHYSIOLOGICAL,
            "symptom_status_unsubmitted",
            1.0,
            EvidenceValidity.NOT_AVAILABLE,
            classification="UNSUBMITTED_STATUS",
            is_eligible=False
        )
    ]

    res = engine.evaluate_risks(items)

    gen_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.GENERAL_PHYSIOLOGICAL)
    assert gen_dom.assessment_status == "NOT_EVALUATED"
    assert gen_dom.risk_level == RiskLevel.UNKNOWN
    assert gen_dom.confidence == RiskConfidence.UNDETERMINED
    assert len(gen_dom.supporting_evidence_ids) == 0
    assert RiskDomain.GENERAL_PHYSIOLOGICAL in res.coverage.unevaluated_domains
    assert RiskDomain.GENERAL_PHYSIOLOGICAL not in res.coverage.evaluated_domains
    assert "GENERAL_PHYSIOLOGICAL" in res.coverage.unavailable_domain_reasons

def test_03_wesad_experimental_context_no_protective_factor():
    """Verify WESAD classifier is treated as experimental context with zero protective factors and capped confidence."""
    engine = RiskEngine()
    items = [
        _build_evidence_item(
            "EV-PHY-EDA-MEAN",
            RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE,
            "eda_mean",
            4.69,
            EvidenceValidity.VALID,
            "uS"
        ),
        _build_evidence_item(
            "EV-ML-WESAD-1",
            RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE,
            "experimental_lab_stress_probability",
            0.12,
            EvidenceValidity.VALID,
            "probability",
            classification="EXPERIMENTAL_CONTEXT",
            is_eligible=False
        )
    ]

    res = engine.evaluate_risks(items)

    psych_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE)
    assert psych_dom.confidence == RiskConfidence.MODERATE
    assert "EV-ML-WESAD-1" not in psych_dom.supporting_evidence_ids
    assert "EV-PHY-EDA-MEAN" in psych_dom.supporting_evidence_ids
    assert not any(pf.domain == RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE for pf in res.protective_factor_details)
    assert any("Psychological assessment limited" in lim for lim in psych_dom.limitations)

def test_04_no_triggered_rules_not_protective_factor():
    """Verify absence of triggered rules alone does not generate ungrounded protective factors."""
    engine = RiskEngine()
    items = [
        _build_evidence_item(
            "EV-PHY-EDA-MEAN",
            RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE,
            "eda_mean",
            4.69,
            EvidenceValidity.VALID,
            "uS"
        )
    ]

    res = engine.evaluate_risks(items)

    assert not any(pf.domain == RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE for pf in res.protective_factor_details)
    assert len(res.triggered_rules) == 0

def test_05_degraded_skin_temperature_no_core_inference():
    """Verify peripheral skin temperature does not trigger core hyperthermia rules or satisfy core protective factors."""
    engine = RiskEngine()
    items = [
        _build_evidence_item(
            "EV-PHY-TEMP-MEAN",
            RiskDomain.THERMOREGULATORY,
            "temperature_mean",
            34.27,
            EvidenceValidity.DEGRADED,
            "°C",
            quality_status="ACCEPTABLE_WITH_WARNING",
            raw_ctx={"measurement_type": "SKIN_SURFACE_TEMPERATURE"}
        ),
        _build_evidence_item(
            "EV-SQ-TEMP",
            RiskDomain.DATA_QUALITY_RELATED,
            "TEMP_quality_score",
            0.85,
            EvidenceValidity.DEGRADED,
            quality_status="ACCEPTABLE_WITH_WARNING"
        )
    ]

    res = engine.evaluate_risks(items)

    therm_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.THERMOREGULATORY)
    assert therm_dom.risk_level == RiskLevel.LOW
    assert therm_dom.confidence == RiskConfidence.MODERATE
    assert not any(r.rule_id == "RR-THERM-HYPERTHERMIA" for r in res.triggered_rules)
    assert not any(pf.factor_id == "PROT-THERM-01" for pf in res.protective_factor_details)
    assert any("skin surface temperature" in lim for lim in therm_dom.limitations)

def test_06_partial_coverage_insufficient_data():
    """Verify partial domain coverage results in PARTIALLY_COMPLETED status and INSUFFICIENT_DATA overall risk."""
    engine = RiskEngine()
    items = [
        _build_evidence_item("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 72.0, EvidenceValidity.VALID, "bpm"),
        _build_evidence_item("EV-02", RiskDomain.RESPIRATORY, "respiratory_rate", 14.0, EvidenceValidity.VALID, "breaths/min"),
        _build_evidence_item("EV-03", RiskDomain.THERMOREGULATORY, "temperature_mean", 34.27, EvidenceValidity.DEGRADED, "°C", raw_ctx={"measurement_type": "SKIN_SURFACE_TEMPERATURE"}),
        _build_evidence_item("EV-04", RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE, "eda_mean", 4.69, EvidenceValidity.VALID, "uS"),
        _build_evidence_item("EV-05", RiskDomain.DATA_QUALITY_RELATED, "ECG_quality_score", 0.98, EvidenceValidity.VALID)
    ]

    res = engine.evaluate_risks(items)

    assert res.assessment_status == "PARTIALLY_COMPLETED"
    assert res.coverage.domain_coverage_ratio == 0.50
    assert res.coverage.coverage_status == "PARTIAL"
    assert res.overall_risk == RiskLevel.INSUFFICIENT_DATA
    assert res.overall_confidence == RiskConfidence.MODERATE
    assert len(res.coverage.evaluated_domains) == 5
    assert len(res.coverage.unevaluated_domains) == 5

def test_07_valid_domain_specific_evidence_low_risk_isolation():
    """Verify valid resting respiratory rate produces LOW domain risk isolated from unevaluated systems."""
    engine = RiskEngine()
    items = [
        _build_evidence_item(
            "EV-PHY-RESP-RATE",
            RiskDomain.RESPIRATORY,
            "respiratory_rate",
            15.0,
            EvidenceValidity.VALID,
            "breaths/min"
        )
    ]

    res = engine.evaluate_risks(items)

    resp_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.RESPIRATORY)
    assert resp_dom.risk_level == RiskLevel.LOW
    assert resp_dom.assessment_status == "EVALUATED"
    assert resp_dom.supporting_evidence_ids == ["EV-PHY-RESP-RATE"]
    assert any(obs.factor_id == "OBS-RESP-WNL-01" for obs in res.nominal_observation_details)
    assert not any(pf.factor_id == "PROT-RESP-01" for pf in res.protective_factor_details)
    assert res.overall_risk == RiskLevel.INSUFFICIENT_DATA

def test_08_llm_grounding_reflects_evidence_limitations():
    """Verify ClaimGroundingValidator rejects clinical synthesis upgrading invalid, experimental, or unsubmitted evidence."""
    invalid_hrv_text = (
        "Astronaut AST-001 exhibits normal HRV and autonomic regulation is intact."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=invalid_hrv_text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is False
    assert any("normal hrv" in v.lower() or "autonomic regulation" in v.lower() for v in violations)

    wesad_leap_text = (
        "Multi-modal telemetry confirms WESAD proves the astronaut is psychologically healthy."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=wesad_leap_text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is False
    assert any("wesad" in v.lower() for v in violations)

    denial_leap_text = (
        "Structured telemetry confirms astronaut denies symptoms during active monitoring."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=denial_leap_text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        symptoms_explicitly_denied=False
    )
    assert is_valid is False
    assert any("symptom denial" in v.lower() for v in violations)

    core_temp_leap_text = (
        "Thermal telemetry confirms core body temperature is 34.27 °C within standard physiological baseline."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=core_temp_leap_text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED
    )
    assert is_valid is False
    assert any("peripheral skin" in v.lower() for v in violations)
