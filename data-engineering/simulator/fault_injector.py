"""Hardware fault injection engine for sensor degradation and transmission disruption."""
import math
from typing import Dict, List, Optional
import numpy as np
from .schemas import FaultType, FaultInjectionConfig, SensorType, TelemetryPacket


class FaultInjector:
    """Injects deterministic and stochastic hardware/transmission faults into simulated signals and packets."""

    def __init__(self, configs: Optional[List[FaultInjectionConfig]] = None):
        self.configs: List[FaultInjectionConfig] = configs or []

    def add_fault(self, config: FaultInjectionConfig) -> None:
        """Register a new fault injection profile."""
        self.configs.append(config)

    def clear_faults(self) -> None:
        """Remove all active fault injection profiles."""
        self.configs.clear()

    def apply_signal_faults(
        self,
        sensor_type: SensorType,
        signal_array: np.ndarray,
        sample_rate_hz: float,
        current_time_sec: float
    ) -> np.ndarray:
        """Apply active signal-domain faults (flatline, noise, wander, clipping) to multichannel array.

        Args:
            sensor_type: SensorType being processed
            signal_array: np.ndarray of shape (channels, samples)
            sample_rate_hz: float sampling frequency
            current_time_sec: elapsed simulation time in seconds
        """
        output = signal_array.copy()
        channels, n_samples = output.shape
        t = np.linspace(current_time_sec, current_time_sec + (n_samples / sample_rate_hz), n_samples, endpoint=False)

        for cfg in self.configs:
            if cfg.target_sensor is not None and cfg.target_sensor != sensor_type:
                continue

            # Check temporal window of fault
            t_start = cfg.start_time_sec
            t_end = t_start + cfg.duration_sec
            if t[-1] < t_start or t[0] > t_end:
                continue

            mask = (t >= t_start) & (t <= t_end)
            if not np.any(mask):
                continue

            if cfg.fault_type == FaultType.FLATLINE:
                # Set signal to constant zero or DC offset in active window
                output[:, mask] = 0.0

            elif cfg.fault_type == FaultType.BASELINE_WANDER:
                # Add high-amplitude low-frequency drift
                freq = cfg.frequency_hz if cfg.frequency_hz is not None else 0.25
                drift = cfg.severity * np.sin(2.0 * math.pi * freq * t[mask])
                for ch in range(channels):
                    output[ch, mask] += drift

            elif cfg.fault_type == FaultType.POWERLINE_NOISE:
                # Add 50Hz/60Hz electromagnetic hum
                freq = cfg.frequency_hz if cfg.frequency_hz is not None else 50.0
                hum = (0.25 * cfg.severity) * np.sin(2.0 * math.pi * freq * t[mask])
                for ch in range(channels):
                    output[ch, mask] += hum

            elif cfg.fault_type == FaultType.CLIPPING:
                # Saturate signal around threshold
                limit = 1.0 - (0.6 * cfg.severity)
                output[:, mask] = np.clip(output[:, mask], -limit, limit)

        return output

    def should_drop_packet(
        self,
        sensor_type: SensorType,
        current_time_sec: float,
        rng: Optional[np.random.Generator] = None
    ) -> bool:
        """Determine if a packet should be dropped due to transmission packet loss fault."""
        if rng is None:
            rng = np.random.default_rng()

        for cfg in self.configs:
            if cfg.fault_type != FaultType.PACKET_LOSS:
                continue
            if cfg.target_sensor is not None and cfg.target_sensor != sensor_type:
                continue

            t_start = cfg.start_time_sec
            t_end = t_start + cfg.duration_sec
            if t_start <= current_time_sec <= t_end:
                loss_prob = cfg.loss_rate if cfg.loss_rate is not None else 0.15
                if rng.random() < loss_prob:
                    return True
        return False
