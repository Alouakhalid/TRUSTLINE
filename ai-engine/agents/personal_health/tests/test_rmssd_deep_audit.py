"""Deep audit test suite for ECG feature extraction, R-peak validation, and RMSSD calculation."""
import numpy as np
import pytest
from pathlib import Path

from personal_health.services.sensor_integration_service import ValidatedSensorStream
from personal_health.services.feature_extraction_service import FeatureExtractionService
from personal_health.schemas.physiological_features import (
    HRVStatus,
    MeasurementStatus,
    ExtractedFeature
)

def make_stream(data: np.ndarray, fs: float, status: str = "VALID") -> ValidatedSensorStream:
    """Helper creating a ValidatedSensorStream for testing."""
    duration = len(data) / fs if fs > 0.0 else 0.0
    timestamps = np.arange(len(data)) / fs if fs > 0.0 else np.zeros(len(data))
    return ValidatedSensorStream(
        sensor_name="ECG",
        data=data,
        timestamps=timestamps,
        sampling_rate=fs,
        unit="mV",
        quality_score=0.98,
        status=status,
        warnings=[]
    )

def test_01_real_ecg_zero_variability_reproduction():
    """Verify that actual recorded ECG yields ZERO_VARIABILITY and RMSSD=0.0 ms."""
    raw_ecg_path = Path("ai-engine/agents/sensor_quality/data/raw_signals/ECG/ecg.npy")
    if not raw_ecg_path.exists():
        raw_ecg_path = Path(__file__).resolve().parents[3] / "sensor_quality" / "data" / "raw_signals" / "ECG" / "ecg.npy"

    assert raw_ecg_path.exists(), f"Raw ECG file not found at {raw_ecg_path}"
    raw_ecg = np.load(raw_ecg_path)
    fs = 700.0
    stream = make_stream(raw_ecg, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.hrv_status == HRVStatus.ZERO_VARIABILITY
    assert diag.rmssd_ms == 0.0
    assert diag.total_r_peaks_detected > 50
    assert diag.valid_nn_intervals > 50
    assert any("unvarying" in w.lower() or "zero" in w.lower() for w in diag.processing_warnings)

    rmssd_feat = next(f for f in features if f.feature_name == "hrv_rmssd_ms")
    assert rmssd_feat.value == 0.0
    assert rmssd_feat.measurement_status == MeasurementStatus.INSUFFICIENT_VARIANCE
    assert rmssd_feat.validity_status == "INVALID"

def test_02_r_peak_refractory_distance_enforcement():
    """Verify refractory distance prevents duplicate peak detections within 250 ms."""
    fs = 1000.0
    signal = np.zeros(3000)
    signal[500] = 5.0
    signal[600] = 4.8
    signal[1500] = 5.0
    stream = make_stream(signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.total_r_peaks_detected == 2

def test_03_exact_rr_interval_formula_unrounded():
    """Verify exact RR interval formula calculation without premature rounding."""
    fs = 500.0
    r_peaks = np.array([500, 950, 1400])
    raw_signal = np.zeros(2000)
    for p in r_peaks:
        raw_signal[p] = 4.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.total_r_peaks_detected == 3
    assert diag.valid_nn_intervals == 2
    expected_rr_ms = (450 / 500.0) * 1000.0
    assert np.isclose(diag.mean_rr_ms, expected_rr_ms)
    assert diag.rmssd_ms == 0.0

def test_04_artifact_policy_filtering():
    """Verify RR intervals outside 270 ms to 2000 ms are classified as artifacts."""
    fs = 1000.0
    raw_signal = np.zeros(6000)
    peak_indices = [500, 760, 1860, 2860]
    for p in peak_indices:
        raw_signal[p] = 5.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.total_r_peaks_detected == 4
    assert diag.invalid_interval_count == 1
    assert diag.valid_nn_intervals == 2
    assert diag.hrv_status == HRVStatus.VALID

def test_05_synthetic_variable_ecg_valid_rmssd():
    """Verify physiologically variable ECG yields VALID status and accurate positive RMSSD."""
    fs = 1000.0
    raw_signal = np.zeros(10000)
    current_idx = 500
    peak_intervals = [800, 850, 800, 850, 800, 850, 800, 850]
    raw_signal[current_idx] = 5.0
    for interval in peak_intervals:
        current_idx += interval
        raw_signal[current_idx] = 5.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.hrv_status == HRVStatus.VALID
    assert np.isclose(diag.rmssd_ms, 50.0)
    rmssd_feat = next(f for f in features if f.feature_name == "hrv_rmssd_ms")
    assert rmssd_feat.measurement_status == MeasurementStatus.AVAILABLE
    assert rmssd_feat.validity_status == "VALID"

def test_06_zero_variability_status_assignment():
    """Verify identical RR intervals trigger ZERO_VARIABILITY status."""
    fs = 1000.0
    raw_signal = np.zeros(6000)
    for p in [500, 1300, 2100, 2900, 3700]:
        raw_signal[p] = 5.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.hrv_status == HRVStatus.ZERO_VARIABILITY
    assert diag.rmssd_ms == 0.0

def test_07_insufficient_r_peaks_handling():
    """Verify signal with fewer than 3 peaks returns INSUFFICIENT_R_PEAKS."""
    fs = 500.0
    raw_signal = np.zeros(2000)
    raw_signal[500] = 5.0
    raw_signal[1200] = 5.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.hrv_status == HRVStatus.INSUFFICIENT_R_PEAKS
    assert diag.valid_nn_intervals == 0
    assert len(features) == 0

def test_08_empty_or_nan_ecg_signal():
    """Verify empty or NaN-containing ECG returns INVALID_ECG_SIGNAL safely."""
    fs = 500.0
    nan_signal = np.full(1000, np.nan)
    stream = make_stream(nan_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.hrv_status == HRVStatus.INVALID_ECG_SIGNAL
    assert len(features) == 0

def test_09_all_intervals_artifacts_handling():
    """Verify signal where all intervals are artifacts returns INVALID_INTERVALS."""
    fs = 1000.0
    raw_signal = np.zeros(4000)
    for p in [500, 760, 1020, 1280]:
        raw_signal[p] = 5.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.hrv_status == HRVStatus.INVALID_INTERVALS
    assert diag.valid_nn_intervals == 0
    assert diag.invalid_interval_count == 3

def test_10_invalid_sampling_rate_safety():
    """Verify zero or negative sampling rate handles safely without crashing."""
    raw_signal = np.zeros(1000)
    raw_signal[200] = 5.0
    raw_signal[500] = 5.0
    raw_signal[800] = 5.0
    stream = make_stream(raw_signal, 0.0)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.hrv_status == HRVStatus.INVALID_ECG_SIGNAL

def test_11_hrv_diagnostic_report_integrity():
    """Verify all fields in HRVDiagnosticReport are properly populated."""
    fs = 1000.0
    raw_signal = np.zeros(6000)
    for p in [500, 1300, 2150, 3000, 3850]:
        raw_signal[p] = 5.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.total_r_peaks_detected == 5
    assert diag.total_rr_intervals == 4
    assert diag.valid_nn_intervals == 4
    assert diag.invalid_interval_count == 0
    assert diag.ecg_sampling_rate == 1000.0
    assert diag.ecg_duration_seconds == 6.0
    assert diag.hrv_status == HRVStatus.VALID
    assert diag.rmssd_ms > 0.0
    assert isinstance(diag.detection_algorithm, str)

def test_12_rmssd_feature_description_autonomic_regulation():
    """Verify RMSSD extraction method description specifies autonomic regulation metric."""
    fs = 1000.0
    raw_signal = np.zeros(4000)
    for p in [500, 1300, 2100, 2900]:
        raw_signal[p] = 5.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    rmssd_feat = next(f for f in features if f.feature_name == "hrv_rmssd_ms")
    assert "Autonomic Regulation" in rmssd_feat.extraction_method

def test_13_ecg_missing_sections_flatline_gap():
    """Verify telemetry gap (>2000 ms) is classified as invalid interval without corrupting valid NN intervals."""
    fs = 1000.0
    raw_signal = np.zeros(12000)
    for p in [500, 1300, 2100, 7500, 8300, 9200]:
        raw_signal[p] = 5.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.total_r_peaks_detected == 6
    assert diag.invalid_interval_count == 1
    assert diag.valid_nn_intervals == 4
    assert diag.hrv_status == HRVStatus.VALID

def test_14_ecg_motion_artifacts_and_high_frequency_noise():
    """Verify refractory distance and peak prominence reject high-frequency noise spikes."""
    fs = 1000.0
    np.random.seed(42)
    noise = np.random.normal(0, 0.02, 5000)
    raw_signal = noise.copy()
    for p in [500, 1300, 2150, 3000, 3850]:
        raw_signal[p] += 4.5
    raw_signal[650] += 2.0
    raw_signal[720] += 0.1
    raw_signal[1450] += 2.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.total_r_peaks_detected == 5
    assert diag.valid_nn_intervals == 4
    assert diag.hrv_status == HRVStatus.VALID

def test_15_ecg_irregular_rr_intervals_handling():
    """Verify irregular but physiological RR intervals yield valid non-zero RMSSD."""
    fs = 1000.0
    raw_signal = np.zeros(10000)
    current = 400
    intervals = [750, 820, 780, 860, 800, 840]
    raw_signal[current] = 5.0
    for itv in intervals:
        current += itv
        raw_signal[current] = 5.0
    stream = make_stream(raw_signal, fs)

    svc = FeatureExtractionService()
    features, diag = svc._extract_ecg_features(stream)

    assert diag is not None
    assert diag.hrv_status == HRVStatus.VALID
    assert diag.rmssd_ms > 10.0
    assert diag.valid_nn_intervals == len(intervals)
