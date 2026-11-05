"""Shared pytest fixtures for sensor quality agent tests."""
import sys
from pathlib import Path
root_dir = str(Path(__file__).resolve().parent.parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import pytest
import numpy as np
from sensor_quality_agent.schemas.signal_schema import SensorStreamData

@pytest.fixture
def clean_ecg_stream() -> SensorStreamData:
    fs = 700.0
    duration = 10.0
    n = int(fs * duration)
    t = np.linspace(0.0, duration, n, endpoint=False)
    sig = 0.5 * np.sin(2 * np.pi * 1.2 * t)
    return SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=t,
        duration_seconds=duration,
        total_samples=n
    )

@pytest.fixture
def flatline_ecg_stream() -> SensorStreamData:
    fs = 700.0
    duration = 10.0
    n = int(fs * duration)
    t = np.linspace(0.0, duration, n, endpoint=False)
    sig = np.ones(n, dtype=np.float32) * 1.25
    return SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=t,
        duration_seconds=duration,
        total_samples=n
    )

@pytest.fixture
def noisy_ecg_stream() -> SensorStreamData:
    fs = 700.0
    duration = 10.0
    n = int(fs * duration)
    t = np.linspace(0.0, duration, n, endpoint=False)
    rng = np.random.RandomState(42)
    sig = 0.5 * np.sin(2 * np.pi * 1.2 * t) + 1.2 * np.sin(2 * np.pi * 50.0 * t) + 0.8 * np.sin(2 * np.pi * 0.2 * t)
    return SensorStreamData(
        sensor="ECG",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=t,
        duration_seconds=duration,
        total_samples=n
    )

@pytest.fixture
def gap_timestamps_stream() -> SensorStreamData:
    fs = 100.0
    n = 500
    t = np.arange(n, dtype=np.float64) / fs
    t[250:] += 5.0
    sig = np.sin(2 * np.pi * 2.0 * t)
    return SensorStreamData(
        sensor="RESP",
        sampling_rate=fs,
        unit="mV",
        data=sig,
        timestamps=t,
        duration_seconds=float(t[-1]),
        total_samples=n
    )
