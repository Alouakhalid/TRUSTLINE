"""Stress Test 02: Invalid and corrupted telemetry data validation and quarantine."""
import copy
import json
import numpy as np
import pytest
from pathlib import Path
from supervisor.config.settings import get_supervisor_settings
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
from sensor_quality.core.quality_engine import QualityEngine
from sensor_quality.schemas.signal_schema import SensorStreamData

def test_01_nan_and_infinity_in_signal_buffer():
    """Verify that QualityEngine rejects or degrades signals containing NaN and Inf."""
    engine = QualityEngine()
    fs = 100.0
    n = 1000
    times = np.linspace(0, n / fs, n)
    sig_nan = np.sin(2 * np.pi * 1.2 * times)
    sig_nan[100:250] = np.nan
    sig_nan[300:350] = np.inf

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig_nan,
        timestamps=times,
        duration_seconds=n / fs,
        total_samples=n
    )

    res = engine.inspect_stream(stream)
    assert res.quality_score < 0.8 or res.critical_failure or len(res.issues) > 0
    assert any("MISSING" in iss.reason_code or "NAN" in iss.reason_code for iss in res.issues) or res.metrics.missing_sample_ratio > 0.0

def test_02_empty_signal_arrays():
    """Verify that zero-length signal arrays are rejected gracefully without uncaught exceptions."""
    engine = QualityEngine()
    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=100.0,
        unit="mV",
        data=np.array([], dtype=float),
        timestamps=np.array([], dtype=float),
        duration_seconds=0.0,
        total_samples=0
    )

    res = engine.inspect_stream(stream)
    assert res.status.value in ("INVALID", "CRITICAL", "DEGRADED") or res.quality_score == 0.0 or res.critical_failure

def test_03_constant_flatline_signals():
    """Verify that flatline signals are deterministically detected and quarantined."""
    engine = QualityEngine()
    fs = 100.0
    n = 1000
    times = np.linspace(0, n / fs, n)
    sig_flat = np.ones(n) * 0.75

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig_flat,
        timestamps=times,
        duration_seconds=n / fs,
        total_samples=n
    )

    res = engine.inspect_stream(stream)
    assert res.metrics.flatline_ratio > 0.5 or any("FLATLINE" in iss.reason_code for iss in res.issues)

def test_04_zero_length_timestamps():
    """Verify that transmission gaps in timestamps are detected and reduce continuity score."""
    engine = QualityEngine()
    fs = 100.0
    n = 1000
    times = np.linspace(0, n / fs, n)
    times[500:] += 10.0
    sig = np.sin(2 * np.pi * 1.0 * times)

    stream = SensorStreamData(
        sensor="RESP",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=times,
        duration_seconds=(n / fs) + 10.0,
        total_samples=n
    )

    res = engine.inspect_stream(stream)
    assert res.metrics.continuity_score < 0.95 or any("GAP" in iss.reason_code for iss in res.issues)

def test_05_duplicate_timestamps():
    """Verify that duplicated timestamps degrade timestamp integrity metrics."""
    engine = QualityEngine()
    fs = 100.0
    n = 200
    times = np.arange(n, dtype=np.float64) / fs
    times[50:60] = times[49]
    sig = np.sin(times)

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=times,
        duration_seconds=2.0,
        total_samples=n
    )

    res = engine.inspect_stream(stream)
    assert res.metrics.timestamp_integrity < 1.0 or any("DUPLICATE" in iss.reason_code for iss in res.issues)

def test_06_non_monotonic_timestamps():
    """Verify that backwards time jumps trigger timestamp integrity warnings."""
    engine = QualityEngine()
    fs = 100.0
    n = 200
    times = np.arange(n, dtype=np.float64) / fs
    times[100] = times[90]
    sig = np.sin(times)

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=times,
        duration_seconds=2.0,
        total_samples=n
    )

    res = engine.inspect_stream(stream)
    assert res.metrics.timestamp_integrity <= 0.20 or any("INCONSISTENCY" in iss.reason_code for iss in res.issues)

def test_07_extreme_impulsive_spikes():
    """Verify that non-physiological spike artifacts are detected."""
    engine = QualityEngine()
    fs = 100.0
    n = 1000
    times = np.linspace(0, n / fs, n)
    sig = np.sin(2 * np.pi * 1.0 * times)
    sig[100:115] = 100.0

    stream = SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=times,
        duration_seconds=n / fs,
        total_samples=n
    )

    res = engine.inspect_stream(stream)
    assert res.metrics.artifact_ratio > 0.0 or any("SPIKE" in iss.reason_code for iss in res.issues)

def test_08_zero_variance_rr_rmssd_quarantined():
    """Verify that zero RMSSD is strictly quarantined from supporting normal cardiovascular regulation."""
    from supervisor.services.astronaut_communication_service import AstronautCommunicationService
    from supervisor.services.evidence_registry_service import EvidenceRegistryService

    state = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "personal_health_result": {
            "core_features": {
                "hr_mean_bpm": 72.0,
                "hrv_rmssd_ms": 0.0
            },
            "hrv_diagnostics": {
                "hrv_status": "ZERO_VARIABILITY"
            }
        }
    }

    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    rmssd_item = next((item for item in registry if item.evidence_id == "EV-PHY-HRV-RMSSD"), None)

    assert rmssd_item is not None
    assert rmssd_item.is_quarantined is True
    assert rmssd_item.validity_status == "INVALID"
    assert "quarantined" in rmssd_item.quarantine_reason

    resp = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        overall_risk="INSUFFICIENT_DATA",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_ratio=0.5,
        evaluated_domains=["CARDIOVASCULAR"],
        unevaluated_domains=[],
        recommended_actions=[],
        core_features={"hr_mean_bpm": 72.0, "hrv_rmssd_ms": 0.0}
    )

    assert "EV-PHY-HRV-RMSSD" in resp
    assert "INVALID" in resp
    assert "sensor artifact" not in resp
