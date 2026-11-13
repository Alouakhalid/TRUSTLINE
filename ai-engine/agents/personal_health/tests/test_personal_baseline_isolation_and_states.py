"""Test suite for Area C: Astronaut Identity Isolation, State Machine Transitions, and Snapshot Persistence."""
from datetime import datetime, timedelta
import pytest

from personal_health.baseline.schemas import (
    ObservationSession,
    BaselineContextType,
    BaselineReadinessState,
    PersonalBaselineProfile
)
from personal_health.baseline.statistical_engine import RobustBaselineEngine
from personal_health.baseline.repository import PersonalBaselineRepository
from personal_health.services.baseline_interface import PersonalBaselineInterface
from personal_health.schemas.assessment import BaselineStatus

def create_session(
    session_id: str,
    astronaut_id: str,
    timestamp: datetime,
    hr: float = 70.0
) -> ObservationSession:
    return ObservationSession(
        session_id=session_id,
        astronaut_id=astronaut_id,
        timestamp=timestamp,
        features={
            "hr_mean_bpm": hr,
            "hrv_rmssd_ms": 45.0,
            "resp_rate_bpm": 14.0,
            "temp_mean": 36.6,
            "eda_mean": 2.0
        },
        context_type=BaselineContextType.NOMINAL_OPERATIONAL,
        sqa_overall_score=0.95
    )

def test_01_astronaut_identity_isolation():
    """Verify profiles for AST-001 and AST-002 are completely isolated and never cross-bleed."""
    repo = PersonalBaselineRepository()
    engine = RobustBaselineEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    # Calibrate AST-001 (HR ~60)
    sessions_astro1 = [
        create_session(f"S1_{i}", "ASTRO-01", base_t + timedelta(days=i), hr=60.0 + i)
        for i in range(5)
    ]
    p1 = engine.compute_baseline_profile("ASTRO-01", sessions_astro1)
    repo.save_baseline(p1, reason="ASTRO-01 calibration")

    # Calibrate AST-002 (HR ~90)
    sessions_astro2 = [
        create_session(f"S2_{i}", "ASTRO-02", base_t + timedelta(days=i), hr=90.0 + i)
        for i in range(5)
    ]
    p2 = engine.compute_baseline_profile("ASTRO-02", sessions_astro2)
    repo.save_baseline(p2, reason="ASTRO-02 calibration")

    # Retrieve both profiles from repository
    retrieved_1 = repo.get_baseline("ASTRO-01")
    retrieved_2 = repo.get_baseline("ASTRO-02")

    assert retrieved_1 is not None
    assert retrieved_2 is not None
    assert retrieved_1.astronaut_id == "ASTRO-01"
    assert retrieved_2.astronaut_id == "ASTRO-02"

    p1_hr = retrieved_1.general_profile.features["hr_mean_bpm"].median
    p2_hr = retrieved_2.general_profile.features["hr_mean_bpm"].median

    assert 60.0 <= p1_hr <= 64.0
    assert 90.0 <= p2_hr <= 94.0
    assert p1_hr != p2_hr

def test_02_rejection_of_unverified_astronaut():
    """Verify unknown or unverified astronaut identities are strictly rejected."""
    repo = PersonalBaselineRepository()
    engine = RobustBaselineEngine()
    sessions = [create_session(f"S_{i}", "AST-UNKNOWN", datetime.utcnow()) for i in range(5)]

    with pytest.raises(ValueError):
        engine.compute_baseline_profile("AST-UNKNOWN", sessions)

    with pytest.raises(ValueError):
        engine.compute_baseline_profile("", sessions)

    assert repo.get_baseline("UNKNOWN") is None
    assert repo.get_baseline("AST-UNKNOWN") is None

def test_03_readiness_state_machine_transitions():
    """Verify state transitions: INSUFFICIENT_DATA (<3) -> PROVISIONAL (3..4) -> ESTABLISHED (>=5 across >=2 days)."""
    engine = RobustBaselineEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    # 1. 2 sessions -> INSUFFICIENT_DATA
    s_2 = [create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(hours=i)) for i in range(2)]
    p_insuf = engine.compute_baseline_profile("ASTRO-01", s_2)
    assert p_insuf.readiness_state == BaselineReadinessState.INSUFFICIENT_DATA

    # 2. 3 sessions same day -> PROVISIONAL
    s_3 = [create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(hours=i)) for i in range(3)]
    p_prov = engine.compute_baseline_profile("ASTRO-01", s_3)
    assert p_prov.readiness_state == BaselineReadinessState.PROVISIONAL

    # 3. 5 sessions across 3 distinct days -> ESTABLISHED
    s_5 = [create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(days=i)) for i in range(5)]
    p_est = engine.compute_baseline_profile("ASTRO-01", s_5)
    assert p_est.readiness_state == BaselineReadinessState.ESTABLISHED

def test_04_baseline_interface_state_mapping():
    """Verify PersonalBaselineInterface maps readiness states to BaselineStatus correctly."""
    repo = PersonalBaselineRepository()
    svc = PersonalBaselineInterface(repository=repo)
    engine = RobustBaselineEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    # Unestablished astronaut
    assert svc.get_baseline_status("ASTRO-UNSEEN") == BaselineStatus.NOT_AVAILABLE
    assert svc.is_baseline_available("ASTRO-UNSEEN") is False

    # Established astronaut
    s_5 = [create_session(f"S_{i}", "ASTRO-KNOWN", base_t + timedelta(days=i)) for i in range(5)]
    p = engine.compute_baseline_profile("ASTRO-KNOWN", s_5)
    repo.save_baseline(p)

    assert svc.get_baseline_status("ASTRO-KNOWN") == BaselineStatus.AVAILABLE
    assert svc.is_baseline_available("ASTRO-KNOWN") is True

def test_05_versioned_snapshot_isolation():
    """Verify updating a baseline creates immutable historical snapshots that can be queried."""
    repo = PersonalBaselineRepository()
    engine = RobustBaselineEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    sessions = [create_session(f"S_{i}", "ASTRO-VER", base_t + timedelta(days=i), hr=70.0) for i in range(5)]
    p_v1 = engine.compute_baseline_profile("ASTRO-VER", sessions)
    p_v1.baseline_version = 1
    repo.save_baseline(p_v1, reason="Version 1 calibration")

    # Update to Version 2
    p_v2 = p_v1.model_copy(deep=True, update={"baseline_version": 2})
    p_v2.general_profile.features["hr_mean_bpm"].median = 75.0
    repo.save_baseline(p_v2, reason="Version 2 update")

    # Check active is v2
    active = repo.get_baseline("ASTRO-VER")
    assert active.baseline_version == 2
    assert active.general_profile.features["hr_mean_bpm"].median == 75.0

    # Check history contains v1
    history = repo.get_baseline_history("ASTRO-VER")
    assert len(history) >= 2
    v1_record = next(h for h in history if h["baseline_version"] == 1)
    assert v1_record["baseline_version"] == 1
    assert "Version 1 calibration" in v1_record["change_reason"]
