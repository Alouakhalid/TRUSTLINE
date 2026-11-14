"""Respiratory mechanics and chest volume effort waveform generation models."""
import math
from typing import Tuple, Optional
import numpy as np


class RespiratoryModel:
    """Chest impedance / RIP breathing generator with asymmetric inspiratory/expiratory mechanics."""

    def __init__(
        self,
        base_respiration_rate_bpm: float = 14.0,
        ie_ratio: float = 0.60,  # Inspiratory to Expiratory duration ratio (e.g. 1:1.67)
        sampling_rate_hz: float = 32.0
    ):
        self.base_rr = base_respiration_rate_bpm
        self.ie_ratio = ie_ratio
        self.fs = sampling_rate_hz
        self._phase = 0.0

    def set_target_rate(self, respiration_rate_bpm: float) -> None:
        """Update instantaneous respiratory rate target."""
        self.base_rr = max(4.0, min(65.0, respiration_rate_bpm))

    def generate_segment(
        self,
        duration_sec: float,
        seed: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generate respiratory chest excursion waveform and phase indicator.

        Returns:
            resp_signal: np.ndarray shape (1, num_samples) in physical units (arbitrary chest expansion [-1, 1])
            phase_signal: np.ndarray shape (num_samples,) in range [-1, 1] for RSA cardiac coupling
        """
        rng = np.random.default_rng(seed)
        n_samples = int(math.ceil(duration_sec * self.fs))
        dt = 1.0 / self.fs

        freq_hz = self.base_rr / 60.0

        # Small breath-to-breath stochastic jitter in frequency
        phase_increment = 2.0 * math.pi * freq_hz * dt
        phases = (self._phase + np.cumsum(np.full(n_samples, phase_increment))) % (2.0 * math.pi)
        self._phase = float(phases[-1])

        # Asymmetric breath shape: inspiration phase is [0, phi_insp], expiration is [phi_insp, 2*pi]
        # phi_insp = 2*pi * (ie_ratio / (1 + ie_ratio))
        phi_insp = 2.0 * math.pi * (self.ie_ratio / (1.0 + self.ie_ratio))

        wave = np.zeros(n_samples)
        for i in range(n_samples):
            p = phases[i]
            if p <= phi_insp:
                # Inhalation: steep sigmoidal / sinusoidal upstroke
                wave[i] = -1.0 + 2.0 * (0.5 - 0.5 * math.cos(math.pi * p / phi_insp))
            else:
                # Exhalation: slower exponential or cosine decay
                decay_fraction = (p - phi_insp) / (2.0 * math.pi - phi_insp)
                wave[i] = 1.0 - 2.0 * (0.5 - 0.5 * math.cos(math.pi * decay_fraction))

        # Add slight cardiogenic oscillations and sensor noise
        noise = rng.normal(0.0, 0.015, size=n_samples)
        resp_waveform = np.clip(wave + noise, -1.0, 1.0).reshape(1, -1)

        return resp_waveform, wave
