"""Robust statistical calculations for astronaut individualized physiological reference profiles."""
import math
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from .schemas import (
    FeatureBaselineStats,
    ContextualBaselineProfile,
    PersonalBaselineProfile,
    BaselineContextType,
    BaselineReadinessState,
    ObservationSession
)
from .data_pipeline import PHYSIOLOGICAL_SANITY_BOUNDS

# Minimum biological noise floors to guarantee stable scale denominators even during constant telemetry
PHYSIOLOGICAL_NOISE_FLOORS: Dict[str, float] = {
    "hr_mean_bpm": 1.0,        # 1.0 bpm minimum scale
    "hr_std_bpm": 0.5,
    "hrv_rmssd_ms": 1.5,       # 1.5 ms minimum scale
    "hrv_sdnn_ms": 1.5,
    "eda_mean": 0.05,          # 0.05 uS
    "eda_std": 0.01,
    "eda_iqr": 0.01,
    "resp_rate_bpm": 0.5,      # 0.5 breaths/min
    "resp_std": 0.2,
    "temp_mean": 0.05,         # 0.05 degC
    "temp_std": 0.02,
    "emg_rms": 0.005,
    "acc_magnitude_mean": 0.01,
    "acc_magnitude_std": 0.005
}

class RobustBaselineEngine:
    """Computes robust non-parametric reference statistics for physiological features."""

    @staticmethod
    def calculate_feature_stats(
        feature_name: str,
        values: List[float]
    ) -> Optional[FeatureBaselineStats]:
        """Compute robust reference statistics for a single feature series."""
        clean = [float(v) for v in values if v is not None and not (math.isnan(v) or math.isinf(v))]
        if not clean:
            return None

        arr = np.array(clean, dtype=np.float64)
        n = len(arr)

        median_val = float(np.median(arr))
        # Median Absolute Deviation (MAD)
        abs_deviations = np.abs(arr - median_val)
        raw_mad = float(np.median(abs_deviations))

        # Interquartile Range (IQR)
        p25 = float(np.percentile(arr, 25))
        p75 = float(np.percentile(arr, 75))
        iqr_val = float(p75 - p25)

        # Minimum noise floor
        noise_floor = PHYSIOLOGICAL_NOISE_FLOORS.get(feature_name, 0.01)

        # Scale estimate resolution when MAD = 0 (constant or heavily quantized observations)
        effective_mad = raw_mad
        if effective_mad <= 0.0:
            if iqr_val > 0.0:
                effective_mad = float(iqr_val / 1.349)
            else:
                std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
                effective_mad = float(max(std_val, noise_floor))

        effective_mad = max(effective_mad, noise_floor)

        _, _, unit_str = PHYSIOLOGICAL_SANITY_BOUNDS.get(feature_name, (0.0, 100.0, ""))

        return FeatureBaselineStats(
            feature_name=feature_name,
            unit=unit_str,
            median=round(median_val, 4),
            mad=round(effective_mad, 4),
            iqr=round(iqr_val, 4),
            mean=round(float(np.mean(arr)), 4),
            std=round(float(np.std(arr, ddof=1)) if n > 1 else 0.0, 4),
            min_val=round(float(np.min(arr)), 4),
            max_val=round(float(np.max(arr)), 4),
            p10=round(float(np.percentile(arr, 10)), 4),
            p25=round(p25, 4),
            p75=round(p75, 4),
            p90=round(float(np.percentile(arr, 90)), 4),
            sample_count=n,
            noise_floor=noise_floor
        )

    def build_contextual_profile(
        self,
        context_type: BaselineContextType,
        sessions: List[ObservationSession]
    ) -> ContextualBaselineProfile:
        """Aggregate sessions into a contextual baseline profile."""
        feature_buckets: Dict[str, List[float]] = {}
        for s in sessions:
            for k, v in s.features.items():
                if k not in feature_buckets:
                    feature_buckets[k] = []
                feature_buckets[k].append(v)

        stats_map: Dict[str, FeatureBaselineStats] = {}
        for feat_name, vals in feature_buckets.items():
            stats = self.calculate_feature_stats(feat_name, vals)
            if stats:
                stats_map[feat_name] = stats

        return ContextualBaselineProfile(
            context_type=context_type,
            sample_count=len(sessions),
            features=stats_map
        )

    def construct_personal_baseline(
        self,
        astronaut_id: str,
        valid_sessions: List[ObservationSession],
        readiness_metrics: Dict[str, Any],
        baseline_version: int = 1
    ) -> PersonalBaselineProfile:
        """Construct the complete multi-context personal baseline profile for an astronaut."""
        if not astronaut_id or astronaut_id in ("UNKNOWN", "AST-UNKNOWN"):
            raise ValueError(f"Cannot construct baseline for invalid astronaut identity: {astronaut_id}")

        # General profile covers all valid sessions
        general_profile = self.build_contextual_profile(
            context_type=BaselineContextType.NOMINAL_OPERATIONAL,
            sessions=valid_sessions
        )

        # Context-specific partitioning
        context_buckets: Dict[BaselineContextType, List[ObservationSession]] = {}
        for s in valid_sessions:
            ctx = s.context_type
            if ctx not in context_buckets:
                context_buckets[ctx] = []
            context_buckets[ctx].append(s)

        context_profiles: Dict[Any, ContextualBaselineProfile] = {}
        context_profiles[BaselineContextType.NOMINAL_OPERATIONAL] = general_profile
        context_profiles["NOMINAL_OPERATIONAL"] = general_profile

        for ctx, ctx_sessions in context_buckets.items():
            if len(ctx_sessions) >= 2:
                c_prof = self.build_contextual_profile(ctx, ctx_sessions)
                context_profiles[ctx] = c_prof
                context_profiles[ctx.value] = c_prof

        last_ts = valid_sessions[-1].timestamp if valid_sessions else None
        readiness_state = readiness_metrics.get("recommended_readiness_state", BaselineReadinessState.INSUFFICIENT_DATA)

        now = datetime.utcnow()
        return PersonalBaselineProfile(
            astronaut_id=astronaut_id,
            baseline_version=baseline_version,
            readiness_state=readiness_state,
            created_at=now,
            updated_at=now,
            last_observation_timestamp=last_ts,
            total_calibrated_sessions=len(valid_sessions),
            total_valid_observations=sum(len(s.features) for s in valid_sessions),
            observation_period_days=float(readiness_metrics.get("calendar_span_days", 0.0)),
            general_profile=general_profile,
            context_profiles=context_profiles,
            provenance_notes=f"Constructed from {len(valid_sessions)} valid longitudinal sessions over {readiness_metrics.get('calendar_span_days', 0.0):.1f} days."
        )

    def compute_baseline_profile(
        self,
        astronaut_id: str,
        sessions: List[ObservationSession],
        min_sessions: int = 5,
        min_observation_days: float = 3.0
    ) -> PersonalBaselineProfile:
        """Filter sessions and compute complete personal baseline profile."""
        from .data_pipeline import BaselineDataPipeline
        pipeline = BaselineDataPipeline()
        valid_sessions, readiness_metrics = pipeline.filter_calibration_sessions(
            sessions=sessions,
            target_astronaut_id=astronaut_id
        )
        return self.construct_personal_baseline(
            astronaut_id=astronaut_id,
            valid_sessions=valid_sessions,
            readiness_metrics=readiness_metrics
        )
