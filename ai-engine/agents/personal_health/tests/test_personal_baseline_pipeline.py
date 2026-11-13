"""Test suite for Area A: Data Eligibility, Sanity Bounding, SQA Gating, and Telemetry Immutability."""
from datetime import datetime, timedelta
import copy
import pytest

from personal_health.baseline.schemas import (
    ObservationSession,
    BaselineContextType
)
from personal_health.baseline.data_pipeline import BaselineDataPipeline

def create_sample_session(
    session_id: str,
    astronaut_id: str = "ASTRO-01",
    timestamp: datetime = None,
    hr: float = 70.0,
    rmssd: float = 45.0,
    resp: float = 14.0,
    temp: float = 36.6,
    eda: float = 2.5,
    acc_std: float = 0.02,
    sqa_score: float = 0.95,
    context: BaselineContextType = BaselineContextType.REST
) -> ObservationSession:
    if timestamp is None:
        timestamp = datetime.utcnow()
    return ObservationSession(
        session_id=session_id,
        astronaut_id=astronaut_id,
        timestamp=timestamp,
        features={
            "hr_mean_bpm": hr,
            "hrv_rmssd_ms": rmssd,
            "resp_rate_bpm": resp,
            "temp_mean": temp,
            "eda_mean": eda,
            "acc_mag_std": acc_std
        },
        sqa_overall_score=sqa_score,
        sensor_quality_scores={
            "ECG": sqa_score,
            "RESP": sqa_score,
            "TEMP": sqa_score,
            "EDA": sqa_score,
            "ACC": sqa_score
        },
        context=context
    )

def test_01_sqa_quality_gating():
    """Verify that only sessions with SQA score >= 0.70 are accepted for baseline calibration."""
    pipeline = BaselineDataPipeline(min_sqa_score=0.70)
    base_time = datetime(2026, 11, 1, 8, 0, 0)

    s1 = create_sample_session("S1", timestamp=base_time, sqa_score=0.95)
    s2 = create_sample_session("S2", timestamp=base_time + timedelta(hours=1), sqa_score=0.69)
    s3 = create_sample_session("S3", timestamp=base_time + timedelta(hours=2), sqa_score=0.70)
    s4 = create_sample_session("S4", timestamp=base_time + timedelta(hours=3), sqa_score=0.45)

    valid_sessions, stats = pipeline.filter_calibration_sessions([s1, s2, s3, s4], "ASTRO-01")
    assert len(valid_sessions) == 2
    assert {s.session_id for s in valid_sessions} == {"S1", "S3"}
    assert stats["rejected_low_sqa"] == 2

def test_02_physiological_sanity_bounding():
    """Verify out-of-bounds physiological signals are purged while in-bound features are preserved."""
    pipeline = BaselineDataPipeline()
    base_time = datetime(2026, 11, 1, 8, 0, 0)

    # Session with HR=0 (physiologically impossible) and Temp=15.0°C (hypothermic dead or sensor error)
    s_invalid = create_sample_session("S_INV", timestamp=base_time, hr=0.0, temp=15.0, resp=14.0)
    # Session with HR=350 (sensor artifact)
    s_high = create_sample_session("S_HIGH", timestamp=base_time + timedelta(hours=1), hr=350.0)
    # Normal session
    s_norm = create_sample_session("S_NORM", timestamp=base_time + timedelta(hours=2), hr=72.0, temp=36.7)

    valid_sessions, stats = pipeline.filter_calibration_sessions([s_invalid, s_high, s_norm], "ASTRO-01")
    # All sessions might survive if at least one feature is valid, but the invalid features are removed
    s_inv_res = next(s for s in valid_sessions if s.session_id == "S_INV")
    assert "hr_mean_bpm" not in s_inv_res.features
    assert "temp_mean" not in s_inv_res.features
    assert "resp_rate_bpm" in s_inv_res.features

    s_high_res = next(s for s in valid_sessions if s.session_id == "S_HIGH")
    assert "hr_mean_bpm" not in s_high_res.features

    s_norm_res = next(s for s in valid_sessions if s.session_id == "S_NORM")
    assert s_norm_res.features["hr_mean_bpm"] == 72.0
    assert s_norm_res.features["temp_mean"] == 36.7

def test_03_zero_variability_hrv_artifact_exclusion():
    """Verify RMSSD < 1.0 ms is identified as zero-variability sensor artifact and excluded."""
    pipeline = BaselineDataPipeline()
    base_time = datetime(2026, 11, 1, 8, 0, 0)

    s1 = create_sample_session("S1", timestamp=base_time, rmssd=0.0)
    s2 = create_sample_session("S2", timestamp=base_time + timedelta(hours=1), rmssd=0.85)
    s3 = create_sample_session("S3", timestamp=base_time + timedelta(hours=2), rmssd=42.0)

    valid_sessions, stats = pipeline.filter_calibration_sessions([s1, s2, s3], "ASTRO-01")
    s1_res = next(s for s in valid_sessions if s.session_id == "S1")
    s2_res = next(s for s in valid_sessions if s.session_id == "S2")
    s3_res = next(s for s in valid_sessions if s.session_id == "S3")

    assert "hrv_rmssd_ms" not in s1_res.features
    assert "hrv_rmssd_ms" not in s2_res.features
    assert s3_res.features["hrv_rmssd_ms"] == 42.0
    assert stats["rejected_artifacts"] >= 2

def test_04_duplicate_observation_rejection():
    """Verify duplicate session timestamps are detected and purged to prevent sampling bias."""
    pipeline = BaselineDataPipeline()
    base_time = datetime(2026, 11, 1, 8, 0, 0)

    s1 = create_sample_session("S1", timestamp=base_time)
    s2 = create_sample_session("S2", timestamp=base_time) # duplicate timestamp
    s3 = create_sample_session("S3", timestamp=base_time + timedelta(hours=1))

    valid_sessions, stats = pipeline.filter_calibration_sessions([s1, s2, s3], "ASTRO-01")
    assert len(valid_sessions) == 2
    assert stats["rejected_duplicates"] == 1

def test_05_identity_isolation_at_ingestion():
    """Verify sessions belonging to another astronaut are strictly rejected during calibration."""
    pipeline = BaselineDataPipeline()
    base_time = datetime(2026, 11, 1, 8, 0, 0)

    s1 = create_sample_session("S1", astronaut_id="ASTRO-01", timestamp=base_time)
    s2 = create_sample_session("S2", astronaut_id="ASTRO-02", timestamp=base_time + timedelta(hours=1))
    s3 = create_sample_session("S3", astronaut_id="ASTRO-01", timestamp=base_time + timedelta(hours=2))

    valid_sessions, stats = pipeline.filter_calibration_sessions([s1, s2, s3], "ASTRO-01")
    assert len(valid_sessions) == 2
    assert all(s.astronaut_id == "ASTRO-01" for s in valid_sessions)
    assert stats["rejected_astronaut_mismatch"] == 1

def test_06_temporal_chronological_ordering():
    """Verify input sessions are sorted chronologically regardless of incoming arrival order."""
    pipeline = BaselineDataPipeline()
    t1 = datetime(2026, 11, 1, 8, 0, 0)
    t2 = datetime(2026, 11, 2, 8, 0, 0)
    t3 = datetime(2026, 11, 3, 8, 0, 0)

    s1 = create_sample_session("S1", timestamp=t1)
    s2 = create_sample_session("S2", timestamp=t2)
    s3 = create_sample_session("S3", timestamp=t3)

    # Pass in shuffled order [S3, S1, S2]
    valid_sessions, stats = pipeline.filter_calibration_sessions([s3, s1, s2], "ASTRO-01")
    assert [s.session_id for s in valid_sessions] == ["S1", "S2", "S3"]

def test_07_telemetry_immutability():
    """Verify data pipeline does not mutate original input session dictionaries or objects."""
    pipeline = BaselineDataPipeline()
    t0 = datetime(2026, 11, 1, 8, 0, 0)
    orig_session = create_sample_session("S_ORIG", timestamp=t0, hr=75.4, resp=15.2)

    session_copy = copy.deepcopy(orig_session)
    valid_sessions, _ = pipeline.filter_calibration_sessions([orig_session], "ASTRO-01")

    # Verify input object remains bitwise identical
    assert orig_session.features["hr_mean_bpm"] == session_copy.features["hr_mean_bpm"]
    assert orig_session.features["resp_rate_bpm"] == session_copy.features["resp_rate_bpm"]
    assert orig_session.session_id == session_copy.session_id
