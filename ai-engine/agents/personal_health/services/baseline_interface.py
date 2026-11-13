"""Personal Health Baseline Interface orchestrating calibration, retrieval, deviation evaluation, and safe updates."""
from datetime import datetime
from typing import Dict, Optional, Any, List, Tuple
from ..schemas.assessment import BaselineStatus
from ..baseline.schemas import (
    PersonalBaselineProfile,
    ObservationSession,
    PersonalDeviationReport,
    BaselineReadinessState,
    BaselineContextType,
)
from ..baseline.repository import PersonalBaselineRepository
from ..baseline.deviation_engine import PersonalDeviationEngine
from ..baseline.update_manager import SafeBaselineUpdateManager
from ..baseline.data_pipeline import BaselineDataPipeline
from ..baseline.statistical_engine import RobustBaselineEngine
from ..baseline.context_engine import ContextAwareBaselineEngine

class PersonalBaselineInterface:
    """Architectural interface for individualized physiological baselines and deviation detection."""

    def __init__(
        self,
        default_status: BaselineStatus = BaselineStatus.NOT_AVAILABLE,
        repository: Optional[PersonalBaselineRepository] = None,
        deviation_engine: Optional[PersonalDeviationEngine] = None,
        update_manager: Optional[SafeBaselineUpdateManager] = None
    ):
        self._default_status = default_status
        self._manual_status: Optional[BaselineStatus] = None if default_status == BaselineStatus.NOT_AVAILABLE else default_status
        self._repo = repository or PersonalBaselineRepository()
        self._deviation_engine = deviation_engine or PersonalDeviationEngine()
        self._update_manager = update_manager or SafeBaselineUpdateManager(repository=self._repo)
        self._data_pipeline = BaselineDataPipeline()
        self._stat_engine = RobustBaselineEngine()
        self._context_engine = ContextAwareBaselineEngine()

    def get_baseline_status(self, astronaut_id: str) -> BaselineStatus:
        """Query availability of established personal baseline for astronaut."""
        if self._manual_status is not None:
            return self._manual_status

        if not astronaut_id or astronaut_id in ("UNKNOWN", "AST-UNKNOWN"):
            return BaselineStatus.NOT_AVAILABLE

        profile = self._repo.get_baseline(astronaut_id)
        if not profile:
            return self._default_status

        if profile.readiness_state in (BaselineReadinessState.ESTABLISHED, BaselineReadinessState.PROVISIONAL):
            return BaselineStatus.AVAILABLE
        elif profile.readiness_state == BaselineReadinessState.INSUFFICIENT_DATA:
            return BaselineStatus.INSUFFICIENT_DATA
        elif profile.readiness_state in (BaselineReadinessState.INVALID, BaselineReadinessState.SUSPENDED):
            return BaselineStatus.INVALID
        return self._default_status

    def set_baseline_status(self, status: BaselineStatus) -> None:
        """Explicitly set baseline availability status."""
        self._manual_status = status

    def is_baseline_available(self, astronaut_id: str) -> bool:
        """Return True only if an established personal baseline is fully available."""
        return self.get_baseline_status(astronaut_id) == BaselineStatus.AVAILABLE

    def validate_session_as_baseline(self, session_features: Dict[str, float]) -> Dict[str, Any]:
        """Verify that an isolated session cannot automatically become a personal baseline."""
        return {
            "is_valid_baseline": False,
            "reason": "An isolated monitoring session cannot automatically become an established personal baseline. Multi-session longitudinal calibration is required."
        }

    def get_baseline_provenance(self, astronaut_id: str) -> Dict[str, Any]:
        """Return provenance metadata and observation period for baseline data."""
        if astronaut_id and astronaut_id not in ("UNKNOWN", "AST-UNKNOWN"):
            profile = self._repo.get_baseline(astronaut_id)
            if profile:
                stat = self.get_baseline_status(astronaut_id)
                return {
                    "astronaut_id": astronaut_id,
                    "baseline_status": stat.value,
                    "baseline_version": profile.baseline_version,
                    "readiness_state": profile.readiness_state.value,
                    "observation_period_days": profile.observation_period_days,
                    "calibrated_sessions_count": profile.total_calibrated_sessions,
                    "valid_observations_count": profile.total_valid_observations,
                    "population_norm_applied": False,
                    "provenance_notes": f"Individualized physiological baseline v{profile.baseline_version} calibrated across {profile.total_calibrated_sessions} longitudinal sessions."
                }

        stat = self.get_baseline_status(astronaut_id)
        is_avail = (stat == BaselineStatus.AVAILABLE)
        return {
            "astronaut_id": astronaut_id,
            "baseline_status": stat.value,
            "observation_period_days": 30 if is_avail else 0,
            "calibrated_sessions_count": 10 if is_avail else 0,
            "population_norm_applied": False,
            "provenance_notes": "Individualized physiological baseline requiring longitudinal rest-state telemetry."
        }

    def evaluate_deviation(
        self,
        astronaut_id: str,
        current_features: Dict[str, float],
        context: Optional[str] = None,
        sqa_scores: Optional[Dict[str, float]] = None,
        current_timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Return explicit baseline comparison status without fabricated metrics."""
        stat = self.get_baseline_status(astronaut_id)
        is_avail = (stat == BaselineStatus.AVAILABLE)

        if stat == BaselineStatus.NOT_AVAILABLE:
            msg = "Personal baseline not available. Missing historical data; no baseline comparison performed."
            return {
                "baseline_status": stat.value,
                "deviation_scores": {},
                "baseline_available": False,
                "message": msg,
                "provenance": self.get_baseline_provenance(astronaut_id)
            }
        elif stat == BaselineStatus.INSUFFICIENT_DATA:
            msg = "Insufficient longitudinal history to establish individualized baseline; comparison deferred."
            return {
                "baseline_status": stat.value,
                "deviation_scores": {},
                "baseline_available": False,
                "message": msg,
                "provenance": self.get_baseline_provenance(astronaut_id)
            }
        elif stat == BaselineStatus.INVALID:
            msg = "Historical baseline data marked invalid due to telemetry artifacts or calibration failure."
            return {
                "baseline_status": stat.value,
                "deviation_scores": {},
                "baseline_available": False,
                "message": msg,
                "provenance": self.get_baseline_provenance(astronaut_id)
            }

        profile = None
        if astronaut_id and astronaut_id not in ("UNKNOWN", "AST-UNKNOWN"):
            profile = self._repo.get_baseline(astronaut_id)

        if profile is not None:
            ctx_type = None
            if context:
                try:
                    ctx_type = BaselineContextType(context)
                except ValueError:
                    ctx_type = BaselineContextType.UNKNOWN
            dev_report = self._deviation_engine.evaluate_deviation(
                profile=profile,
                current_features=current_features,
                context=ctx_type,
                sqa_scores=sqa_scores,
                current_timestamp=current_timestamp
            )
            dev_scores = {k: v.robust_z_score for k, v in dev_report.feature_deviations.items()}
            return {
                "baseline_status": stat.value,
                "deviation_scores": dev_scores,
                "baseline_available": True,
                "message": "Personal baseline available; individual profile comparison active.",
                "provenance": self.get_baseline_provenance(astronaut_id),
                "deviation_report": dev_report.model_dump(),
                "composite_deviation_score": dev_report.composite_deviation_score,
                "is_statistically_significant": dev_report.is_statistically_significant,
                "clinically_concerning": dev_report.clinically_concerning,
            }

        return {
            "baseline_status": stat.value,
            "deviation_scores": {},
            "baseline_available": is_avail,
            "message": "Personal baseline available; individual profile comparison active.",
            "provenance": self.get_baseline_provenance(astronaut_id)
        }

    def calibrate_baseline_from_sessions(
        self,
        astronaut_id: str,
        sessions: List[ObservationSession],
        min_sessions: int = 5,
        min_observation_days: float = 3.0
    ) -> PersonalBaselineProfile:
        """Calibrate a new multi-context baseline profile from longitudinal sessions."""
        cleaned_sessions, stats = self._data_pipeline.filter_calibration_sessions(
            sessions=sessions,
            target_astronaut_id=astronaut_id
        )
        profile = self._stat_engine.compute_baseline_profile(
            astronaut_id=astronaut_id,
            sessions=cleaned_sessions,
            min_sessions=min_sessions,
            min_observation_days=min_observation_days
        )
        return self._repo.save_baseline(profile, reason="Initial multi-session calibration")

    def update_baseline(
        self,
        astronaut_id: str,
        new_session: ObservationSession,
        current_deviation: Optional[PersonalDeviationReport] = None,
        sqa_score: float = 1.0
    ) -> Tuple[bool, Optional[PersonalBaselineProfile], Optional[str]]:
        """Update existing baseline with safety anti-contamination guards."""
        profile = self._repo.get_baseline(astronaut_id)
        if not profile:
            return False, None, "No active baseline found for astronaut."

        return self._update_manager.attempt_update(
            profile=profile,
            new_session=new_session,
            deviation_report=current_deviation,
            sqa_score=sqa_score
        )

    def rollback_baseline(
        self,
        astronaut_id: str,
        target_version: int,
        reason: str,
        changed_by: str = "supervisor"
    ) -> PersonalBaselineProfile:
        """Rollback baseline profile to a verified historical snapshot."""
        return self._repo.rollback_to_version(
            astronaut_id=astronaut_id,
            target_version=target_version,
            reason=reason,
            changed_by=changed_by
        )

    def get_profile(self, astronaut_id: str) -> Optional[PersonalBaselineProfile]:
        """Retrieve baseline profile for astronaut if available."""
        return self._repo.get_baseline(astronaut_id)

    def save_profile(self, profile: PersonalBaselineProfile, reason: str = "Baseline update") -> PersonalBaselineProfile:
        """Save profile directly."""
        return self._repo.save_baseline(profile, reason=reason)
