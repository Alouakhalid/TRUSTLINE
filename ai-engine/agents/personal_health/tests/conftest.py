"""Pytest fixtures and mock configurations for Personal Health Agent test suite."""
import os
import sys
from pathlib import Path
import pytest
import numpy as np

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

cur = Path(__file__).resolve().parent.parent.parent.parent
if str(cur) not in sys.path:
    sys.path.insert(0, str(cur))
agent_dir = Path(__file__).resolve().parent.parent
if str(agent_dir.parent) not in sys.path:
    sys.path.insert(0, str(agent_dir.parent))

from personal_health.schemas.health_profile import (
    AstronautHealthProfile,
    BasicInformation,
    MedicalHistory,
    MedicationRecord,
    PsychologicalProfile,
    CognitiveProfile,
    PhysicalFitnessProfile
)
from personal_health.services.sensor_integration_service import ValidatedSensorStream

@pytest.fixture
def sample_health_profile() -> AstronautHealthProfile:
    """Fixture providing verified astronaut health profile."""
    basic = BasicInformation(
        astronaut_id="AST-TEST-01",
        age=36,
        height_cm=178.0,
        weight_kg=75.0,
        body_fat_percentage=15.0,
        blood_type="A_POS"
    )
    return AstronautHealthProfile(
        astronaut_id="AST-TEST-01",
        basic_info=basic,
        medical_history=MedicalHistory(),
        medications=[],
        psychological_profile=PsychologicalProfile(),
        cognitive_profile=CognitiveProfile(),
        physical_fitness=PhysicalFitnessProfile(),
        recent_health_events=[]
    )

@pytest.fixture
def mock_ecg_stream() -> ValidatedSensorStream:
    """Synthetic 700 Hz ECG stream with realistic R-peaks."""
    fs = 700.0
    duration = 10.0
    total_samples = int(fs * duration)
    t = np.arange(total_samples) / fs
    ecg_signal = np.zeros(total_samples)
    for beat_time in np.arange(0.8, duration, 0.833):
        idx = int(beat_time * fs)
        if idx < total_samples:
            ecg_signal[idx] = 1.5
    return ValidatedSensorStream(
        sensor_name="ECG",
        data=ecg_signal,
        timestamps=t,
        sampling_rate=fs,
        unit="mV",
        quality_score=0.98,
        status="VALID",
        warnings=[]
    )

@pytest.fixture
def mock_eda_stream() -> ValidatedSensorStream:
    """Synthetic 4 Hz EDA stream."""
    fs = 4.0
    duration = 10.0
    total_samples = int(fs * duration)
    t = np.arange(total_samples) / fs
    eda_data = np.full(total_samples, 4.5) + np.random.normal(0, 0.05, total_samples)
    return ValidatedSensorStream(
        sensor_name="EDA",
        data=eda_data,
        timestamps=t,
        sampling_rate=fs,
        unit="uS",
        quality_score=0.95,
        status="VALID",
        warnings=[]
    )

@pytest.fixture
def mock_resp_stream() -> ValidatedSensorStream:
    """Synthetic 700 Hz RESP stream with 14 breaths/min."""
    fs = 700.0
    duration = 10.0
    total_samples = int(fs * duration)
    t = np.arange(total_samples) / fs
    resp_signal = np.sin(2 * np.pi * 0.233 * t)
    return ValidatedSensorStream(
        sensor_name="RESP",
        data=resp_signal,
        timestamps=t,
        sampling_rate=fs,
        unit="mV",
        quality_score=0.96,
        status="VALID",
        warnings=[]
    )

@pytest.fixture
def mock_temp_stream() -> ValidatedSensorStream:
    """Synthetic 700 Hz TEMP stream."""
    fs = 700.0
    duration = 10.0
    total_samples = int(fs * duration)
    t = np.arange(total_samples) / fs
    temp_signal = np.full(total_samples, 33.5)
    return ValidatedSensorStream(
        sensor_name="TEMP",
        data=temp_signal,
        timestamps=t,
        sampling_rate=fs,
        unit="C",
        quality_score=0.99,
        status="VALID",
        warnings=[]
    )

@pytest.fixture
def mock_emg_stream() -> ValidatedSensorStream:
    """Synthetic 700 Hz EMG stream."""
    fs = 700.0
    duration = 10.0
    total_samples = int(fs * duration)
    t = np.arange(total_samples) / fs
    emg_signal = np.random.normal(0, 0.02, total_samples)
    return ValidatedSensorStream(
        sensor_name="EMG",
        data=emg_signal,
        timestamps=t,
        sampling_rate=fs,
        unit="mV",
        quality_score=0.97,
        status="VALID",
        warnings=[]
    )

@pytest.fixture
def mock_acc_stream() -> ValidatedSensorStream:
    """Synthetic 700 Hz ACC 3-axis stream."""
    fs = 700.0
    duration = 10.0
    total_samples = int(fs * duration)
    t = np.arange(total_samples) / fs
    acc_signal = np.zeros((total_samples, 3))
    acc_signal[:, 2] = 0.98
    return ValidatedSensorStream(
        sensor_name="ACC",
        data=acc_signal,
        timestamps=t,
        sampling_rate=fs,
        unit="g",
        quality_score=0.98,
        status="VALID",
        warnings=[]
    )
