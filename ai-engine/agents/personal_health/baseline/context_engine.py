"""Context detection, contextual profile routing, and graceful fallback for personal baselines."""
from typing import Dict, Optional, Tuple, Any

from .schemas import (
    BaselineContextType,
    PersonalBaselineProfile,
    ContextualBaselineProfile
)

class ContextAwareBaselineEngine:
    """Classifies operational/physiological context and resolves appropriate baseline profiles."""

    @staticmethod
    def infer_context_from_features(features: Dict[str, float]) -> BaselineContextType:
        """Infer physiological context from accelerometry and autonomic features."""
        acc_mag = features.get("acc_magnitude_mean")
        acc_std = features.get("acc_magnitude_std")
        hr = features.get("hr_mean_bpm")

        if acc_mag is None:
            return BaselineContextType.UNKNOWN

        # High physical locomotion / exercise
        if acc_mag > 1.15 or (acc_std is not None and acc_std > 0.10):
            return BaselineContextType.ACTIVITY

        # Low motion rest state
        if acc_mag <= 1.05 and (acc_std is not None and acc_std <= 0.04):
            if hr is not None and hr <= 78.0:
                return BaselineContextType.REST

        return BaselineContextType.NOMINAL_OPERATIONAL

    def resolve_contextual_profile(
        self,
        profile: PersonalBaselineProfile,
        requested_context: BaselineContextType
    ) -> Tuple[ContextualBaselineProfile, bool, Optional[str]]:
        """Select context-specific baseline profile with transparent fallback to general profile."""
        ctx_key = requested_context.value

        # Check if context-specific profile exists and has sufficient sample count
        if ctx_key in profile.context_profiles:
            c_prof = profile.context_profiles[ctx_key]
            if c_prof.sample_count >= 2:
                return c_prof, False, None

        # Fallback to general nominal baseline profile
        fallback_reason = (
            f"Context profile '{ctx_key}' has insufficient calibration data "
            f"(sample_count={profile.context_profiles.get(ctx_key, ContextualBaselineProfile(context_type=requested_context)).sample_count}); "
            f"falling back to general longitudinal reference profile."
        )
        return profile.general_profile, True, fallback_reason
