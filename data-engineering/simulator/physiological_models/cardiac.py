"""Cardiac electrical and hemodynamic waveform generation models."""
import math
from typing import Dict, List, Tuple, Optional
import numpy as np


class CardiacModel:
    """Coupled ECG and PPG waveform generator with autonomic HRV and respiratory sinus arrhythmia (RSA)."""

    def __init__(
        self,
        base_heart_rate_bpm: float = 70.0,
        hrv_rmssd_ms: float = 50.0,
        sampling_rate_ecg_hz: float = 256.0,
        sampling_rate_ppg_hz: float = 64.0
    ):
        self.base_hr = base_heart_rate_bpm
        self.target_rmssd = hrv_rmssd_ms
        self.fs_ecg = sampling_rate_ecg_hz
        self.fs_ppg = sampling_rate_ppg_hz
        self._phase = 0.0
        self._current_rr_sec = 60.0 / self.base_hr

        # Standard Gaussian parameters for ECG morphology: (amplitude, width, center_rad)
        self.ecg_wavelet_params = [
            (0.15, 0.05, -math.pi / 3.0),   # P wave
            (-0.15, 0.02, -math.pi / 12.0), # Q wave
            (1.20, 0.03, 0.0),              # R peak
            (-0.25, 0.02, math.pi / 12.0),  # S wave
            (0.30, 0.10, math.pi / 2.0)     # T wave
        ]

    def set_target_state(self, hr_bpm: float, hrv_rmssd_ms: float) -> None:
        """Update instantaneous cardiovascular target parameters."""
        self.base_hr = max(30.0, min(220.0, hr_bpm))
        self.target_rmssd = max(5.0, min(150.0, hrv_rmssd_ms))

    def generate_segment(
        self,
        duration_sec: float,
        respiratory_phase_signal: Optional[np.ndarray] = None,
        seed: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate coupled Lead-II ECG, derived PPG pulse, and instantaneous heart rate.

        Returns:
            ecg_leads: np.ndarray shape (num_channels, num_samples_ecg)
            ppg_signal: np.ndarray shape (1, num_samples_ppg)
            hr_series: np.ndarray shape (num_samples_ecg,)
        """
        rng = np.random.default_rng(seed)
        n_ecg = int(math.ceil(duration_sec * self.fs_ecg))
        n_ppg = int(math.ceil(duration_sec * self.fs_ppg))

        t_ecg = np.linspace(0, duration_sec, n_ecg, endpoint=False)
        t_ppg = np.linspace(0, duration_sec, n_ppg, endpoint=False)

        # Autonomic modulation (RSA + Mayer waves 0.1Hz + stochastic HRV)
        rsa_coupling = 0.0
        if respiratory_phase_signal is not None and len(respiratory_phase_signal) > 0:
            if len(respiratory_phase_signal) != n_ecg:
                rsa_interp = np.interp(
                    np.linspace(0, 1, n_ecg),
                    np.linspace(0, 1, len(respiratory_phase_signal)),
                    respiratory_phase_signal
                )
            else:
                rsa_interp = respiratory_phase_signal
        else:
            # Synthetic 0.25Hz respiratory rhythm
            rsa_interp = np.sin(2.0 * math.pi * 0.25 * t_ecg)

        # Mayer wave (sympathetic blood pressure regulation ~0.1 Hz)
        mayer_wave = 0.03 * np.sin(2.0 * math.pi * 0.10 * t_ecg)

        # Scale RSA modulation proportional to target RMSSD
        rsa_weight = min(0.12, (self.target_rmssd / 1000.0) * 1.5)
        hr_mod = 1.0 + (rsa_weight * rsa_interp) + mayer_wave

        # Instantaneous Heart Rate (bpm)
        inst_hr = self.base_hr * hr_mod
        inst_freq = inst_hr / 60.0  # Hz

        # Cumulative phase integration: dtheta/dt = 2*pi*f(t)
        dt_ecg = 1.0 / self.fs_ecg
        phase_steps = 2.0 * math.pi * inst_freq * dt_ecg
        phase_ecg = (self._phase + np.cumsum(phase_steps)) % (2.0 * math.pi)
        self._phase = float(phase_ecg[-1])

        # Centered phase [-pi, pi] for wavelet synthesis
        wrapped_phase = np.angle(np.exp(1j * phase_ecg))

        # Synthesize Lead II ECG using sum of Gaussians
        lead_ii = np.zeros(n_ecg)
        for a, b, theta in self.ecg_wavelet_params:
            diff = np.angle(np.exp(1j * (wrapped_phase - theta)))
            lead_ii += a * np.exp(-0.5 * (diff / b) ** 2)

        # Lead I (approx 0.6 * Lead II + atrial emphasis)
        lead_i = 0.65 * lead_ii + 0.05 * np.exp(-0.5 * ((wrapped_phase + math.pi / 3.0) / 0.06) ** 2)
        # Lead III = Lead II - Lead I (Einthoven's law)
        lead_iii = lead_ii - lead_i

        # Add physical noise floor
        noise_ecg = rng.normal(0.0, 0.008, size=(3, n_ecg))
        ecg_leads = np.vstack([lead_i, lead_ii, lead_iii]) + noise_ecg

        # Synthesize PPG at optical sampling rate
        # Pulse transit time delay (PTT ~ 200 ms)
        ptt_delay_sec = 0.20
        phase_ppg = np.interp(
            t_ppg,
            np.clip(t_ecg - ptt_delay_sec, 0.0, duration_sec),
            wrapped_phase
        )

        # Realistic photoplethysmogram: asymmetric systolic upstroke + dicrotic notch
        # Systolic wave
        systolic = np.maximum(0.0, np.sin(0.5 * (phase_ppg + math.pi))) ** 2.5
        # Dicrotic wave
        dicrotic = 0.35 * np.maximum(0.0, np.sin(0.5 * (phase_ppg + math.pi * 0.4))) ** 4.0
        ppg_raw = systolic + dicrotic
        # Normalize to [0.05, 0.95]
        min_p, max_p = np.min(ppg_raw), np.max(ppg_raw)
        if max_p > min_p:
            ppg_norm = 0.05 + 0.90 * (ppg_raw - min_p) / (max_p - min_p)
        else:
            ppg_norm = np.full_like(ppg_raw, 0.5)

        noise_ppg = rng.normal(0.0, 0.004, size=(1, n_ppg))
        ppg_signal = np.clip(ppg_norm.reshape(1, -1) + noise_ppg, 0.0, 1.0)

        return ecg_leads, ppg_signal, inst_hr
