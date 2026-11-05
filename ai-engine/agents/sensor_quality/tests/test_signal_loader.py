"""Tests for SignalLoader ingestion module."""
import pytest
from pathlib import Path
import numpy as np
from sensor_quality_agent.ingestion.signal_loader import SignalLoader
from sensor_quality_agent.schemas.input_schema import AstronautHealthManifest, SensorSignalConfig, RecordingMetadata

def test_signal_loader_memory_mapped(tmp_path: Path):
    loader = SignalLoader(base_dir=tmp_path)
    data_dir = tmp_path / "raw_signals" / "ECG"
    data_dir.mkdir(parents=True, exist_ok=True)
    arr = np.linspace(0.0, 1.0, 1400, dtype=np.float32)
    np.save(str(data_dir / "ecg.npy"), arr)

    config = SensorSignalConfig(
        file="raw_signals/ECG/ecg.npy",
        sampling_rate=700.0,
        unit="mV"
    )

    stream = loader.load_sensor_stream("ECG", config, mmap=True)
    assert stream.sensor == "ECG"
    assert stream.total_samples == 1400
    assert stream.sampling_rate == 700.0
    assert np.isclose(stream.duration_seconds, 2.0)
    assert len(stream.timestamps) == 1400

def test_signal_loader_path_traversal_protection(tmp_path: Path):
    with pytest.raises(ValueError, match="path traversal prohibited"):
        SensorSignalConfig(
            file="../../etc/passwd",
            sampling_rate=100.0,
            unit="mV"
        )

def test_sliding_windows(tmp_path: Path):
    loader = SignalLoader(base_dir=tmp_path)
    fs = 10.0
    total = 300
    t = np.arange(total) / fs
    sig = np.sin(t)
    data_dir = tmp_path / "raw_signals" / "EDA"
    data_dir.mkdir(parents=True, exist_ok=True)
    np.save(str(data_dir / "eda.npy"), sig)

    config = SensorSignalConfig(
        file="raw_signals/EDA/eda.npy",
        sampling_rate=fs,
        unit="uS"
    )
    stream = loader.load_sensor_stream("EDA", config, mmap=False)
    windows = list(loader.create_sliding_windows(stream, window_duration_sec=10.0, step_duration_sec=5.0))
    assert len(windows) > 0
    assert windows[0].data.shape[0] == 100
    assert windows[0].sampling_rate == 10.0
