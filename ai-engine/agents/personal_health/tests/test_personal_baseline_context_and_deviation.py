"""Test suite for Area D & E: Context-Aware Baselines, Robust Z-scores, Severity Tiers, and Persistence Tracking."""
from datetime import datetime, timedelta
import math
import pytest

from personal_health.baseline.schemas import (
    ObservationSession,
    BaselineContextType,
    BaselineReadinessState,
    DeviationSeverity,
    DeviationDirection
)
from personal_health.baseline.context_engine import ContextAwareBaselineEngine
from personal_health.baseline.statistical_engine import RobustBaselineEngine
from personal_health.baseline.deviation_engine import PersonalDeviationEngine

def create_session(
    session_id: str,
    astronaut_id: str,
    timestamp: datetime,
    hr: float = 70.0,
    context: BaselineContextType = BaselineContextType.REST
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
        context_type=context,
        context=context,
        sqa_overall_score=0.95
    )

def test_01_context_inference_from_accelerometry():
    """Verify context classifier correctly identifies REST, ACTIVITY, and NOMINAL_OPERATIONAL."""
    ctx_engine = ContextAwareBaselineEngine()

    # REST: Low motion and low HR
    rest_ctx = ctx_engine.infer_context_from_features({
        "acc_magnitude_mean": 1.0,
        "acc_magnitude_std": 0.02,
        "hr_mean_bpm": 65.0
    })
    assert rest_ctx == BaselineContextType.REST

    # ACTIVITY: High motion
    act_ctx = ctx_engine.infer_context_from_features({
        "acc_magnitude_mean": 1.45,
        "acc_magnitude_std": 0.35,
        "hr_mean_bpm": 130.0
    })
    assert act_ctx == BaselineContextType.ACTIVITY

    # NOMINAL_OPERATIONAL: Moderate acceleration
    nom_ctx = ctx_engine.infer_context_from_features({
        "acc_magnitude_mean": 1.08,
        "acc_magnitude_std": 0.06,
        "hr_mean_bpm": 80.0
    })
    assert nom_ctx == BaselineContextType.NOMINAL_OPERATIONAL

    # UNKNOWN: Missing accelerometry
    unk_ctx = ctx_engine.infer_context_from_features({"hr_mean_bpm": 75.0})
    assert unk_ctx == BaselineContextType.UNKNOWN

def test_02_transparent_contextual_fallback():
    """Verify fallback to NOMINAL_OPERATIONAL profile with explicit flag when requested context is uncalibrated."""
    stat_engine = RobustBaselineEngine()
    ctx_engine = ContextAwareBaselineEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    # Create baseline with 5 REST sessions only
    sessions = [create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(days=i), hr=62.0) for i in range(5)]
    profile = stat_engine.compute_baseline_profile("ASTRO-01", sessions)

    # Request ACTIVITY profile (which does not exist)
    resolved_profile, fallback_applied, reason = ctx_engine.resolve_contextual_profile(
        profile=profile,
        requested_context=BaselineContextType.ACTIVITY
    )

    assert fallback_applied is True
    assert "insufficient calibration data" in reason
    assert resolved_profile.context_type == BaselineContextType.NOMINAL_OPERATIONAL

def test_03_robust_z_score_and_severity_classification():
    """Verify robust Z-score calculation: 0.6745 * (x - median) / MAD and severity tiers."""
    stat_engine = RobustBaselineEngine()
    dev_engine = PersonalDeviationEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    # 5 sessions at 70 bpm with MAD = 2.0 (values: 68, 70, 70, 72, 74) -> median 70.0, MAD 2.0
    vals = [68.0, 70.0, 70.0, 72.0, 74.0]
    sessions = [create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(days=i), hr=vals[i]) for i in range(5)]
    profile = stat_engine.compute_baseline_profile("ASTRO-01", sessions)

    # 1. Observation at median (70 bpm) -> Z = 0.0 -> NOMINAL
    r_nom = dev_engine.evaluate_deviation(
        baseline_profile=profile,
        current_features={"hr_mean_bpm": 70.0},
        session_id="S_TEST_NOM"
    )
    hr_nom = r_nom.feature_deviations["hr_mean_bpm"]
    assert hr_nom.robust_z_score == 0.0
    assert hr_nom.deviation_severity == DeviationSeverity.NOMINAL
    assert hr_nom.deviation_direction == DeviationDirection.NOMINAL

    # 2. Observation at 76 bpm -> diff = 6 bpm -> Z = 0.6745 * 6 / 2.0 = 2.024 -> MILD
    r_mild = dev_engine.evaluate_deviation(
        baseline_profile=profile,
        current_features={"hr_mean_bpm": 76.0},
        session_id="S_TEST_MILD"
    )
    hr_mild = r_mild.feature_deviations["hr_mean_bpm"]
    assert 2.0 <= hr_mild.robust_z_score <= 2.05
    assert hr_mild.deviation_severity == DeviationSeverity.MILD
    assert hr_mild.deviation_direction == DeviationDirection.ELEVATED

    # 3. Observation at 80 bpm -> diff = 10 bpm -> Z = 0.6745 * 10 / 2.0 = 3.373 -> MODERATE
    r_mod = dev_engine.evaluate_deviation(
        baseline_profile=profile,
        current_features={"hr_mean_bpm": 80.0},
        session_id="S_TEST_MOD"
    )
    hr_mod = r_mod.feature_deviations["hr_mean_bpm"]
    assert 3.3 <= hr_mod.robust_z_score <= 3.4
    assert hr_mod.deviation_severity == DeviationSeverity.MODERATE

    # 4. Observation at 55 bpm -> diff = -15 bpm -> Z = -5.059 -> SIGNIFICANT, DEPRESSED
    r_dep = dev_engine.evaluate_deviation(
        baseline_profile=profile,
        current_features={"hr_mean_bpm": 55.0},
        session_id="S_TEST_DEP"
    )
    hr_dep = r_dep.feature_deviations["hr_mean_bpm"]
    assert hr_dep.robust_z_score <= -5.0
    assert hr_dep.deviation_severity == DeviationSeverity.SIGNIFICANT
    assert hr_dep.deviation_direction == DeviationDirection.DEPRESSED

def test_04_composite_anomaly_score():
    """Verify composite anomaly score computes root-mean-square of multi-signal robust Z-scores."""
    stat_engine = RobustBaselineEngine()
    dev_engine = PersonalDeviationEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    sessions = [create_session(f"S_{i}", "ASTRO-01", base_t + timedelta(days=i), hr=70.0) for i in range(5)]
    profile = stat_engine.compute_baseline_profile("ASTRO-01", sessions)

    report = dev_engine.evaluate_deviation(
        baseline_profile=profile,
        current_features={
            "hr_mean_bpm": 78.0,
            "resp_rate_bpm": 20.0,
            "temp_mean": 37.5
        },
        session_id="S_MULTI"
    )

    z_vals = [d.robust_z_score for d in report.feature_deviations.values()]
    expected_rms = round(float(math.sqrt(sum(z ** 2 for z in z_vals) / len(z_vals))), 3)
    assert report.composite_deviation_score == expected_rms
    assert report.composite_deviation_score > 0.0

def test_05_safe_abstention_on_unestablished_baseline():
    """Verify deviation engine cleanly abstains without generating fabricated metrics when baseline is unestablished."""
    dev_engine = PersonalDeviationEngine()
    stat_engine = RobustBaselineEngine()

    # Create unestablished profile (only 1 session)
    s1 = [create_session("S1", "ASTRO-NEW", datetime.utcnow())]
    profile = stat_engine.compute_baseline_profile("ASTRO-NEW", s1)
    assert profile.readiness_state == BaselineReadinessState.INSUFFICIENT_DATA

    report = dev_engine.evaluate_deviation(
        baseline_profile=profile,
        current_features={"hr_mean_bpm": 105.0},
        session_id="S_LIVE"
    )

    assert report.abstention_reason is not None
    assert "insufficient validated observations" in report.abstention_reason
    assert report.composite_deviation_score == 0.0
    assert len(report.feature_deviations) == 0

def test_06_temporal_persistence_tracking():
    """Verify multi-window persistence tracking differentiates transient spike from sustained deviation."""
    stat_engine = RobustBaselineEngine()
    dev_engine = PersonalDeviationEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    sessions = [create_session(f"S_{i}", "ASTRO-PERSIST", base_t + timedelta(days=i), hr=70.0) for i in range(5)]
    profile = stat_engine.compute_baseline_profile("ASTRO-PERSIST", sessions)

    # 1. First anomalous session (transient spike) -> persistent should be False
    rep1 = dev_engine.evaluate_deviation(profile, {"hr_mean_bpm": 95.0}, session_id="S_SPK1")
    assert rep1.persistent_deviation_detected is False

    # 2. Second consecutive anomalous session -> still False (< 3 sessions)
    rep2 = dev_engine.evaluate_deviation(profile, {"hr_mean_bpm": 95.0}, session_id="S_SPK2")
    assert rep2.persistent_deviation_detected is False

    # 3. Third consecutive anomalous session -> True (sustaining pattern)
    rep3 = dev_engine.evaluate_deviation(profile, {"hr_mean_bpm": 95.0}, session_id="S_SPK3")
    assert rep3.persistent_deviation_detected is True
