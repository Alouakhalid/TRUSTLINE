"""Test suite for Area B: Robust Non-Parametric Statistics, Zero-MAD Handling, and Determinism."""
from datetime import datetime, timedelta
import pytest
import numpy as np

from personal_health.baseline.schemas import (
    ObservationSession,
    BaselineContextType,
    BaselineReadinessState
)
from personal_health.baseline.statistical_engine import (
    RobustBaselineEngine,
    PHYSIOLOGICAL_NOISE_FLOORS
)

def create_session(
    session_id: str,
    astronaut_id: str,
    timestamp: datetime,
    hr: float,
    rmssd: float = 40.0,
    resp: float = 14.0,
    temp: float = 36.6,
    eda: float = 2.0,
    context: BaselineContextType = BaselineContextType.REST
) -> ObservationSession:
    return ObservationSession(
        session_id=session_id,
        astronaut_id=astronaut_id,
        timestamp=timestamp,
        features={
            "hr_mean_bpm": hr,
            "hrv_rmssd_ms": rmssd,
            "resp_rate_bpm": resp,
            "temp_mean": temp,
            "eda_mean": eda
        },
        context_type=context,
        context=context,
        sqa_overall_score=0.95
    )

def test_01_non_parametric_statistics_accuracy():
    """Verify median, MAD, IQR, quantiles, mean, and std match numpy/scipy ground truth."""
    engine = RobustBaselineEngine()
    values = [68.0, 70.0, 72.0, 74.0, 76.0]

    stats = engine.calculate_feature_stats("hr_mean_bpm", values)
    assert stats is not None
    assert stats.median == 72.0
    assert stats.mean == 72.0
    assert stats.count == 5
    assert stats.q25 == 70.0
    assert stats.q75 == 74.0
    assert stats.iqr == 4.0
    # MAD of [68, 70, 72, 74, 76] around 72 is median of [4, 2, 0, 2, 4] -> median is 2.0
    assert stats.mad == 2.0
    assert stats.p10 == 68.8
    assert stats.p90 == 75.2

def test_02_zero_mad_fallback_handling():
    """Verify that constant signals (MAD=0) trigger noise-floor or IQR fallback without crashing."""
    engine = RobustBaselineEngine()
    # Identical values -> MAD = 0
    constant_values = [70.0, 70.0, 70.0, 70.0, 70.0, 70.0]

    stats = engine.calculate_feature_stats("hr_mean_bpm", constant_values)
    assert stats is not None
    assert stats.median == 70.0
    # MAD must be strictly positive, backed by physiological noise floor
    assert stats.mad > 0.0
    expected_floor = PHYSIOLOGICAL_NOISE_FLOORS.get("hr_mean_bpm", 1.0)
    assert stats.mad >= expected_floor

def test_03_multi_context_baseline_generation():
    """Verify multi-context engine produces separate profiles for REST, ACTIVITY, and NOMINAL_OPERATIONAL."""
    engine = RobustBaselineEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)
    sessions = []

    # 5 REST sessions (HR ~60)
    for i in range(5):
        sessions.append(create_session(
            session_id=f"S_REST_{i}",
            astronaut_id="ASTRO-01",
            timestamp=base_t + timedelta(days=i, hours=1),
            hr=60.0 + i,
            context=BaselineContextType.REST
        ))

    # 5 ACTIVITY sessions (HR ~120)
    for i in range(5):
        sessions.append(create_session(
            session_id=f"S_ACT_{i}",
            astronaut_id="ASTRO-01",
            timestamp=base_t + timedelta(days=i, hours=5),
            hr=120.0 + i,
            context=BaselineContextType.ACTIVITY
        ))

    profile = engine.compute_baseline_profile(
        astronaut_id="ASTRO-01",
        sessions=sessions,
        min_sessions=5,
        min_observation_days=3.0
    )

    assert profile.astronaut_id == "ASTRO-01"
    assert BaselineContextType.REST in profile.context_profiles
    assert BaselineContextType.ACTIVITY in profile.context_profiles
    assert BaselineContextType.NOMINAL_OPERATIONAL in profile.context_profiles

    rest_hr = profile.context_profiles[BaselineContextType.REST].features["hr_mean_bpm"].median
    act_hr = profile.context_profiles[BaselineContextType.ACTIVITY].features["hr_mean_bpm"].median
    nom_hr = profile.context_profiles[BaselineContextType.NOMINAL_OPERATIONAL].features["hr_mean_bpm"].median

    assert 60.0 <= rest_hr <= 65.0
    assert 120.0 <= act_hr <= 125.0
    assert rest_hr < nom_hr < act_hr

def test_04_determinism_and_reproducibility():
    """Verify compute_baseline_profile is completely deterministic on identical inputs."""
    engine = RobustBaselineEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)
    sessions = [
        create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(days=i), 70.0 + (i % 3))
        for i in range(6)
    ]

    p1 = engine.compute_baseline_profile("ASTRO-01", sessions)
    p2 = engine.compute_baseline_profile("ASTRO-01", sessions)

    p1_hr = p1.context_profiles[BaselineContextType.NOMINAL_OPERATIONAL].features["hr_mean_bpm"]
    p2_hr = p2.context_profiles[BaselineContextType.NOMINAL_OPERATIONAL].features["hr_mean_bpm"]

    assert p1_hr.median == p2_hr.median
    assert p1_hr.mad == p2_hr.mad
    assert p1_hr.iqr == p2_hr.iqr
    assert p1.total_valid_observations == p2.total_valid_observations

def test_05_outlier_robustness_median_vs_mean():
    """Verify median and MAD are resilient to a massive single-session artifact outlier."""
    engine = RobustBaselineEngine()
    # 9 nominal observations at 70 bpm, 1 artifact outlier at 180 bpm
    clean_vals = [70.0] * 9
    corrupted_vals = clean_vals + [180.0]

    stats_clean = engine.calculate_feature_stats("hr_mean_bpm", clean_vals)
    stats_corrupted = engine.calculate_feature_stats("hr_mean_bpm", corrupted_vals)

    # Median is completely unaffected
    assert stats_corrupted.median == 70.0
    # Mean is dragged by 11 bpm
    assert stats_corrupted.mean == 81.0
    # Outlier shift on median is 0.0, demonstrating non-parametric robustness
    assert abs(stats_corrupted.median - stats_clean.median) == 0.0
