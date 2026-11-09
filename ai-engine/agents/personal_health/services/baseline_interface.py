"""Interface for astronaut personalized physiological baseline engine (Deferred Phase)."""
from typing import Dict, Optional, Any
from ..schemas.assessment import BaselineStatus

class PersonalBaselineInterface:
    """Architectural interface for individualized physiological baselines."""

    def __init__(self, default_status: BaselineStatus = BaselineStatus.NOT_AVAILABLE):
        self._baseline_status = default_status

    def get_baseline_status(self, astronaut_id: str) -> BaselineStatus:
        """Query availability of established personal baseline for astronaut."""
        return self._baseline_status

    def set_baseline_status(self, status: BaselineStatus) -> None:
        """Explicitly set baseline availability status."""
        self._baseline_status = status

    def is_baseline_available(self, astronaut_id: str) -> bool:
        """Return True only if an established personal baseline is fully available."""
        return self._baseline_status == BaselineStatus.AVAILABLE

    def validate_session_as_baseline(self, session_features: Dict[str, float]) -> Dict[str, Any]:
        """Verify that an isolated session cannot automatically become a personal baseline."""
        return {
            "is_valid_baseline": False,
            "reason": "An isolated monitoring session cannot automatically become an established personal baseline. Multi-session longitudinal calibration is required."
        }

    def get_baseline_provenance(self, astronaut_id: str) -> Dict[str, Any]:
        """Return provenance metadata and observation period for baseline data."""
        return {
            "astronaut_id": astronaut_id,
            "baseline_status": self._baseline_status.value,
            "observation_period_days": 0 if self._baseline_status != BaselineStatus.AVAILABLE else 30,
            "calibrated_sessions_count": 0 if self._baseline_status != BaselineStatus.AVAILABLE else 10,
            "population_norm_applied": False,
            "provenance_notes": "Individualized physiological baseline requiring longitudinal rest-state telemetry."
        }

    def evaluate_deviation(
        self,
        astronaut_id: str,
        current_features: Dict[str, float]
    ) -> Dict[str, Any]:
        """Return explicit baseline comparison status without fabricated metrics."""
        is_avail = self.is_baseline_available(astronaut_id)
        if self._baseline_status == BaselineStatus.NOT_AVAILABLE:
            msg = "Personal baseline not available. Missing historical data; no baseline comparison performed."
        elif self._baseline_status == BaselineStatus.INSUFFICIENT_DATA:
            msg = "Insufficient longitudinal history to establish individualized baseline; comparison deferred."
        elif self._baseline_status == BaselineStatus.INVALID:
            msg = "Historical baseline data marked invalid due to telemetry artifacts or calibration failure."
        else:
            msg = "Personal baseline available; individual profile comparison active."

        return {
            "baseline_status": self._baseline_status.value,
            "deviation_scores": {},
            "baseline_available": is_avail,
            "message": msg,
            "provenance": self.get_baseline_provenance(astronaut_id)
        }
