"""Personal deviation detection engine evaluating incoming telemetry against personal baselines."""
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from .schemas import (
    PersonalBaselineProfile,
    FeatureBaselineStats,
    FeatureDeviationResult,
    PersonalDeviationReport,
    BaselineContextType,
    BaselineReadinessState,
    DeviationDirection,
    DeviationSeverity
)
from .context_engine import ContextAwareBaselineEngine

class PersonalDeviationEngine:
    """Evaluates physiological observations against individualized reference envelopes."""

    def __init__(
        self,
        unusual_z_threshold: float = 3.0,
        context_engine: Optional[ContextAwareBaselineEngine] = None
    ):
        self.unusual_z_threshold = unusual_z_threshold
        self.context_engine = context_engine or ContextAwareBaselineEngine()
        # In-memory circular buffer for temporal EWMA tracking per astronaut
        self._history_buffers: Dict[str, List[float]] = {}

    def evaluate_feature_deviation(
        self,
        feature_name: str,
        observed_value: float,
        stats: FeatureBaselineStats,
        context_type: BaselineContextType
    ) -> FeatureDeviationResult:
        """Calculate standardized robust deviation and explainability for a single feature."""
        # Standard robust Z-score calculation: 0.6745 * (x - median) / MAD
        diff = observed_value - stats.median
        mad = stats.mad if stats.mad > 0.0 else max(stats.noise_floor, 0.01)
        robust_z = round(float(0.6745 * diff / mad), 3)

        # Direction
        if robust_z >= 1.0:
            direction = DeviationDirection.ELEVATED
        elif robust_z <= -1.0:
            direction = DeviationDirection.DEPRESSED
        else:
            direction = DeviationDirection.NOMINAL

        # Severity tier
        abs_z = abs(robust_z)
        if abs_z < 2.0:
            severity = DeviationSeverity.NOMINAL
        elif abs_z < 3.0:
            severity = DeviationSeverity.MILD
        elif abs_z < 4.5:
            severity = DeviationSeverity.MODERATE
        elif abs_z < 6.0:
            severity = DeviationSeverity.SIGNIFICANT
        else:
            severity = DeviationSeverity.EXTREME

        is_unusual = abs_z >= self.unusual_z_threshold

        # Estimated quantile ranking
        if observed_value <= stats.p10:
            q_rank = 0.05
        elif observed_value <= stats.p25:
            q_rank = 0.175
        elif observed_value <= stats.median:
            q_rank = 0.375
        elif observed_value <= stats.p75:
            q_rank = 0.625
        elif observed_value <= stats.p90:
            q_rank = 0.825
        else:
            q_rank = 0.95

        # Explainability narrative
        sign_str = "+" if robust_z >= 0 else ""
        explanation = (
            f"Observed {feature_name} ({observed_value:.2f} {stats.unit}) is {severity.value.lower()} "
            f"({sign_str}{robust_z:.2f} robust Z) relative to personal baseline "
            f"(median={stats.median:.2f}, MAD={stats.mad:.2f} {stats.unit}, N={stats.sample_count}) "
            f"under context '{context_type.value}'."
        )

        return FeatureDeviationResult(
            feature_name=feature_name,
            observed_value=round(observed_value, 4),
            unit=stats.unit,
            reference_median=stats.median,
            reference_mad=stats.mad,
            robust_z_score=robust_z,
            quantile_rank=q_rank,
            deviation_direction=direction,
            deviation_severity=severity,
            context_used=context_type,
            is_statistically_unusual=is_unusual,
            explanation=explanation
        )

    def evaluate_deviation(
        self,
        profile: Optional[PersonalBaselineProfile] = None,
        current_features: Optional[Dict[str, float]] = None,
        context: Optional[BaselineContextType] = None,
        sqa_scores: Optional[Dict[str, float]] = None,
        current_timestamp: Optional[datetime] = None,
        astronaut_id: Optional[str] = None,
        session_id: Optional[str] = None,
        baseline_profile: Optional[PersonalBaselineProfile] = None,
        explicit_context: Optional[BaselineContextType] = None
    ) -> PersonalDeviationReport:
        """Evaluate incoming features against baseline profile with flexible argument binding."""
        target_profile = profile or baseline_profile
        target_astro = astronaut_id or (target_profile.astronaut_id if target_profile else "AST-UNKNOWN")
        target_session = session_id or "SESSION-LIVE"
        target_feats = current_features or {}
        target_ctx = context or explicit_context
        return self.evaluate_session(
            astronaut_id=target_astro,
            session_id=target_session,
            current_features=target_feats,
            baseline_profile=target_profile,
            explicit_context=target_ctx
        )

    def evaluate_session(
        self,
        astronaut_id: str,
        session_id: str,
        current_features: Dict[str, float],
        baseline_profile: Optional[PersonalBaselineProfile],
        explicit_context: Optional[BaselineContextType] = None
    ) -> PersonalDeviationReport:
        """Evaluate complete current session against astronaut's personal baseline profile."""
        now = datetime.utcnow()

        # Handle absent or unestablished baselines
        if not baseline_profile:
            return PersonalDeviationReport(
                astronaut_id=astronaut_id,
                session_id=session_id,
                timestamp=now,
                baseline_version=0,
                readiness_state=BaselineReadinessState.INSUFFICIENT_DATA,
                context_detected=BaselineContextType.UNKNOWN,
                feature_deviations={},
                composite_deviation_score=0.0,
                abstention_reason="No personal baseline profile exists for this astronaut; deviation analysis deferred.",
                provenance="Personal Deviation Engine (Abstained: Missing Baseline)"
            )

        if baseline_profile.readiness_state in (
            BaselineReadinessState.INSUFFICIENT_DATA,
            BaselineReadinessState.INVALID,
            BaselineReadinessState.SUSPENDED
        ):
            return PersonalDeviationReport(
                astronaut_id=astronaut_id,
                session_id=session_id,
                timestamp=now,
                baseline_version=baseline_profile.baseline_version,
                readiness_state=baseline_profile.readiness_state,
                context_detected=BaselineContextType.UNKNOWN,
                feature_deviations={},
                composite_deviation_score=0.0,
                abstention_reason=f"Personal baseline in state '{baseline_profile.readiness_state.value}'; insufficient validated observations.",
                provenance="Personal Deviation Engine (Abstained: Unestablished Readiness)"
            )

        # Context detection
        detected_context = explicit_context or self.context_engine.infer_context_from_features(current_features)
        profile_to_use, fallback_applied, fallback_reason = self.context_engine.resolve_contextual_profile(
            profile=baseline_profile,
            requested_context=detected_context
        )

        deviations: Dict[str, FeatureDeviationResult] = {}
        z_scores: List[float] = []
        unusual_count = 0

        for feat_name, obs_val in current_features.items():
            if obs_val is None or math.isnan(obs_val) or math.isinf(obs_val):
                continue

            stats = profile_to_use.features.get(feat_name)
            if not stats:
                # If feature missing in contextual profile, try general profile
                stats = baseline_profile.general_profile.features.get(feat_name)

            if stats:
                dev = self.evaluate_feature_deviation(
                    feature_name=feat_name,
                    observed_value=obs_val,
                    stats=stats,
                    context_type=profile_to_use.context_type
                )
                deviations[feat_name] = dev
                z_scores.append(dev.robust_z_score)
                if dev.is_statistically_unusual:
                    unusual_count += 1

        # Composite anomaly score: RMS of robust Z-scores
        comp_score = 0.0
        if z_scores:
            comp_score = round(float(math.sqrt(sum(z ** 2 for z in z_scores) / len(z_scores))), 3)

        # Track temporal persistence
        is_persistent = self._update_persistence_tracking(astronaut_id, comp_score)

        return PersonalDeviationReport(
            astronaut_id=astronaut_id,
            session_id=session_id,
            timestamp=now,
            baseline_version=baseline_profile.baseline_version,
            readiness_state=baseline_profile.readiness_state,
            context_detected=detected_context,
            context_fallback_applied=fallback_applied,
            context_fallback_reason=fallback_reason,
            feature_deviations=deviations,
            composite_deviation_score=comp_score,
            persistent_deviation_detected=is_persistent,
            unusual_signals_count=unusual_count,
            abstention_reason=None,
            provenance=f"Personal Deviation Engine v1 (Baseline v{baseline_profile.baseline_version}, State: {baseline_profile.readiness_state.value})"
        )

    def _update_persistence_tracking(self, astronaut_id: str, current_composite_score: float) -> bool:
        """Track sequential composite scores to identify sustained anomalies versus transient noise."""
        if astronaut_id not in self._history_buffers:
            self._history_buffers[astronaut_id] = []

        buf = self._history_buffers[astronaut_id]
        buf.append(current_composite_score)
        if len(buf) > 10:
            buf.pop(0)

        # Persistent if last 3 consecutive sessions exceed threshold (composite >= 2.5)
        if len(buf) >= 3 and all(score >= 2.5 for score in buf[-3:]):
            return True
        return False
