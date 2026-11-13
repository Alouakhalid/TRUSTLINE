"""Data eligibility, quality gating, and readiness assessment pipeline for personal baselines."""
import math
import copy
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from .schemas import (
    ObservationSession,
    BaselineContextType,
    BaselineReadinessState
)

# Physiological sanity boundaries based on NASA flight surgeon standards
PHYSIOLOGICAL_SANITY_BOUNDS: Dict[str, Tuple[float, float, str]] = {
    "hr_mean_bpm": (30.0, 220.0, "bpm"),
    "hr_std_bpm": (0.0, 60.0, "bpm"),
    "hrv_rmssd_ms": (1.0, 350.0, "ms"),
    "hrv_sdnn_ms": (1.0, 350.0, "ms"),
    "eda_mean": (0.01, 50.0, "uS"),
    "eda_std": (0.0, 20.0, "uS"),
    "eda_iqr": (0.0, 20.0, "uS"),
    "resp_rate_bpm": (4.0, 50.0, "br/min"),
    "resp_std": (0.0, 15.0, "br/min"),
    "temp_mean": (25.0, 42.0, "degC"),
    "temp_std": (0.0, 5.0, "degC"),
    "emg_rms": (0.0, 5.0, "mV"),
    "acc_magnitude_mean": (0.0, 10.0, "g"),
    "acc_magnitude_std": (0.0, 5.0, "g"),
    "acc_mag_std": (0.0, 5.0, "g")
}

FEATURE_TO_SENSOR_MAP: Dict[str, str] = {
    "hr_mean_bpm": "ECG",
    "hr_std_bpm": "ECG",
    "hrv_rmssd_ms": "ECG",
    "hrv_sdnn_ms": "ECG",
    "eda_mean": "EDA",
    "eda_std": "EDA",
    "eda_iqr": "EDA",
    "resp_rate_bpm": "RESP",
    "resp_std": "RESP",
    "temp_mean": "TEMP",
    "temp_std": "TEMP",
    "emg_rms": "EMG",
    "acc_magnitude_mean": "ACC",
    "acc_magnitude_std": "ACC",
    "acc_mag_std": "ACC"
}

class BaselineDataPipeline:
    """Prepares, audits, and validates physiological sessions for personal baseline construction."""

    def __init__(
        self,
        min_session_duration_seconds: float = 0.0,
        min_quality_score: float = 0.60,
        min_sqa_score: Optional[float] = None
    ):
        self.min_session_duration_seconds = min_session_duration_seconds
        self.min_quality_score = min_sqa_score if min_sqa_score is not None else min_quality_score

    def audit_and_filter_session(
        self,
        session: ObservationSession,
        target_astronaut_id: str
    ) -> Tuple[bool, Optional[str], Dict[str, float], int]:
        """Validate a single observation session against identity, quality, and sanity invariants."""
        # 1. Identity isolation
        sess_astro = (session.astronaut_id or "").strip().upper()
        target_astro = (target_astronaut_id or "").strip().upper()

        if not sess_astro or sess_astro in ("UNKNOWN", "AST-UNKNOWN"):
            return False, "Unknown or unverified astronaut identity.", {}, 0
        if not target_astro or target_astro in ("UNKNOWN", "AST-UNKNOWN"):
            return False, "Target astronaut identity is unverified.", {}, 0
        if sess_astro != target_astro:
            return False, f"Cross-astronaut violation: session belongs to {sess_astro}, not {target_astro}.", {}, 0

        # 2. SQA overall score gating
        if session.sqa_overall_score is not None and session.sqa_overall_score < self.min_quality_score:
            return False, f"Low SQA overall quality score ({session.sqa_overall_score:.2f} < {self.min_quality_score:.2f})", {}, 0

        # 3. Duration check
        if self.min_session_duration_seconds > 0.0 and session.duration_seconds < self.min_session_duration_seconds:
            return False, f"Session duration ({session.duration_seconds:.1f}s) is below threshold.", {}, 0

        # 4. Feature and quality validation per physiological metric
        valid_features: Dict[str, float] = {}
        rejected_artifacts_count = 0

        for feat_name, val in session.features.items():
            if val is None or math.isnan(val) or math.isinf(val):
                rejected_artifacts_count += 1
                continue

            # Check sensor quality if SQA scores provided
            sensor_name = FEATURE_TO_SENSOR_MAP.get(feat_name)
            if sensor_name and session.sensor_quality_scores:
                q_score = session.sensor_quality_scores.get(sensor_name, 1.0)
                if q_score < self.min_quality_score:
                    rejected_artifacts_count += 1
                    continue

            # Check zero-variability HRV artifact
            if feat_name in ("hrv_rmssd_ms", "hrv_sdnn_ms") and val < 1.0:
                rejected_artifacts_count += 1
                continue

            # Physiological boundary check
            bounds = PHYSIOLOGICAL_SANITY_BOUNDS.get(feat_name)
            if bounds:
                min_b, max_b, _ = bounds
                if not (min_b <= val <= max_b):
                    rejected_artifacts_count += 1
                    continue

            valid_features[feat_name] = float(val)

        if not valid_features:
            return False, "No valid physiological features passed quality and sanity filters.", {}, rejected_artifacts_count

        return True, None, valid_features, rejected_artifacts_count

    def prepare_dataset(
        self,
        raw_sessions: List[ObservationSession],
        astronaut_id: str
    ) -> Tuple[List[ObservationSession], Dict[str, Any]]:
        """Filter raw sessions and compute comprehensive data readiness metrics."""
        valid_sessions: List[ObservationSession] = []
        rejection_counts: Dict[str, int] = {
            "rejected_low_sqa": 0,
            "rejected_astronaut_mismatch": 0,
            "rejected_duplicates": 0,
            "rejected_artifacts": 0,
        }
        seen_sessions = set()
        seen_timestamps = set()

        for s in raw_sessions:
            sess_astro = (s.astronaut_id or "").strip().upper()
            target_astro = (astronaut_id or "").strip().upper()
            if sess_astro != target_astro:
                rejection_counts["rejected_astronaut_mismatch"] += 1
                continue

            # Check duplicate session_id or timestamp
            if s.session_id in seen_sessions or s.timestamp in seen_timestamps:
                rejection_counts["rejected_duplicates"] += 1
                continue

            is_valid, reason, cleaned_feats, art_count = self.audit_and_filter_session(s, astronaut_id)
            rejection_counts["rejected_artifacts"] += art_count

            if not is_valid:
                if reason and "Low SQA" in reason:
                    rejection_counts["rejected_low_sqa"] += 1
                else:
                    rejection_counts["rejected_artifacts"] += 1
            else:
                seen_sessions.add(s.session_id)
                seen_timestamps.add(s.timestamp)
                cleaned_session = s.model_copy(deep=True, update={"features": cleaned_feats, "is_valid": True})
                valid_sessions.append(cleaned_session)

        # Sort temporally to enforce time-awareness
        valid_sessions.sort(key=lambda x: x.timestamp)

        readiness_metrics = self.calculate_readiness_metrics(
            valid_sessions=valid_sessions,
            total_submitted=len(raw_sessions),
            rejection_counts=rejection_counts
        )
        readiness_metrics.update(rejection_counts)

        return valid_sessions, readiness_metrics

    def filter_calibration_sessions(
        self,
        sessions: List[ObservationSession],
        target_astronaut_id: str
    ) -> Tuple[List[ObservationSession], Dict[str, Any]]:
        """Convenience alias for prepare_dataset for baseline calibration."""
        return self.prepare_dataset(raw_sessions=sessions, astronaut_id=target_astronaut_id)

    def calculate_readiness_metrics(
        self,
        valid_sessions: List[ObservationSession],
        total_submitted: int,
        rejection_counts: Dict[str, int]
    ) -> Dict[str, Any]:
        """Compute statistical data readiness, missingness, and observation coverage."""
        valid_count = len(valid_sessions)
        rejected_count = total_submitted - valid_count

        total_duration_sec = sum(s.duration_seconds for s in valid_sessions)

        # Temporal span in days
        calendar_span_days = 0.0
        if valid_count >= 2:
            span_delta = valid_sessions[-1].timestamp - valid_sessions[0].timestamp
            calendar_span_days = max(0.01, round(span_delta.total_seconds() / 86400.0, 2))

        # Distinct calendar days
        distinct_days = len(set(s.timestamp.date() for s in valid_sessions))

        # Missingness per feature
        feature_counts: Dict[str, int] = {}
        for s in valid_sessions:
            for feat in s.features.keys():
                feature_counts[feat] = feature_counts.get(feat, 0) + 1

        missingness: Dict[str, float] = {}
        for feat in PHYSIOLOGICAL_SANITY_BOUNDS.keys():
            present = feature_counts.get(feat, 0)
            missingness[feat] = round(1.0 - (present / float(max(1, valid_count))), 3)

        if valid_count < 3:
            state = BaselineReadinessState.INSUFFICIENT_DATA
        elif valid_count < 5 or distinct_days < 2:
            state = BaselineReadinessState.PROVISIONAL
        else:
            state = BaselineReadinessState.ESTABLISHED

        return {
            "total_submitted_sessions": total_submitted,
            "valid_sessions_count": valid_count,
            "rejected_sessions_count": rejected_count,
            "rejection_reasons": rejection_counts,
            "total_observation_duration_seconds": total_duration_sec,
            "total_observation_hours": round(total_duration_sec / 3600.0, 2),
            "calendar_span_days": calendar_span_days,
            "distinct_observation_days": distinct_days,
            "feature_missingness": missingness,
            "recommended_readiness_state": state
        }
