"""Unit tests for the Risk Assessment deterministic risk evaluation engine."""
import pytest
from datetime import datetime
from risk_assessment.schemas.evidence import (
    RiskDomain,
    EvidenceSourceType,
    EvidenceValidity,
    NormalizedEvidenceItem
)
from risk_assessment.schemas.risk_rules import RiskLevel, RiskConfidence, EscalationState
from risk_assessment.services.risk_engine import RiskEngine

def _create_item(
    ev_id: str,
    domain: RiskDomain,
    name: str,
    val: float,
    validity: EvidenceValidity = EvidenceValidity.VALID,
    unit: str = ""
) -> NormalizedEvidenceItem:
    """Helper creating a test NormalizedEvidenceItem instance."""
    return NormalizedEvidenceItem(
        evidence_id=ev_id,
        source_agent="unit_test",
        source_type=EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT,
        domain=domain,
        metric_name=name,
        observed_value=val,
        unit=unit,
        validity_status=validity,
        timestamp=datetime.utcnow(),
        source_reference=f"REF-{ev_id}",
        evidence_description=f"Test evidence for {name}"
    )

def test_01_zero_rules_triggered_nominal_full_coverage():
    """Verify nominal telemetry across all 10 domains yields complete coverage, LOW overall risk, and protective factors."""
    engine = RiskEngine()
    items = [
        _create_item("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 72.0, EvidenceValidity.VALID, "bpm"),
        _create_item("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.98, EvidenceValidity.VALID),
        _create_item("EV-03", RiskDomain.RESPIRATORY, "respiratory_rate", 14.0, EvidenceValidity.VALID, "breaths/min"),
        _create_item("EV-04", RiskDomain.RESPIRATORY, "RESP_quality_score", 0.95, EvidenceValidity.VALID),
        _create_item("EV-05", RiskDomain.THERMOREGULATORY, "temperature_mean", 36.8, EvidenceValidity.VALID, "°C"),
        _create_item("EV-06", RiskDomain.THERMOREGULATORY, "TEMP_quality_score", 0.99, EvidenceValidity.VALID),
        _create_item("EV-07", RiskDomain.NEUROLOGICAL, "neuro_status", 1.0, EvidenceValidity.VALID),
        _create_item("EV-08", RiskDomain.SLEEP_AND_FATIGUE, "actual_sleep_hours", 8.0, EvidenceValidity.VALID, "hours"),
        _create_item("EV-09", RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE, "stress_probability", 0.12, EvidenceValidity.VALID),
        _create_item("EV-10", RiskDomain.HYDRATION_AND_FLUID_BALANCE, "hydration_index", 1.0, EvidenceValidity.VALID),
        _create_item("EV-11", RiskDomain.MUSCULOSKELETAL, "emg_rms", 0.02, EvidenceValidity.VALID),
        _create_item("EV-12", RiskDomain.GENERAL_PHYSIOLOGICAL, "general_status", 1.0, EvidenceValidity.VALID),
        NormalizedEvidenceItem(
            evidence_id="EV-13",
            source_agent="sensor_quality_agent",
            source_type=EvidenceSourceType.SENSOR_QUALITY,
            domain=RiskDomain.DATA_QUALITY_RELATED,
            metric_name="ECG_quality_score",
            observed_value=0.98,
            validity_status=EvidenceValidity.VALID,
            source_reference="SQA-01",
            evidence_description="ECG quality score valid"
        )
    ]

    res = engine.evaluate_risks(items)

    assert res.overall_risk == RiskLevel.LOW
    assert res.evaluated_domains_risk == RiskLevel.LOW
    assert res.overall_confidence == RiskConfidence.HIGH
    assert res.assessment_status == "COMPLETED"
    assert res.coverage.domain_coverage_ratio == 1.0
    assert res.coverage.coverage_status == "COMPLETE"
    assert len(res.triggered_rules) == 0
    assert len(res.protective_factor_details) > 0
    assert len(res.nominal_observation_details) > 0
    assert any("nominal" in obs for obs in res.nominal_observations)

def test_02_single_rule_triggered_moderate_tachycardia():
    """Verify resting heart rate of 120 bpm triggers moderate tachycardia rule."""
    engine = RiskEngine()
    items = [
        _create_item("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 120.0, EvidenceValidity.VALID, "bpm"),
        _create_item("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.95, EvidenceValidity.VALID),
    ]

    res = engine.evaluate_risks(items)

    assert res.overall_risk == RiskLevel.MODERATE
    assert res.evaluated_domains_risk == RiskLevel.MODERATE
    assert len(res.triggered_rules) == 1
    assert res.triggered_rules[0].rule_id == "RR-CARDIO-TACHY-MODERATE"
    assert len(res.concerns) == 1
    assert res.concerns[0].severity == RiskLevel.MODERATE

    cardio_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.CARDIOVASCULAR)
    assert cardio_dom.risk_level == RiskLevel.MODERATE
    assert cardio_dom.assessment_status == "EVALUATED"

def test_03_multiple_rules_severity_precedence():
    """Verify CRITICAL severity overrides HIGH and MODERATE rules in overall risk determination."""
    engine = RiskEngine()
    items = [
        _create_item("EV-01", RiskDomain.CARDIOVASCULAR, "symptom_chest_pain", 1.0, EvidenceValidity.VALID),
        _create_item("EV-02", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 115.0, EvidenceValidity.VALID, "bpm"),
        _create_item("EV-03", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.90, EvidenceValidity.VALID),
        _create_item("EV-04", RiskDomain.THERMOREGULATORY, "temperature_mean", 38.6, EvidenceValidity.VALID, "°C"),
        _create_item("EV-05", RiskDomain.THERMOREGULATORY, "TEMP_quality_score", 0.92, EvidenceValidity.VALID),
    ]

    res = engine.evaluate_risks(items)

    assert res.overall_risk == RiskLevel.CRITICAL
    assert res.evaluated_domains_risk == RiskLevel.CRITICAL
    triggered_ids = [r.rule_id for r in res.triggered_rules]
    assert "RR-EMERG-CHEST-PAIN" in triggered_ids
    assert "RR-CARDIO-TACHY-MODERATE" in triggered_ids
    assert "RR-THERM-HYPERTHERMIA" in triggered_ids

    therm_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.THERMOREGULATORY)
    assert therm_dom.risk_level == RiskLevel.HIGH

    cardio_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.CARDIOVASCULAR)
    assert cardio_dom.risk_level == RiskLevel.CRITICAL

def test_04_data_quality_failure_isolation():
    """Verify invalid telemetry leads to INSUFFICIENT_DATA domain status and triggers data quality rule."""
    engine = RiskEngine()
    items = [
        _create_item("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 85.0, EvidenceValidity.INVALID, "bpm"),
        _create_item("EV-02", RiskDomain.DATA_QUALITY_RELATED, "ECG_quality_score", 0.12, EvidenceValidity.INVALID),
    ]

    res = engine.evaluate_risks(items)

    cardio_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.CARDIOVASCULAR)
    assert cardio_dom.risk_level == RiskLevel.INSUFFICIENT_DATA
    assert cardio_dom.assessment_status == "INSUFFICIENT_DATA"

    dq_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.DATA_QUALITY_RELATED)
    assert dq_dom.risk_level == RiskLevel.HIGH

    assert any(r.rule_id == "RR-DATA-SENSOR-CRITICAL-FAIL" for r in res.triggered_rules)
    assert res.overall_risk == RiskLevel.HIGH

def test_05_deterministic_repeatability():
    """Verify running the evaluation engine multiple times with identical inputs produces identical results."""
    engine = RiskEngine()
    items = [
        _create_item("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 105.0, EvidenceValidity.VALID, "bpm"),
        _create_item("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.91, EvidenceValidity.VALID),
        _create_item("EV-03", RiskDomain.RESPIRATORY, "cabin_co2_percent", 0.85, EvidenceValidity.VALID, "%"),
    ]

    res1 = engine.evaluate_risks(items)
    res2 = engine.evaluate_risks(items)

    assert res1.overall_risk == res2.overall_risk
    assert res1.overall_confidence == res2.overall_confidence
    assert len(res1.concerns) == len(res2.concerns)
    assert len(res1.triggered_rules) == len(res2.triggered_rules)
    assert [r.rule_id for r in res1.triggered_rules] == [r.rule_id for r in res2.triggered_rules]
    assert res1.uncertainties == res2.uncertainties
    assert res1.coverage.domain_coverage_ratio == res2.coverage.domain_coverage_ratio
