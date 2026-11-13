"""Test suite for Area F: Safe Baseline Update Manager, Anti-Contamination Guards, and Rollback."""
from datetime import datetime, timedelta
import pytest

from personal_health.baseline.schemas import (
    ObservationSession,
    BaselineContextType,
    BaselineReadinessState,
    UpdateRejectionReason
)
from personal_health.baseline.statistical_engine import RobustBaselineEngine
from personal_health.baseline.repository import PersonalBaselineRepository
from personal_health.baseline.update_manager import SafeBaselineUpdateManager

def create_session(
    session_id: str,
    astronaut_id: str,
    timestamp: datetime,
    hr: float = 70.0,
    rmssd: float = 45.0,
    sqa_score: float = 0.95
) -> ObservationSession:
    return ObservationSession(
        session_id=session_id,
        astronaut_id=astronaut_id,
        timestamp=timestamp,
        features={
            "hr_mean_bpm": hr,
            "hrv_rmssd_ms": rmssd,
            "resp_rate_bpm": 14.0,
            "temp_mean": 36.6,
            "eda_mean": 2.0
        },
        context_type=BaselineContextType.NOMINAL_OPERATIONAL,
        sqa_overall_score=sqa_score,
        sensor_quality_scores={
            "ECG": sqa_score,
            "RESP": sqa_score,
            "TEMP": sqa_score,
            "EDA": sqa_score
        }
    )

def test_01_anti_contamination_guard_rejects_anomalous_session():
    """Verify an observation session with composite anomaly z >= 3.0 is rejected to prevent baseline poisoning."""
    repo = PersonalBaselineRepository()
    engine = RobustBaselineEngine()
    update_mgr = SafeBaselineUpdateManager(repository=repo)
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    # Establish baseline for ASTRO-01 at 70 bpm
    sessions = [create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(days=i), hr=70.0) for i in range(5)]
    profile = engine.compute_baseline_profile("ASTRO-01", sessions)
    repo.save_baseline(profile, reason="Initial established baseline")

    # Attempt to update with a severe tachycardia spike (HR=130 bpm)
    spike_session = create_session("S_SPIKE", "ASTRO-01", base_t + timedelta(days=6), hr=130.0)
    success, updated_p, audit_log = update_mgr.update_baseline_with_session(
        session=spike_session,
        all_historical_sessions=sessions
    )

    assert success is False
    assert audit_log.is_successful is False
    assert audit_log.rejection_reason == UpdateRejectionReason.ANOMALOUS_OBSERVATION
    # Current active baseline version remains unchanged
    assert repo.get_baseline("ASTRO-01").baseline_version == 1

def test_02_poor_sensor_quality_rejection():
    """Verify session with degraded sensor quality (SQA < 0.70) is strictly rejected from updating baseline."""
    repo = PersonalBaselineRepository()
    engine = RobustBaselineEngine()
    update_mgr = SafeBaselineUpdateManager(repository=repo)
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    sessions = [create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(days=i), hr=70.0) for i in range(5)]
    profile = engine.compute_baseline_profile("ASTRO-01", sessions)
    repo.save_baseline(profile)

    # Low SQA session
    degraded_session = create_session("S_DEG", "ASTRO-01", base_t + timedelta(days=6), hr=71.0, sqa_score=0.45)
    success, _, audit_log = update_mgr.update_baseline_with_session(
        session=degraded_session,
        all_historical_sessions=sessions
    )

    assert success is False
    assert audit_log.is_successful is False
    assert audit_log.rejection_reason == UpdateRejectionReason.POOR_SENSOR_QUALITY

def test_03_cross_astronaut_update_rejection():
    """Verify attempting to update ASTRO-01's baseline using a session labeled ASTRO-02 is rejected."""
    repo = PersonalBaselineRepository()
    engine = RobustBaselineEngine()
    update_mgr = SafeBaselineUpdateManager(repository=repo)
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    sessions = [create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(days=i), hr=70.0) for i in range(5)]
    profile = engine.compute_baseline_profile("ASTRO-01", sessions)
    repo.save_baseline(profile)

    # Session belonging to ASTRO-02
    other_session = create_session("S_OTHER", "ASTRO-02", base_t + timedelta(days=6), hr=71.0)
    is_eligible, rej_code, reason = update_mgr.evaluate_update_eligibility(
        session=other_session,
        current_profile=profile
    )

    assert is_eligible is False
    assert rej_code == UpdateRejectionReason.CROSS_ASTRONAUT_VIOLATION
    assert "Cross-astronaut violation" in reason

def test_04_version_increment_and_audit_logging():
    """Verify safe nominal session updates increment baseline version and create audit log."""
    repo = PersonalBaselineRepository()
    engine = RobustBaselineEngine()
    update_mgr = SafeBaselineUpdateManager(repository=repo)
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    sessions = [create_session(f"S_{i}", "ASTRO-UPDATE", base_t + timedelta(days=i), hr=70.0) for i in range(5)]
    p_v1 = engine.compute_baseline_profile("ASTRO-UPDATE", sessions)
    repo.save_baseline(p_v1, reason="Initial calibration")

    # Normal new session (HR=71 bpm)
    nom_session = create_session("S_NOM_NEW", "ASTRO-UPDATE", base_t + timedelta(days=6), hr=71.0)
    success, updated_p, audit_log = update_mgr.update_baseline_with_session(
        session=nom_session,
        all_historical_sessions=sessions,
        reason="Nominal operational day update"
    )

    assert success is True
    assert updated_p is not None
    assert updated_p.baseline_version == 2
    assert audit_log.is_successful is True
    assert audit_log.from_version == 1
    assert audit_log.to_version == 2
    assert audit_log.rejection_reason is None

    # Check repository state
    active = repo.get_baseline("ASTRO-UPDATE")
    assert active.baseline_version == 2

def test_05_snapshot_rollback():
    """Verify rollback restores previous baseline snapshot version and logs event."""
    repo = PersonalBaselineRepository()
    engine = RobustBaselineEngine()
    update_mgr = SafeBaselineUpdateManager(repository=repo)
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    # Version 1 (HR=70.0)
    sessions_v1 = [create_session(f"S_{i}", "ASTRO-ROLL", base_t + timedelta(days=i), hr=70.0) for i in range(5)]
    p_v1 = engine.compute_baseline_profile("ASTRO-ROLL", sessions_v1)
    p_v1.baseline_version = 1
    repo.save_baseline(p_v1, reason="Calibration v1")

    # Version 2 (HR=74.0)
    sessions_v2 = sessions_v1 + [create_session("S_5", "ASTRO-ROLL", base_t + timedelta(days=5), hr=74.0)]
    p_v2 = engine.compute_baseline_profile("ASTRO-ROLL", sessions_v2)
    p_v2.baseline_version = 2
    repo.save_baseline(p_v2, reason="Update v2")

    assert repo.get_baseline("ASTRO-ROLL").baseline_version == 2

    # Execute rollback to Version 1
    rolled_back = update_mgr.rollback(
        astronaut_id="ASTRO-ROLL",
        target_version=1,
        reason="Sensor calibration discrepancy discovered in v2"
    )

    assert rolled_back is not None
    # Version advances monotonically to 3 upon rollback restoration
    assert rolled_back.baseline_version == 3
    assert "Restored from historical snapshot version 1" in rolled_back.provenance_notes

    # Active baseline in repo reflects rollback
    active = repo.get_baseline("ASTRO-ROLL")
    assert active.baseline_version == 3
    assert active.general_profile.features["hr_mean_bpm"].median == 70.0
