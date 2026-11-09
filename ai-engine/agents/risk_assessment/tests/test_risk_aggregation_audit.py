"""Post-execution scientific audit regression tests for the TRUSTLINE Risk Assessment Agent.

Validates the epistemic integrity of:
1. Disaggregated risk calculation (evaluated_domains_risk vs system-wide overall_risk).
2. Explicit AssessmentCoverage computation and status transitions.
3. Unmonitored domain uncertainty logging.
4. Audited protective factor generation requiring verified evidence.
5. Cross-modal conflict detection and discordant uncertainty recording.
6. Rigorous LLM grounding rejection of unevaluated domain and unverified protective factor claims.
"""
from datetime import datetime
from typing import List, Optional
import pytest

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
from risk_assessment.schemas.risk_input import RiskAssessmentInput
from risk_assessment.services.risk_engine import RiskEngine
from risk_assessment.services.escalation_service import RiskEscalationService
from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
from risk_assessment.agent.agent import RiskAssessmentAgent
from sensor_quality.schemas.output_schema import (
    SensorQualityReport,
    SensorQualityResult,
    SensorQualityMetrics,
    OverallQuality,
    ProcessingDecision
)
from sensor_quality.schemas.signal_schema import QualityStatus
from personal_health.schemas.assessment import (
    PersonalHealthAssessment,
    AssessmentStatus
)
from personal_health.schemas.physiological_features import Core14Features
from personal_health.schemas.symptom_event import SymptomEvent, SymptomAssessmentStatus

def _create_evidence(
    ev_id: str,
    domain: RiskDomain,
    metric_name: str,
    val: float,
    validity: EvidenceValidity = EvidenceValidity.VALID,
    unit: str = "",
    source_type: EvidenceSourceType = EvidenceSourceType.PHYSIOLOGICAL_MEASUREMENT
) -> NormalizedEvidenceItem:
    """Helper creating a test NormalizedEvidenceItem instance."""
    return NormalizedEvidenceItem(
        evidence_id=ev_id,
        source_agent="unit_test",
        source_type=source_type,
        domain=domain,
        metric_name=metric_name,
        observed_value=val,
        unit=unit,
        validity_status=validity,
        timestamp=datetime.utcnow(),
        source_reference=f"REF-{ev_id}",
        evidence_description=f"Evidence for {metric_name}"
    )

def _build_full_nominal_evidence() -> List[NormalizedEvidenceItem]:
    """Helper producing nominal valid telemetry covering all 10 physiological and operational domains."""
    return [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 72.0, EvidenceValidity.VALID, "bpm"),
        _create_evidence("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.98, EvidenceValidity.VALID),
        _create_evidence("EV-03", RiskDomain.RESPIRATORY, "respiratory_rate", 14.0, EvidenceValidity.VALID, "breaths/min"),
        _create_evidence("EV-04", RiskDomain.RESPIRATORY, "RESP_quality_score", 0.95, EvidenceValidity.VALID),
        _create_evidence("EV-05", RiskDomain.THERMOREGULATORY, "temperature_mean", 36.8, EvidenceValidity.VALID, "°C"),
        _create_evidence("EV-06", RiskDomain.THERMOREGULATORY, "TEMP_quality_score", 0.99, EvidenceValidity.VALID),
        _create_evidence("EV-07", RiskDomain.NEUROLOGICAL, "neuro_status", 1.0, EvidenceValidity.VALID),
        _create_evidence("EV-08", RiskDomain.SLEEP_AND_FATIGUE, "actual_sleep_hours", 8.0, EvidenceValidity.VALID, "hours"),
        _create_evidence("EV-09", RiskDomain.PSYCHOLOGICAL_AND_COGNITIVE, "stress_probability", 0.12, EvidenceValidity.VALID),
        _create_evidence("EV-10", RiskDomain.HYDRATION_AND_FLUID_BALANCE, "hydration_index", 1.0, EvidenceValidity.VALID),
        _create_evidence("EV-11", RiskDomain.MUSCULOSKELETAL, "emg_rms", 0.02, EvidenceValidity.VALID),
        _create_evidence("EV-12", RiskDomain.GENERAL_PHYSIOLOGICAL, "general_status", 1.0, EvidenceValidity.VALID),
        _create_evidence(
            "EV-13",
            RiskDomain.DATA_QUALITY_RELATED,
            "ECG_quality_score",
            0.98,
            EvidenceValidity.VALID,
            source_type=EvidenceSourceType.SENSOR_QUALITY
        )
    ]

def _build_synthetic_sqr(
    ecg_status: QualityStatus = QualityStatus.VALID,
    astronaut_id: str = "AST-AUDIT",
    session_id: str = "S-AUDIT-01"
) -> SensorQualityReport:
    """Helper producing synthetic SensorQualityReport for multi-agent payload tests."""
    ecg_res = SensorQualityResult(
        sensor="ECG",
        quality_score=0.98 if ecg_status == QualityStatus.VALID else (0.45 if ecg_status == QualityStatus.DEGRADED else 0.0),
        status=ecg_status,
        metrics=SensorQualityMetrics(
            valid_sample_ratio=1.0 if ecg_status == QualityStatus.VALID else 0.0,
            missing_sample_ratio=0.0,
            artifact_ratio=0.0,
            flatline_ratio=1.0 if ecg_status == QualityStatus.INVALID else 0.0,
            noise_index=0.0,
            timestamp_integrity=1.0
        ),
        recommendation="ACCEPT" if ecg_status == QualityStatus.VALID else "REJECT",
        critical_failure=(ecg_status == QualityStatus.INVALID),
        sampling_rate=700.0,
        total_samples_analyzed=42000,
        duration_seconds=60.0
    )
    return SensorQualityReport(
        astronaut_id=astronaut_id,
        session_id=session_id,
        execution_timestamp=datetime.utcnow().isoformat(),
        overall_quality=OverallQuality(
            score=0.95 if ecg_status == QualityStatus.VALID else 0.40,
            status=ecg_status,
            valid_sensors_count=1 if ecg_status == QualityStatus.VALID else 0,
            total_sensors_count=1
        ),
        sensors={"ECG": ecg_res},
        processing_decision=ProcessingDecision(can_proceed=(ecg_status != QualityStatus.INVALID))
    )

def test_01_all_domains_evaluated_with_valid_evidence():
    """Verify full 10-domain valid telemetry yields COMPLETED status, coverage 1.0, LOW risk, and HIGH confidence."""
    engine = RiskEngine()
    items = _build_full_nominal_evidence()

    res = engine.evaluate_risks(items)

    assert res.assessment_status == "COMPLETED"
    assert res.coverage.domain_coverage_ratio == 1.0
    assert res.coverage.coverage_status == "COMPLETE"
    assert res.overall_risk == RiskLevel.LOW
    assert res.evaluated_domains_risk == RiskLevel.LOW
    assert res.overall_confidence == RiskConfidence.HIGH
    assert len(res.coverage.unevaluated_domains) == 0
    assert len(res.concerns) == 0

def test_02_five_domains_evaluated_five_unavailable():
    """Verify 5 evaluated domains yield PARTIALLY_COMPLETED, coverage 0.5, and INSUFFICIENT_DATA overall risk."""
    engine = RiskEngine()
    items = [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 72.0, EvidenceValidity.VALID, "bpm"),
        _create_evidence("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.98, EvidenceValidity.VALID),
        _create_evidence("EV-03", RiskDomain.RESPIRATORY, "respiratory_rate", 14.0, EvidenceValidity.VALID, "breaths/min"),
        _create_evidence("EV-04", RiskDomain.RESPIRATORY, "RESP_quality_score", 0.95, EvidenceValidity.VALID),
        _create_evidence("EV-05", RiskDomain.THERMOREGULATORY, "temperature_mean", 36.8, EvidenceValidity.VALID, "°C"),
        _create_evidence("EV-06", RiskDomain.THERMOREGULATORY, "TEMP_quality_score", 0.99, EvidenceValidity.VALID),
        _create_evidence("EV-07", RiskDomain.NEUROLOGICAL, "neuro_status", 1.0, EvidenceValidity.VALID),
        _create_evidence("EV-08", RiskDomain.SLEEP_AND_FATIGUE, "actual_sleep_hours", 8.0, EvidenceValidity.VALID, "hours")
    ]

    res = engine.evaluate_risks(items)

    assert res.assessment_status == "PARTIALLY_COMPLETED"
    assert res.coverage.domain_coverage_ratio == 0.5
    assert res.coverage.coverage_status == "PARTIAL"
    assert res.evaluated_domains_risk == RiskLevel.LOW
    assert res.overall_risk == RiskLevel.INSUFFICIENT_DATA
    assert len(res.coverage.evaluated_domains) == 5
    assert len(res.coverage.unevaluated_domains) == 5
    assert len(res.coverage.unavailable_domain_reasons) == 5
    assert any("partial assessment coverage" in u.lower() for u in res.uncertainties)

def test_03_no_symptoms_submitted():
    """Verify unsubmitted symptoms produce explicit limitation in uncertainties and zero symptom protective factors."""
    engine = RiskEngine()
    items = [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 70.0, EvidenceValidity.VALID, "bpm"),
        _create_evidence("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.95, EvidenceValidity.VALID),
        _create_evidence("EV-SYM", RiskDomain.GENERAL_PHYSIOLOGICAL, "symptom_status_unsubmitted", 1.0, EvidenceValidity.NOT_AVAILABLE)
    ]

    res = engine.evaluate_risks(items)

    assert not any(p.factor_id == "PROT-SYM-DENIAL-01" for p in res.protective_factor_details)
    assert any("Subjective symptoms were not submitted" in u for u in res.uncertainties)

def test_04_explicitly_denied_symptoms():
    """Verify confirmed absence of symptoms creates PROT-SYM-DENIAL-01 with supporting evidence pointer."""
    engine = RiskEngine()
    items = [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 72.0, EvidenceValidity.VALID, "bpm"),
        _create_evidence("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.95, EvidenceValidity.VALID),
        _create_evidence("EV-SYM-CONF", RiskDomain.GENERAL_PHYSIOLOGICAL, "symptom_explicitly_denied", 1.0, EvidenceValidity.VALID)
    ]

    res = engine.evaluate_risks(items)

    assert any(p.factor_id == "PROT-SYM-DENIAL-01" for p in res.protective_factor_details)
    denial_factor = next(p for p in res.protective_factor_details if p.factor_id == "PROT-SYM-DENIAL-01")
    assert "EV-SYM-CONF" in denial_factor.supporting_evidence_ids
    assert not any("Subjective symptoms were not submitted" in u for u in res.uncertainties)

def test_05_missing_symptom_data():
    """Verify omitted symptom telemetry logs explicit data gap uncertainty without protective claims."""
    engine = RiskEngine()
    items = [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 70.0, EvidenceValidity.VALID, "bpm"),
        _create_evidence("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.95, EvidenceValidity.VALID),
        _create_evidence("EV-SYM-UNAVAIL", RiskDomain.GENERAL_PHYSIOLOGICAL, "symptom_data_unavailable", 1.0, EvidenceValidity.NOT_AVAILABLE)
    ]

    res = engine.evaluate_risks(items)

    assert not any(p.factor_id == "PROT-SYM-DENIAL-01" for p in res.protective_factor_details)
    assert any("symptom assessment data is unavailable" in u.lower() for u in res.uncertainties)

def test_06_valid_sensor_quality_report():
    """Verify verified valid sensor quality telemetry creates PROT-DATA-QUALITY-01 factor."""
    engine = RiskEngine()
    items = [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 72.0, EvidenceValidity.VALID, "bpm"),
        _create_evidence("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.98, EvidenceValidity.VALID),
        _create_evidence(
            "EV-SQA-01",
            RiskDomain.DATA_QUALITY_RELATED,
            "ECG_quality_score",
            0.98,
            EvidenceValidity.VALID,
            source_type=EvidenceSourceType.SENSOR_QUALITY
        )
    ]

    res = engine.evaluate_risks(items)

    assert any(p.factor_id == "PROT-DATA-QUALITY-01" for p in res.protective_factor_details)
    sqa_factor = next(p for p in res.protective_factor_details if p.factor_id == "PROT-DATA-QUALITY-01")
    assert "EV-SQA-01" in sqa_factor.supporting_evidence_ids
    assert not any("Sensor Quality Agent report not provided" in u for u in res.uncertainties)

def test_07_missing_sensor_quality_report():
    """Verify omitted Sensor Quality report triggers uncertainty limitation and rejects data quality factor."""
    engine = RiskEngine()
    items = [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 72.0, EvidenceValidity.VALID, "bpm")
    ]

    res = engine.evaluate_risks(items)

    assert not any(p.factor_id == "PROT-DATA-QUALITY-01" for p in res.protective_factor_details)
    assert any("Sensor Quality Agent report not provided" in u for u in res.uncertainties)

def test_08_no_rule_triggered_but_domains_remain_unevaluated():
    """Verify zero triggered rules with partial coverage maintains NO_TRIGGER_DETECTED without asserting whole-body health."""
    engine = RiskEngine()
    items = [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 75.0, EvidenceValidity.VALID, "bpm"),
        _create_evidence("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.95, EvidenceValidity.VALID),
        _create_evidence("EV-03", RiskDomain.RESPIRATORY, "respiratory_rate", 15.0, EvidenceValidity.VALID, "breaths/min"),
        _create_evidence("EV-04", RiskDomain.RESPIRATORY, "RESP_quality_score", 0.95, EvidenceValidity.VALID),
        _create_evidence("EV-05", RiskDomain.THERMOREGULATORY, "temperature_mean", 36.9, EvidenceValidity.VALID, "°C"),
        _create_evidence("EV-06", RiskDomain.THERMOREGULATORY, "TEMP_quality_score", 0.95, EvidenceValidity.VALID),
        _create_evidence("EV-07", RiskDomain.NEUROLOGICAL, "neuro_status", 1.0, EvidenceValidity.VALID),
        _create_evidence("EV-08", RiskDomain.SLEEP_AND_FATIGUE, "actual_sleep_hours", 7.5, EvidenceValidity.VALID, "hours")
    ]

    res = engine.evaluate_risks(items)
    esc_details, _ = RiskEscalationService.determine_escalation(
        triggered_rules=res.triggered_rules,
        overall_risk=res.overall_risk,
        evidence_items=items
    )

    assert esc_details.state == EscalationState.NO_TRIGGER_DETECTED
    assert "unassessed domains" in esc_details.reason
    unevaluated = [d for d in res.domain_assessments if d.domain in res.coverage.unevaluated_domains]
    assert all(d.assessment_status == "NOT_EVALUATED" for d in unevaluated)
    assert all(d.risk_level == RiskLevel.UNKNOWN for d in unevaluated)

def test_09_high_severity_evidence_with_low_confidence():
    """Verify critical physiological concern maintains CRITICAL severity even when evidential confidence is LOW."""
    engine = RiskEngine()
    items = [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 165.0, EvidenceValidity.VALID, "bpm"),
        _create_evidence("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.40, EvidenceValidity.DEGRADED)
    ]

    res = engine.evaluate_risks(items)

    assert res.overall_risk == RiskLevel.CRITICAL
    assert res.evaluated_domains_risk == RiskLevel.CRITICAL
    assert res.overall_confidence == RiskConfidence.LOW
    assert any(c.severity == RiskLevel.CRITICAL for c in res.concerns)

def test_10_no_approved_rule_for_domain():
    """Verify domains without specific triggered rules are assessed nominal if valid, while unmonitored domains stay UNKNOWN."""
    engine = RiskEngine()
    items = [
        _create_evidence("EV-01", RiskDomain.THERMOREGULATORY, "temperature_mean", 37.0, EvidenceValidity.VALID, "°C"),
        _create_evidence("EV-02", RiskDomain.THERMOREGULATORY, "TEMP_quality_score", 0.95, EvidenceValidity.VALID)
    ]

    res = engine.evaluate_risks(items)

    therm_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.THERMOREGULATORY)
    assert therm_dom.risk_level == RiskLevel.LOW
    assert therm_dom.assessment_status == "EVALUATED"

    musc_dom = next(d for d in res.domain_assessments if d.domain == RiskDomain.MUSCULOSKELETAL)
    assert musc_dom.risk_level == RiskLevel.UNKNOWN
    assert musc_dom.assessment_status == "NOT_EVALUATED"
    assert RiskDomain.MUSCULOSKELETAL.value in res.coverage.unavailable_domain_reasons

def test_11_conflicting_evidence():
    """Verify cross-modal conflict between subjective symptom denial and objective tachycardia is flagged in uncertainties."""
    agent = RiskAssessmentAgent()
    sqr = _build_synthetic_sqr(QualityStatus.VALID, astronaut_id="AST-CONFLICT", session_id="S-CONFLICT")
    pha = PersonalHealthAssessment(
        assessment_id="PHA-CONFLICT",
        astronaut_id="AST-CONFLICT",
        session_id="S-CONFLICT",
        assessment_status=AssessmentStatus.COMPLETED,
        symptom_assessment_status=SymptomAssessmentStatus.CONFIRMED_ABSENCE_OF_SYMPTOMS,
        core_features=Core14Features(
            hr_mean_bpm=145.0,
            hr_std_bpm=5.0,
            hrv_rmssd_ms=18.0,
            hrv_sdnn_ms=25.0,
            eda_mean=4.0,
            eda_std=0.2,
            eda_iqr=0.3,
            resp_rate_bpm=16.0,
            resp_std=0.4,
            temp_mean=36.8,
            temp_std=0.1,
            emg_rms=0.02,
            acc_magnitude_mean=1.0,
            acc_magnitude_std=0.05
        )
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-CONFLICT",
        session_id="S-CONFLICT",
        sensor_quality_report=sqr,
        personal_health_assessment=pha,
        reported_symptoms=[]
    )

    output = agent.assess(payload)

    assert any("Cross-modal conflict" in u for u in output.uncertainties)
    correlations = output.processing_metadata.get("correlations", [])
    assert any(c.get("correlation_id") == "CORR-CONFLICT-ASYMPTOMATIC-TACHYCARDIA" for c in correlations)

def test_12_llm_invents_nominal_finding():
    """Verify ClaimGroundingValidator rejects LLM text claiming nominal status for unevaluated domains."""
    unsupported_text = (
        "Multi-agent review completes. The hydration and fluid balance domain is nominal and musculoskeletal stability is confirmed."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=unsupported_text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        mission_day_supplied=False,
        unevaluated_domains=["musculoskeletal", "hydration_and_fluid_balance"]
    )

    assert is_valid is False
    assert any("unevaluated domain" in v.lower() for v in violations)

def test_13_llm_invents_protective_factor():
    """Verify ClaimGroundingValidator rejects LLM text asserting unverified sensor quality protective factor."""
    unsupported_text = (
        "Telemetry review complete. All sensor quality is nominal and full signal fidelity is verified."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=unsupported_text,
        overall_risk=RiskLevel.LOW,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        mission_day_supplied=False,
        protective_factors=[]
    )

    assert is_valid is False
    assert any("protective factor" in v.lower() for v in violations)

def test_14_llm_changes_overall_risk_classification():
    """Verify ClaimGroundingValidator rejects LLM text claiming low risk when overall risk is INSUFFICIENT_DATA."""
    contradictory_text = (
        "Based on monitoring, Astronaut AST-001 is evaluated at overall low risk with nominal health status."
    )
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=contradictory_text,
        overall_risk=RiskLevel.INSUFFICIENT_DATA,
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        mission_day_supplied=False
    )

    assert is_valid is False
    assert any("contradicts deterministic overall risk" in v.lower() for v in violations)

def test_15_assessment_coverage_and_overall_status_consistency():
    """Verify strict mathematical consistency among evaluated domain count, coverage ratio, and assessment status."""
    engine = RiskEngine()

    zero_res = engine.evaluate_risks([])
    assert zero_res.coverage.domain_coverage_ratio == 0.0
    assert zero_res.coverage.coverage_status == "INSUFFICIENT"
    assert zero_res.assessment_status == "INSUFFICIENT_DATA"
    assert zero_res.overall_risk == RiskLevel.UNKNOWN

    partial_items = [
        _create_evidence("EV-01", RiskDomain.CARDIOVASCULAR, "heart_rate_mean", 72.0, EvidenceValidity.VALID, "bpm"),
        _create_evidence("EV-02", RiskDomain.CARDIOVASCULAR, "ECG_quality_score", 0.98, EvidenceValidity.VALID),
        _create_evidence("EV-03", RiskDomain.RESPIRATORY, "respiratory_rate", 14.0, EvidenceValidity.VALID, "breaths/min"),
        _create_evidence("EV-04", RiskDomain.RESPIRATORY, "RESP_quality_score", 0.95, EvidenceValidity.VALID),
        _create_evidence("EV-05", RiskDomain.THERMOREGULATORY, "temperature_mean", 36.8, EvidenceValidity.VALID, "°C"),
        _create_evidence("EV-06", RiskDomain.THERMOREGULATORY, "TEMP_quality_score", 0.99, EvidenceValidity.VALID),
        _create_evidence("EV-07", RiskDomain.NEUROLOGICAL, "neuro_status", 1.0, EvidenceValidity.VALID),
        _create_evidence("EV-08", RiskDomain.SLEEP_AND_FATIGUE, "actual_sleep_hours", 8.0, EvidenceValidity.VALID, "hours")
    ]
    partial_res = engine.evaluate_risks(partial_items)
    assert partial_res.coverage.domain_coverage_ratio == 0.5
    assert partial_res.coverage.coverage_status == "PARTIAL"
    assert partial_res.assessment_status == "PARTIALLY_COMPLETED"
    assert partial_res.overall_risk == RiskLevel.INSUFFICIENT_DATA
    assert round(len(partial_res.coverage.evaluated_domains) / partial_res.coverage.total_domains, 2) == 0.5

    full_items = _build_full_nominal_evidence()
    full_res = engine.evaluate_risks(full_items)
    assert full_res.coverage.domain_coverage_ratio == 1.0
    assert full_res.coverage.coverage_status == "COMPLETE"
    assert full_res.assessment_status == "COMPLETED"
    assert full_res.overall_risk == RiskLevel.LOW
    assert round(len(full_res.coverage.evaluated_domains) / full_res.coverage.total_domains, 2) == 1.0
