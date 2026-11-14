"""NASA-STD-3001 space radiation exposure standards and operational guidelines."""
from typing import Dict, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class RadiationLimits:
    """NASA-STD-3001 Volume 1 Revision C Table 2: Radiation Dose Limits for Astronauts."""
    # Short-term (30-day) limits in mSv
    blood_forming_organs_30d_msv: float = 250.0
    eye_lens_30d_msv: float = 1000.0
    skin_30d_msv: float = 1500.0

    # 1-year limits in mSv
    blood_forming_organs_1yr_msv: float = 500.0
    eye_lens_1yr_msv: float = 2000.0
    skin_1yr_msv: float = 3000.0

    # Acute SPE storm shelter alert threshold in µGy/h
    spe_acute_action_threshold_microgy_h: float = 500.0


NASA_RADIATION_LIMITS = RadiationLimits()
