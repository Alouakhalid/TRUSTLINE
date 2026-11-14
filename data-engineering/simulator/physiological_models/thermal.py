"""Thermal physiology and multi-compartment body temperature simulation models."""
import math
from typing import Tuple, Optional
import numpy as np


class ThermalModel:
    """Two-compartment (core and peripheral skin) thermal inertia model."""

    def __init__(
        self,
        base_core_temp_c: float = 37.0,
        base_skin_temp_c: float = 33.5,
        ambient_temp_c: float = 21.0,
        fs_core_hz: float = 1.0,
        fs_skin_hz: float = 4.0
    ):
        self.core_temp = base_core_temp_c
        self.skin_temp = base_skin_temp_c
        self.ambient_temp = ambient_temp_c
        self.fs_core = fs_core_hz
        self.fs_skin = fs_skin_hz

        # Metabolic heat rate multiplier (1.0 = resting basal metabolic rate)
        self.metabolic_multiplier = 1.0
        # Thermal inertia time constants (in seconds): core is sluggish, skin faster
        self.tau_core_sec = 600.0  # 10 minutes
        self.tau_skin_sec = 180.0  # 3 minutes

    def set_metabolic_state(self, activity_mets: float) -> None:
        """Set metabolic workload in METs (1.0 = resting, 4.0 = moderate EVA, 8.0 = heavy exercise)."""
        self.metabolic_multiplier = max(0.8, min(12.0, activity_mets))

    def generate_segment(
        self,
        duration_sec: float,
        seed: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generate core temperature and peripheral skin surface temperature traces.

        Returns:
            core_trace: np.ndarray shape (1, num_core_samples) at 1 Hz
            skin_trace: np.ndarray shape (1, num_skin_samples) at 4 Hz
        """
        rng = np.random.default_rng(seed)
        n_core = int(math.ceil(duration_sec * self.fs_core))
        n_skin = int(math.ceil(duration_sec * self.fs_skin))

        dt_core = 1.0 / self.fs_core
        dt_skin = 1.0 / self.fs_skin

        # Target equilibrium core temp based on metabolic rate (e.g. 37.0 at rest, 38.2 under sustained 8 METs)
        equilibrium_core = 36.8 + (0.16 * (self.metabolic_multiplier - 1.0))
        equilibrium_skin = 32.5 + (0.25 * (self.metabolic_multiplier - 1.0))

        core_vals = np.zeros(n_core)
        for i in range(n_core):
            # Slow exponential approach
            alpha = dt_core / self.tau_core_sec
            self.core_temp += alpha * (equilibrium_core - self.core_temp)
            noise_c = rng.normal(0.0, 0.003)
            core_vals[i] = self.core_temp + noise_c

        skin_vals = np.zeros(n_skin)
        for i in range(n_skin):
            alpha_s = dt_skin / self.tau_skin_sec
            self.skin_temp += alpha_s * (equilibrium_skin - self.skin_temp)
            noise_s = rng.normal(0.0, 0.008)
            skin_vals[i] = self.skin_temp + noise_s

        core_trace = np.clip(core_vals, 34.0, 42.0).reshape(1, -1)
        skin_trace = np.clip(skin_vals, 25.0, 42.0).reshape(1, -1)

        return core_trace, skin_trace
