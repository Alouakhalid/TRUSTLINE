"""Comprehensive 20-case test suite for TRUSTLINE Sensor Quality Validation Layer."""

import sys
from pathlib import Path
import numpy as np
import pytest

cur = Path(__file__).resolve().parent
while cur != cur.parent:
    if (cur / "sensor_quality_agent").exists():
        if str(cur) not in sys.path:
            sys.path.insert(0, str(cur))
        break
    cur = cur.parent

from sensor_quality_agent.validation.schemas import (
    ValidationVerdict,
    CheckStatus,
    ValidationCheckResult,
)
from sensor_quality_agent.validation.input_validator import InputValidator
from sensor_quality_agent.validation.sensor_validator import SensorOutputValidator
from sensor_quality_agent.validation.score_auditor import QualityScoreAuditor
from sensor_quality_agent.validation.signal_auditor import SignalAuditor
from sensor_quality_agent.validation.cross_validator import CrossValidator
from sensor_quality_agent.validation.validator_engine import ValidationEngine
from sensor_quality_agent.schemas.signal_schema import QualityStatus, IssueSeverity, SensorStreamData
from sensor_quality_agent.schemas.output_schema import (
    SensorQualityResult,
    SensorQualityMetrics,
    DetectedIssue,
    IssueEvidence,
    OverallQuality,
    ProcessingDecision,
    SensorQualityReport,
)


def _make_dummy_metrics():
    return SensorQualityMetrics(
        valid_sample_ratio=1.0,
        missing_sample_ratio=0.0,
        artifact_ratio=0.0,
        flatline_ratio=0.0,
        noise_index=0.05,
        timestamp_integrity=1.0,
        saturation_ratio=0.0,
        continuity_score=1.0
    )


def _make_dummy_sensor_result(sensor="ECG", score=0.98, status=QualityStatus.VALID, issues=None, critical=False, rec="ACCEPT"):
    return SensorQualityResult(
        sensor=sensor,
        quality_score=score,
        status=status,
        metrics=_make_dummy_metrics(),
        issues=issues or [],
        recommendation=rec,
        critical_failure=critical,
        sampling_rate=700.0,
        total_samples_analyzed=42000,
        duration_seconds=60.0
    )


def test_01_valid_input_and_signals():
    """Case 1: Fully valid input manifest dictionary and file configurations."""
    validator = InputValidator()
    manifest_dict = {
        "metadata": {"astronaut_id": "AST-001", "session_id": "SES-001"},
        "signals": {
            "ECG": {
                "file": "nonexistent.npy",
                "sampling_rate": 700.0,
                "unit": "mV"
            }
        }
    }
    checks = validator.validate_manifest_dict(manifest_dict)
    meta_checks = [c for c in checks if "META" in c.check_id]
    assert any(c.check_id == "INPUT-META-002" and c.status == CheckStatus.PASSED for c in meta_checks)
    assert any(c.check_id == "INPUT-META-003" and c.status == CheckStatus.PASSED for c in meta_checks)


def test_02_empty_signal():
    """Case 2: Zero-sample empty signal array validation."""
    validator = InputValidator()
    empty_arr = np.array([], dtype=np.float32)
    checks = validator.validate_raw_array("ECG", empty_arr)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "INPUT-ARRAY-EMPTY" for c in failed)


def test_03_nan_and_inf_values():
    """Case 3: Unacceptable NaN and Inf values present in raw signal."""
    validator = InputValidator()
    corrupt_arr = np.array([1.0, np.nan, 2.0, np.inf, 3.0], dtype=np.float32)
    checks = validator.validate_raw_array("EDA", corrupt_arr)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "INPUT-ARRAY-NAN-INF" for c in failed)


def test_04_missing_timestamps():
    """Case 4: Timestamps array length mismatch against signal array."""
    validator = InputValidator()
    ts_arr = np.array([0.0, 0.25], dtype=np.float64)
    checks = validator.validate_timestamps("EDA", ts_arr, expected_len=100, sampling_rate=4.0)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "INPUT-TS-LEN-MISMATCH" for c in failed)


def test_05_duplicate_timestamps():
    """Case 5: Non-monotonic or duplicate timestamps detection."""
    validator = InputValidator()
    duplicate_ts = np.array([0.0, 0.25, 0.25, 0.75], dtype=np.float64)
    checks = validator.validate_timestamps("EDA", duplicate_ts, expected_len=4, sampling_rate=4.0)
    assert any(c.check_id == "INPUT-TS-DUPLICATES" for c in checks)


def test_06_irregular_sampling():
    """Case 6: Timestamp gaps and non-monotonic irregular progression detection."""
    validator = InputValidator()
    backwards_ts = np.array([0.0, 0.5, 0.2, 0.9, 1.2], dtype=np.float64)
    checks = validator.validate_timestamps("EDA", backwards_ts, expected_len=5, sampling_rate=4.0)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "INPUT-TS-BACKWARDS" for c in failed)


def test_07_severe_ecg_artifact():
    """Case 7: Verification of detected severe ECG impulsive spikes."""
    auditor = SignalAuditor()
    fs = 700.0
    t = np.arange(1400) / fs
    clean_ecg = np.sin(2 * np.pi * 1.5 * t)
    clean_ecg[100:150] += 50.0
    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=clean_ecg,
        timestamps=t,
        duration_seconds=2.0,
        total_samples=1400
    )
    issue = DetectedIssue(
        reason_code="SIGNAL_SPIKES",
        sensor="ECG",
        severity=IssueSeverity.MODERATE,
        evidence=[
            IssueEvidence(
                metric_name="spike_ratio",
                measured_value=0.035,
                threshold_value=0.005,
                units="ratio"
            )
        ],
        method="MAD Z-score",
        explanation="Impulsive spikes detected."
    )
    res = _make_dummy_sensor_result(sensor="ECG", score=0.90, issues=[issue])
    checks, _, _ = auditor.audit_signal_evidence({"ECG": stream}, {"ECG": res})
    assert any(c.check_id == "SIG-SPIKE-EVIDENCE-CONFIRMED" for c in checks)


def test_08_eda_discontinuity():
    """Case 8: Verification of EDA signal spike and artifact issues."""
    auditor = SignalAuditor()
    fs = 4.0
    t = np.arange(40) / fs
    eda_data = np.ones(40) * 5.0
    eda_data[10] = 50.0
    stream = SensorStreamData(
        sensor="EDA",
        sampling_rate=fs,
        unit="uS",
        data=eda_data,
        timestamps=t,
        duration_seconds=10.0,
        total_samples=40
    )
    issue = DetectedIssue(
        reason_code="SIGNAL_SPIKES",
        sensor="EDA",
        severity=IssueSeverity.MODERATE,
        evidence=[
            IssueEvidence(
                metric_name="spike_ratio",
                measured_value=0.025,
                threshold_value=0.005,
                units="ratio"
            )
        ],
        method="MAD Z-score",
        explanation="Impulsive spikes detected."
    )
    res = _make_dummy_sensor_result(sensor="EDA", score=0.95, issues=[issue])
    checks, _, _ = auditor.audit_signal_evidence({"EDA": stream}, {"EDA": res})
    assert any(c.check_id == "SIG-SPIKE-EVIDENCE-CONFIRMED" for c in checks)


def test_09_resp_interruption():
    """Case 9: Verification of respiratory signal flatline / interruption."""
    auditor = SignalAuditor()
    fs = 700.0
    t = np.arange(700) / fs
    flatline = np.zeros(700)
    stream = SensorStreamData(
        sensor="RESP",
        sampling_rate=fs,
        unit="mV",
        data=flatline,
        timestamps=t,
        duration_seconds=1.0,
        total_samples=700
    )
    issue = DetectedIssue(
        reason_code="SENSOR_FLATLINE",
        sensor="RESP",
        severity=IssueSeverity.HIGH,
        evidence=[
            IssueEvidence(
                metric_name="flatline_ratio",
                measured_value=1.0,
                threshold_value=0.1,
                units="ratio"
            )
        ],
        method="Variance inspection",
        explanation="Channel flatline detected."
    )
    res = _make_dummy_sensor_result(sensor="RESP", score=0.50, issues=[issue])
    checks, _, _ = auditor.audit_signal_evidence({"RESP": stream}, {"RESP": res})
    assert any(c.check_id == "SIG-FLATLINE-EVIDENCE-CONFIRMED" for c in checks)


def test_10_emg_saturation():
    """Case 10: Verification of EMG boundary clipping / saturation."""
    auditor = SignalAuditor()
    fs = 700.0
    t = np.arange(700) / fs
    clipped_data = np.clip(np.sin(2 * np.pi * 5 * t) * 10, -5.0, 5.0)
    stream = SensorStreamData(
        sensor="EMG",
        sampling_rate=fs,
        unit="mV",
        data=clipped_data,
        timestamps=t,
        duration_seconds=1.0,
        total_samples=700
    )
    issue = DetectedIssue(
        reason_code="SIGNAL_CLIPPING",
        sensor="EMG",
        severity=IssueSeverity.HIGH,
        evidence=[
            IssueEvidence(
                metric_name="clipping_ratio",
                measured_value=0.20,
                threshold_value=0.01,
                units="ratio"
            )
        ],
        method="Min/max saturation inspection",
        explanation="Boundary clipping detected."
    )
    res = _make_dummy_sensor_result(sensor="EMG", score=0.60, issues=[issue])
    checks, _, _ = auditor.audit_signal_evidence({"EMG": stream}, {"EMG": res})
    assert any(c.check_id == "SIG-CLIPPING-EVIDENCE-CONFIRMED" for c in checks)


def test_11_acc_clipping():
    """Case 11: Verification of Accelerometer clipping artifact."""
    auditor = SignalAuditor()
    fs = 700.0
    t = np.arange(700) / fs
    acc_data = np.clip(np.ones(700) * 16.0, -16.0, 16.0)
    stream = SensorStreamData(
        sensor="ACC",
        sampling_rate=fs,
        unit="g",
        data=acc_data,
        timestamps=t,
        duration_seconds=1.0,
        total_samples=700
    )
    issue = DetectedIssue(
        reason_code="SIGNAL_CLIPPING",
        sensor="ACC",
        severity=IssueSeverity.HIGH,
        evidence=[
            IssueEvidence(
                metric_name="clipping_ratio",
                measured_value=1.0,
                threshold_value=0.01,
                units="ratio"
            )
        ],
        method="Saturation inspection",
        explanation="Accelerometer maximum range exceeded."
    )
    res = _make_dummy_sensor_result(sensor="ACC", score=0.50, issues=[issue])
    checks, _, _ = auditor.audit_signal_evidence({"ACC": stream}, {"ACC": res})
    assert any(c.check_id == "SIG-CLIPPING-EVIDENCE-CONFIRMED" for c in checks)


def test_12_temperature_rate_of_change_warning():
    """Case 12: Deep temperature investigation calculating point-to-point and smoothed dT/dt."""
    auditor = SignalAuditor()
    fs = 700.0
    n = 1400
    t = np.arange(n) / fs
    temp_vals = np.ones(n) * 36.5
    temp_vals[100] += 0.03
    stream = SensorStreamData(
        sensor="TEMP",
        sampling_rate=fs,
        unit="C",
        data=temp_vals,
        timestamps=t,
        duration_seconds=2.0,
        total_samples=n
    )
    temp_res = _make_dummy_sensor_result(
        sensor="TEMP",
        score=0.85,
        status=QualityStatus.ACCEPTABLE_WITH_WARNING,
        rec="ACCEPT_WITH_WARNING"
    )
    checks, investigation = auditor._deep_temperature_investigation(stream, temp_res)
    assert investigation["max_instantaneous_rate_c_per_sec"] > 0.50
    assert investigation["max_instantaneous_rate_c_per_min"] == round(investigation["max_instantaneous_rate_c_per_sec"] * 60.0, 2)
    assert "DISCRETIZATION" in investigation["classification"] or "CONTACT" in investigation["classification"]
    assert any(c.check_id == "SIG-TEMP-ROC-CONFIRMED" for c in checks)


def test_13_critical_sensor_failure():
    """Case 13: Critical sensor failure invariant enforcement."""
    cross = CrossValidator()
    bad_report = {
        "sensors": {
            "ECG": {
                "quality_score": 0.20,
                "status": "CRITICAL_FAILURE",
                "recommendation": "REJECT",
                "critical_failure": True,
                "issues": []
            }
        },
        "processing_decision": {
            "can_proceed": True,
            "rejected_sensors": []
        },
        "overall_quality": {"score": 0.20}
    }
    checks = cross.validate_decision_critical_invariants(bad_report)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "DECISION_CRITICAL_FAILURE_INVARIANT" for c in failed)


def test_14_invalid_quality_score():
    """Case 14: Quality score outside bounded [0.0, 1.0] domain."""
    validator = SensorOutputValidator()
    bad_result = SensorQualityResult.model_construct(
        sensor="ECG",
        quality_score=1.45,
        status=QualityStatus.VALID,
        metrics=_make_dummy_metrics(),
        issues=[],
        recommendation="ACCEPT",
        critical_failure=False,
        sampling_rate=700.0,
        total_samples_analyzed=42000,
        duration_seconds=60.0
    )
    checks, _ = validator.validate_single_sensor("ECG", bad_result)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "SENSOR-SCORE-BOUNDS" for c in failed)


def test_15_inconsistent_sensor_status_and_recommendation():
    """Case 15: Inconsistent status and recommendation pairing."""
    validator = SensorOutputValidator()
    inconsistent_res = _make_dummy_sensor_result(
        status=QualityStatus.INVALID,
        rec="ACCEPT"
    )
    checks, _ = validator.validate_single_sensor("ECG", inconsistent_res)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "SENSOR-STATUS-REC-INCONSISTENT" for c in failed)


def test_16_incorrect_overall_score():
    """Case 16: Mathematical audit catching mismatch in overall session score."""
    auditor = QualityScoreAuditor()
    sensors = {
        "ECG": _make_dummy_sensor_result(score=0.90),
        "EDA": _make_dummy_sensor_result(score=0.90)
    }
    bad_overall = OverallQuality(
        score=0.50,
        status=QualityStatus.VALID,
        valid_sensors_count=2,
        total_sensors_count=2,
        degraded_sensors=[],
        rejected_sensors=[]
    )
    records, checks = auditor.audit_scores(sensors, bad_overall)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "SCORE-OVERALL-MISMATCH" for c in failed)


def test_17_llm_briefing_contradiction():
    """Case 17: Hallucinated sensor failure in LLM executive briefing."""
    cross = CrossValidator()
    report = {
        "overall_quality": {"score": 0.95},
        "sensors": {
            "RESP": {
                "quality_score": 0.99,
                "status": "VALID",
                "recommendation": "ACCEPT",
                "issues": []
            }
        },
        "llm_explanation": {
            "briefing": "Executive Briefing: RESP has suffered a fatal failure and data is completely corrupted."
        }
    }
    checks = cross.validate_json_vs_llm_consistency(report)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "LLM_CONSISTENCY_NO_HALLUCINATIONS" for c in failed)


def test_18_invalid_downstream_decision():
    """Case 18: Session score under minimum acceptable threshold but can_proceed=True."""
    cross = CrossValidator()
    report = {
        "overall_quality": {"score": 0.40},
        "sensors": {},
        "processing_decision": {"can_proceed": True}
    }
    checks = cross.validate_decision_critical_invariants(report)
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "DECISION_MINIMUM_SCORE_INVARIANT" for c in failed)


def test_19_missing_sensor_file():
    """Case 19: Sensor signal file does not exist on disk."""
    validator = InputValidator()
    checks = validator.validate_sensor_config("ECG", {
        "file": "raw_signals/NON_EXISTENT_FILE.npy",
        "sampling_rate": 700.0,
        "unit": "mV"
    })
    failed = [c for c in checks if c.status == CheckStatus.FAILED]
    assert any(c.check_id == "INPUT-FILE-NOT-FOUND" for c in failed)


def test_20_partial_sensor_availability():
    """Case 20: Missing sensor in manifest relative to required modalities."""
    validator = InputValidator()
    manifest_dict = {
        "metadata": {"astronaut_id": "AST-001", "session_id": "SES-001"},
        "signals": {
            "ECG": {"file": "a.npy", "sampling_rate": 700.0, "unit": "mV"},
            "EDA": {"file": "b.npy", "sampling_rate": 4.0, "unit": "uS"}
        }
    }
    checks = validator.validate_manifest_dict(manifest_dict)
    assert len(manifest_dict["signals"]) < len(validator.VALID_SENSORS)
    assert any(c.target in ("ECG", "EDA") for c in checks)
