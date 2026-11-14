"""Spacecraft radiation physics and environmental dosimetry simulation model."""
import math
from typing import Optional, Tuple
from ..schemas import SpaceEnvironmentPacket
from .nasa_standards import NASA_RADIATION_LIMITS


class RadiationModel:
    """Simulates Galactic Cosmic Rays (GCR), Solar Particle Events (SPE), and shielding attenuation.

    ARCHITECTURAL RULE:
    Radiation telemetry is strictly environmental physical instrumentation.
    It is NEVER mixed with physiological machine learning feature vectors (WESAD).
    """

    def __init__(
        self,
        baseline_gcr_dose_rate_microgy_h: float = 22.0,
        shielding_thickness_g_cm2: float = 10.0,
        initial_cumulative_dose_msv: float = 0.0
    ):
        self.baseline_gcr_rate = baseline_gcr_dose_rate_microgy_h
        self.shielding_thickness = shielding_thickness_g_cm2
        self.cumulative_dose_msv = initial_cumulative_dose_msv

        # Active event state
        self.spe_active = False
        self.spe_peak_flux_pfu = 0.0
        self.spe_elapsed_sec = 0.0

        # Physical constants
        # Mass attenuation coefficient for aluminum (g/cm2)^-1 for high-energy protons/ions
        self.mu_shielding = 0.035

    def trigger_solar_particle_event(self, peak_flux_pfu: float = 1500.0) -> None:
        """Trigger an active Solar Particle Event (SPE) proton surge."""
        self.spe_active = True
        self.spe_peak_flux_pfu = max(10.0, peak_flux_pfu)
        self.spe_elapsed_sec = 0.0

    def terminate_solar_particle_event(self) -> None:
        """Terminate active Solar Particle Event."""
        self.spe_active = False
        self.spe_peak_flux_pfu = 0.0
        self.spe_elapsed_sec = 0.0

    def calculate_dose_rate(self, dt_sec: float = 1.0) -> Tuple[float, float, str]:
        """Compute absorbed dose rate (µGy/h) and equivalent dose rate (mSv/h) behind shielding.

        Returns:
            dose_rate_microgy_h: float absorbed dose rate in silicon/tissue
            eq_dose_rate_msv_h: float equivalent biological dose rate
            alert_level: str ("NOMINAL", "ADVISORY", "WARNING", "ALARM")
        """
        # 1. Unshielded ambient dose rate
        unshielded_rate = self.baseline_gcr_rate

        if self.spe_active:
            # SPE temporal profile: rapid rise and gradual power-law decay
            self.spe_elapsed_sec += dt_sec
            t_hours = self.spe_elapsed_sec / 3600.0
            # SPE surge formula
            surge_factor = math.exp(-0.25 * t_hours)
            spe_unshielded = (self.spe_peak_flux_pfu * 0.85) * surge_factor
            unshielded_rate += spe_unshielded

        # 2. Attenuation through spacecraft shielding: I = I_0 * exp(-mu * x)
        shielding_factor = math.exp(-self.mu_shielding * self.shielding_thickness)
        shielded_dose_rate_microgy_h = unshielded_rate * shielding_factor

        # 3. Quality Factor conversion to Equivalent Dose (mSv/h)
        # GCR ions have Q ~ 3.5, SPE solar protons have Q ~ 1.8
        if self.spe_active:
            q_factor = 2.0
        else:
            q_factor = 3.5

        # 1 Gy = 10^6 µGy; 1 Sv = 10^3 mSv; Eq_mSv = (Abs_µGy / 10^6) * Q * 10^3 = Abs_µGy * Q * 10^-3
        eq_dose_rate_msv_h = shielded_dose_rate_microgy_h * q_factor * 0.001

        # 4. Integrate cumulative dose
        dose_increment_msv = eq_dose_rate_msv_h * (dt_sec / 3600.0)
        self.cumulative_dose_msv += dose_increment_msv

        # 5. Determine NASA-STD-3001 alert level
        if shielded_dose_rate_microgy_h >= NASA_RADIATION_LIMITS.spe_acute_action_threshold_microgy_h:
            alert = "ALARM"
        elif shielded_dose_rate_microgy_h >= 100.0:
            alert = "WARNING"
        elif self.spe_active:
            alert = "ADVISORY"
        else:
            alert = "NOMINAL"

        return shielded_dose_rate_microgy_h, eq_dose_rate_msv_h, alert
