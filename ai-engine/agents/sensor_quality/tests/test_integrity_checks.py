"""Tests for IntegrityChecker module."""
import pytest
import numpy as np
from sensor_quality_agent.core.integrity_checks import IntegrityChecker
from sensor_quality_agent.schemas.signal_schema import SensorStreamData, IssueSeverity
from sensor_quality_agent.explainability.reason_codes import ReasonCode

def test_clean_signal_integrity(clean_ecg_stream: SensorStreamData):
    checker = IntegrityChecker()
    valid_ratio, nan_ratio, issues = checker.check_integrity(clean_ecg_stream)
    assert valid_ratio == 1.0
    assert nan_ratio == 0.0
    assert len(issues) == 0

def test_missing_values_detected():
    fs = 100.0
    n = 1000
    t = np.arange(n) / fs
    data = np.ones(n, dtype=np.float32)
    data[100:200] = np.nan
    data[500:550] = np.inf

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=data,
        timestamps=t,
        duration_seconds=10.0,
        total_samples=n
    )

    checker = IntegrityChecker(max_acceptable_nan_ratio=0.05, critical_nan_ratio=0.20)
    valid_ratio, nan_ratio, issues = checker.check_integrity(stream)
    assert nan_ratio == 0.15
    assert valid_ratio == 0.85
    assert len(issues) == 1
    assert issues[0].reason_code == ReasonCode.SIGNAL_MISSING_VALUES.value
    assert issues[0].severity == IssueSeverity.HIGH

def test_empty_signal_triggers_critical():
    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=100.0,
        unit="mV",
        data=np.array([], dtype=np.float32),
        timestamps=np.array([], dtype=np.float64),
        duration_seconds=0.0,
        total_samples=0
    )
    checker = IntegrityChecker()
    valid_ratio, nan_ratio, issues = checker.check_integrity(stream)
    assert valid_ratio == 0.0
    assert nan_ratio == 1.0
    assert any(iss.reason_code == ReasonCode.SIGNAL_EMPTY.value for iss in issues)
    assert any(iss.severity == IssueSeverity.CRITICAL for iss in issues)
