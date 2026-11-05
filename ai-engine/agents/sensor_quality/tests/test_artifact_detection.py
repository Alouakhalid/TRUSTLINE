"""Tests for ArtifactDetector, FlatlineDetector, and SensorValidator modules."""
import pytest
import numpy as np
from sensor_quality_agent.core.artifact_detection import ArtifactDetector
from sensor_quality_agent.core.flatline_detection import FlatlineDetector
from sensor_quality_agent.core.sensor_validation import SensorValidator
from sensor_quality_agent.schemas.signal_schema import SensorStreamData, IssueSeverity
from sensor_quality_agent.explainability.reason_codes import ReasonCode

def test_flatline_detection(flatline_ecg_stream: SensorStreamData):
    detector = FlatlineDetector()
    ratio, issues = detector.detect_flatline(flatline_ecg_stream)
    assert ratio >= 0.50
    assert any(iss.reason_code == ReasonCode.SENSOR_FLATLINE.value for iss in issues)

def test_clipping_detection():
    fs = 100.0
    n = 1000
    t = np.arange(n) / fs
    sig = np.sin(2 * np.pi * 1.0 * t)
    sig = np.clip(sig, -0.6, 0.6)

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=t,
        duration_seconds=10.0,
        total_samples=n
    )
    detector = ArtifactDetector()
    art_ratio, sat_ratio, issues = detector.detect_artifacts(stream)
    assert sat_ratio > 0.05
    assert any(iss.reason_code == ReasonCode.SIGNAL_CLIPPING.value for iss in issues)

def test_spike_detection():
    fs = 100.0
    n = 1000
    t = np.arange(n) / fs
    rng = np.random.RandomState(42)
    sig = 0.1 * rng.randn(n)
    sig[100] = 5.0
    sig[200] = -5.0
    sig[300] = 6.0
    sig[400] = 7.0
    sig[500] = -6.0
    sig[600] = 8.0

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=t,
        duration_seconds=10.0,
        total_samples=n
    )
    detector = ArtifactDetector()
    art_ratio, sat_ratio, issues = detector.detect_artifacts(stream)
    assert any(iss.reason_code == ReasonCode.SIGNAL_SPIKES.value for iss in issues)

def test_sensor_validation_temperature_limits():
    fs = 10.0
    n = 100
    t = np.arange(n) / fs
    sig = np.ones(n) * 65.0

    stream = SensorStreamData(
        sensor="TEMP",
        sampling_rate=fs,
        unit="C",
        data=sig,
        timestamps=t,
        duration_seconds=10.0,
        total_samples=n
    )
    validator = SensorValidator()
    is_valid, issues = validator.validate_sensor(stream)
    assert is_valid is False
    assert any(iss.reason_code == ReasonCode.TEMP_OUT_OF_RANGE.value for iss in issues)
