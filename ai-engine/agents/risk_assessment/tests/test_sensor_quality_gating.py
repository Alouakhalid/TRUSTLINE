"""Unit tests verifying strict sensor quality gating and evidential degradation."""
import pytest
from datetime import datetime
from risk_assessment.schemas.risk_input import RiskAssessmentInput
from risk_assessment.schemas.evidence import RiskDomain, EvidenceValidity
from risk_assessment.schemas.risk_rules import RiskLevel, RiskConfidence
from risk_assessment.services.evidence_normalization_service import EvidenceNormalizationService
from risk_assessment.agent.agent import RiskAssessmentAgent
from sensor_quality.schemas.output_schema import (
    SensorQualityReport,
    SensorQualityResult,
    SensorQualityMetrics,
    OverallQuality,
    ProcessingDecision
)
from sensor_quality.schemas.signal_schema import QualityStatus
from personal_health.schemas.assessment import PersonalHealthAssessment, AssessmentStatus
from personal_health.schemas.physiological_features import Core14Features

def _make_sqr(ecg_status: QualityStatus, temp_status: QualityStatus = QualityStatus.VALID) -> SensorQualityReport:
    """Helper creating synthetic SensorQualityReport with specified sensor statuses."""
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
    temp_res = SensorQualityResult(
        sensor="TEMP",
        quality_score=0.95,
        status=temp_status,
        metrics=SensorQualityMetrics(
            valid_sample_ratio=1.0,
            missing_sample_ratio=0.0,
            artifact_ratio=0.0,
            flatline_ratio=0.0,
            noise_index=0.0,
            timestamp_integrity=1.0
        ),
        recommendation="ACCEPT",
        critical_failure=False,
        sampling_rate=4.0,
        total_samples_analyzed=240,
        duration_seconds=60.0
    )
    return SensorQualityReport(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        execution_timestamp=datetime.utcnow().isoformat(),
        overall_quality=OverallQuality(
            score=0.90 if ecg_status == QualityStatus.VALID else 0.40,
            status=ecg_status,
            valid_sensors_count=2 if ecg_status == QualityStatus.VALID else 1,
            total_sensors_count=2
        ),
        sensors={"ECG": ecg_res, "TEMP": temp_res},
        processing_decision=ProcessingDecision(can_proceed=(ecg_status != QualityStatus.INVALID))
    )

def test_01_valid_sensor_telemetry_normalization():
    """Verify clean ECG telemetry produces VALID evidence item with high confidence."""
    sqr = _make_sqr(QualityStatus.VALID)
    pha = PersonalHealthAssessment(
        assessment_id="PHA-001",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        assessment_status=AssessmentStatus.COMPLETED,
        core_features=Core14Features(
            hr_mean_bpm=72.0,
            hr_std_bpm=2.0,
            hrv_rmssd_ms=35.0,
            hrv_sdnn_ms=40.0,
            eda_mean=4.5,
            eda_std=0.2,
            eda_iqr=0.3,
            resp_rate_bpm=14.0,
            resp_std=0.5,
            temp_mean=36.7,
            temp_std=0.1,
            emg_rms=0.02,
            acc_magnitude_mean=1.0,
            acc_magnitude_std=0.05
        )
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        sensor_quality_report=sqr,
        personal_health_assessment=pha
    )
    evidence = EvidenceNormalizationService.normalize_all(payload)
    hr_item = next((e for e in evidence if e.metric_name == "heart_rate_mean"), None)
    assert hr_item is not None
    assert hr_item.validity_status == EvidenceValidity.VALID
    assert hr_item.confidence >= 0.90

def test_02_invalid_critical_sensor_gating():
    """Verify INVALID ECG sensor marks cardiovascular evidence as INVALID and triggers data quality rule."""
    sqr = _make_sqr(QualityStatus.INVALID)
    pha = PersonalHealthAssessment(
        assessment_id="PHA-002",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        assessment_status=AssessmentStatus.COMPLETED,
        core_features=Core14Features(
            hr_mean_bpm=170.0,
            hr_std_bpm=0.0,
            hrv_rmssd_ms=0.0,
            hrv_sdnn_ms=0.0,
            eda_mean=4.5,
            eda_std=0.2,
            eda_iqr=0.3,
            resp_rate_bpm=14.0,
            resp_std=0.5,
            temp_mean=36.7,
            temp_std=0.1,
            emg_rms=0.02,
            acc_magnitude_mean=1.0,
            acc_magnitude_std=0.05
        )
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        sensor_quality_report=sqr,
        personal_health_assessment=pha
    )
    agent = RiskAssessmentAgent()
    output = agent.assess(payload)

    cardio_dom = next((d for d in output.risk_domains if d.domain == RiskDomain.CARDIOVASCULAR), None)
    assert cardio_dom is not None
    assert not any(r.rule_id == "RR-CARDIO-TACHY-EXTREME" for r in output.triggered_rules)

    data_dom = next((d for d in output.risk_domains if d.domain == RiskDomain.DATA_QUALITY_RELATED), None)
    assert data_dom is not None
    assert any(r.rule_id == "RR-DATA-SENSOR-CRITICAL-FAIL" for r in output.triggered_rules)

def test_03_degraded_sensor_reduces_confidence():
    """Verify DEGRADED sensor status reduces confidence score to MODERATE."""
    sqr = _make_sqr(QualityStatus.DEGRADED)
    pha = PersonalHealthAssessment(
        assessment_id="PHA-003",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        assessment_status=AssessmentStatus.COMPLETED,
        core_features=Core14Features(
            hr_mean_bpm=75.0,
            hr_std_bpm=3.0,
            hrv_rmssd_ms=30.0,
            hrv_sdnn_ms=35.0,
            eda_mean=4.5,
            eda_std=0.2,
            eda_iqr=0.3,
            resp_rate_bpm=14.0,
            resp_std=0.5,
            temp_mean=36.7,
            temp_std=0.1,
            emg_rms=0.02,
            acc_magnitude_mean=1.0,
            acc_magnitude_std=0.05
        )
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        sensor_quality_report=sqr,
        personal_health_assessment=pha
    )
    evidence = EvidenceNormalizationService.normalize_all(payload)
    hr_item = next((e for e in evidence if e.metric_name == "heart_rate_mean"), None)
    assert hr_item is not None
    assert hr_item.validity_status == EvidenceValidity.DEGRADED
    assert hr_item.confidence <= 0.60
