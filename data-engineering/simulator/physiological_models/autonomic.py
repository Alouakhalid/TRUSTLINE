"""Autonomic nervous system electrodermal activity (EDA) simulation model."""
import math
from typing import Tuple, List, Optional
import numpy as np


class ElectrodermalModel:
    """Bi-component EDA model synthesizing tonic skin conductance level (SCL) and phasic bursts (SCR)."""

    def __init__(
        self,
        baseline_scl_us: float = 3.0,
        sampling_rate_hz: float = 4.0,
        tau_rise_sec: float = 1.0,
        tau_decay_sec: float = 3.5
    ):
        self.tonic_level = baseline_scl_us
        self.fs = sampling_rate_hz
        self.tau_rise = tau_rise_sec
        self.tau_decay = tau_decay_sec
        self._active_responses: List[Tuple[float, float]] = []  # List of (elapsed_time_sec, amplitude)
        self._current_tonic = baseline_scl_us

    def set_target_tonic(self, scl_us: float) -> None:
        """Update steady-state tonic baseline level."""
        self.tonic_level = max(0.1, min(35.0, scl_us))

    def trigger_phasic_burst(self, amplitude_us: float = 1.2) -> None:
        """Inject a spontaneous or stimulus-driven sympathetic Skin Conductance Response."""
        amp = max(0.1, min(15.0, amplitude_us))
        self._active_responses.append((0.0, amp))

    def generate_segment(
        self,
        duration_sec: float,
        burst_probability_per_sec: float = 0.05,
        seed: Optional[int] = None
    ) -> np.ndarray:
        """Generate continuous electrodermal conductance trace in microSiemens (µS).

        Returns:
            eda_signal: np.ndarray shape (1, num_samples)
        """
        rng = np.random.default_rng(seed)
        n_samples = int(math.ceil(duration_sec * self.fs))
        dt = 1.0 / self.fs

        eda_trace = np.zeros(n_samples)

        for i in range(n_samples):
            # Slow adaptation of tonic level toward target
            adaptation_rate = 0.02 * dt
            self._current_tonic += (self.tonic_level - self._current_tonic) * adaptation_rate
            # Micro-fluctuations in tonic
            self._current_tonic += rng.normal(0.0, 0.001)

            # Random spontaneous SCR event generation based on arousal probability
            if rng.random() < (burst_probability_per_sec * dt):
                amp = rng.exponential(scale=0.8) + 0.2
                self.trigger_phasic_burst(amp)

            # Sum active phasic responses: g(t) = A * (exp(-t/tau_decay) - exp(-t/tau_rise))
            phasic_sum = 0.0
            updated_responses = []
            for t_resp, amp in self._active_responses:
                t_resp_next = t_resp + dt
                if t_resp_next < (self.tau_decay * 5.0):  # Stop when decayed to < 1%
                    val = amp * (math.exp(-t_resp / self.tau_decay) - math.exp(-t_resp / self.tau_rise))
                    if val > 0:
                        phasic_sum += val
                    updated_responses.append((t_resp_next, amp))
            self._active_responses = updated_responses

            total_eda = max(0.05, self._current_tonic + phasic_sum)
            eda_trace[i] = total_eda

        # Add instrumental measurement noise
        noise = rng.normal(0.0, 0.005, size=n_samples)
        return np.clip(eda_trace + noise, 0.05, 40.0).reshape(1, -1)
