"""Tests for TemporalChecker module."""
import pytest
import numpy as np
from sensor_quality_agent.core.temporal_checks import TemporalChecker
from sensor_quality_agent.schemas.signal_schema import SensorStreamData, IssueSeverity
from sensor_quality_agent.explainability.reason_codes import ReasonCode

def test_clean_temporal_integrity(clean_ecg_stream: SensorStreamData):
    checker = TemporalChecker()
    ts_integrity, continuity, issues = checker.check_temporal_integrity(clean_ecg_stream)
    assert ts_integrity >= 0.95
    assert continuity >= 0.95
    assert len(issues) == 0

def test_gap_detection(gap_timestamps_stream: SensorStreamData):
    checker = TemporalChecker()
    ts_integrity, continuity, issues = checker.check_temporal_integrity(gap_timestamps_stream)
    assert any(iss.reason_code == ReasonCode.TIMESTAMP_GAP_DETECTED.value for iss in issues)
    assert continuity < 0.95

def test_backwards_timestamps_detected():
    fs = 100.0
    n = 200
    t = np.arange(n, dtype=np.float64) / fs
    t[100] = t[90]
    data = np.zeros(n, dtype=np.float32)

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=data,
        timestamps=t,
        duration_seconds=2.0,
        total_samples=n
    )
    checker = TemporalChecker()
    ts_integrity, continuity, issues = checker.check_temporal_integrity(stream)
    assert any(iss.reason_code == ReasonCode.TIMESTAMP_INCONSISTENCY.value for iss in issues)
    assert any(iss.severity == IssueSeverity.CRITICAL for iss in issues)
    assert ts_integrity <= 0.20

def test_duplicate_timestamps_detected():
    fs = 100.0
    n = 200
    t = np.arange(n, dtype=np.float64) / fs
    t[50] = t[49]
    t[80] = t[79]
    data = np.zeros(n, dtype=np.float32)

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=data,
        timestamps=t,
        duration_seconds=2.0,
        total_samples=n
    )
    checker = TemporalChecker()
    ts_integrity, continuity, issues = checker.check_temporal_integrity(stream)
    assert any(iss.reason_code == ReasonCode.TIMESTAMP_DUPLICATES.value for iss in issues)
