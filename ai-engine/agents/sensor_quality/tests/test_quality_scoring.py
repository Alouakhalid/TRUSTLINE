"""Tests for QualityScorer module."""
import pytest
from sensor_quality_agent.core.quality_scoring import QualityScorer
from sensor_quality_agent.schemas.signal_schema import QualityStatus, IssueSeverity
from sensor_quality_agent.schemas.output_schema import SensorQualityMetrics, DetectedIssue
from sensor_quality_agent.explainability.reason_codes import ReasonCode

def test_clean_sensor_scoring():
    scorer = QualityScorer()
    metrics = SensorQualityMetrics(
        valid_sample_ratio=1.0,
        missing_sample_ratio=0.0,
        artifact_ratio=0.0,
        flatline_ratio=0.0,
        noise_index=0.0,
        timestamp_integrity=1.0,
        saturation_ratio=0.0,
        continuity_score=1.0
    )
    res = scorer.score_sensor(
        sensor="ECG",
        metrics=metrics,
        issues=[],
        sampling_rate=700.0,
        total_samples=7000,
        duration_seconds=10.0
    )
    assert res.quality_score >= 0.95
    assert res.status == QualityStatus.VALID
    assert res.recommendation == "ACCEPT"
    assert res.critical_failure is False

def test_critical_failure_override():
    scorer = QualityScorer()
    metrics = SensorQualityMetrics(
        valid_sample_ratio=1.0,
        missing_sample_ratio=0.0,
        artifact_ratio=0.0,
        flatline_ratio=0.45,
        noise_index=0.0,
        timestamp_integrity=1.0,
        saturation_ratio=0.0,
        continuity_score=1.0
    )
    issue = DetectedIssue(
        reason_code=ReasonCode.SENSOR_FLATLINE.value,
        sensor="ECG",
        severity=IssueSeverity.CRITICAL,
        method="Zero variance test",
        explanation="Sensor is flatlined."
    )
    res = scorer.score_sensor(
        sensor="ECG",
        metrics=metrics,
        issues=[issue],
        sampling_rate=700.0,
        total_samples=7000,
        duration_seconds=10.0
    )
    assert res.quality_score <= 0.40
    assert res.status == QualityStatus.INVALID
    assert res.recommendation == "REJECT"
    assert res.critical_failure is True

def test_overall_session_scoring():
    scorer = QualityScorer()
    metrics_valid = SensorQualityMetrics(
        valid_sample_ratio=1.0,
        missing_sample_ratio=0.0,
        artifact_ratio=0.0,
        flatline_ratio=0.0,
        noise_index=0.0,
        timestamp_integrity=1.0,
        saturation_ratio=0.0,
        continuity_score=1.0
    )
    metrics_invalid = SensorQualityMetrics(
        valid_sample_ratio=0.5,
        missing_sample_ratio=0.5,
        artifact_ratio=0.5,
        flatline_ratio=0.5,
        noise_index=0.5,
        timestamp_integrity=0.1,
        saturation_ratio=0.5,
        continuity_score=0.2
    )

    r1 = scorer.score_sensor("ECG", metrics_valid, [], 700.0, 7000, 10.0)
    r2 = scorer.score_sensor("EDA", metrics_valid, [], 4.0, 40, 10.0)
    r3 = scorer.score_sensor("RESP", metrics_valid, [], 700.0, 7000, 10.0)
    r4 = scorer.score_sensor("EMG", metrics_invalid, [], 700.0, 7000, 10.0)

    results = {"ECG": r1, "EDA": r2, "RESP": r3, "EMG": r4}
    overall = scorer.score_overall_session(results)
    assert overall.valid_sensors_count == 3
    assert overall.total_sensors_count == 4
    assert "EMG" in overall.rejected_sensors
    assert overall.status in {QualityStatus.ACCEPTABLE_WITH_WARNING, QualityStatus.DEGRADED}
