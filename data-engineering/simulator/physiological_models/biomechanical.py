"""Biomechanical kinematics: 3-axis accelerometer and gyroscope motion simulation."""
import math
from enum import Enum
from typing import Tuple, Optional
import numpy as np


class MotionState(str, Enum):
    """Operational astronaut motion activity states."""
    MICROGRAVITY_REST = "MICROGRAVITY_REST"
    EARTH_REST = "EARTH_REST"
    LOCOMOTION_EXERCISE = "LOCOMOTION_EXERCISE"
    EVA_MANEUVERING = "EVA_MANEUVERING"


class BiomechanicalModel:
    """Simulates triaxial accelerometer and gyroscope data across mission activity states."""

    def __init__(self, sampling_rate_hz: float = 32.0):
        self.fs = sampling_rate_hz
        self.state = MotionState.MICROGRAVITY_REST
        self._cadence_phase = 0.0

    def set_motion_state(self, state: MotionState) -> None:
        """Switch kinematic activity state."""
        self.state = state

    def generate_segment(
        self,
        duration_sec: float,
        seed: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generate 3-axis accelerometer (g) and 3-axis gyroscope (deg/s) arrays.

        Returns:
            acc_data: np.ndarray shape (3, num_samples) [X, Y, Z]
            gyro_data: np.ndarray shape (3, num_samples) [X, Y, Z]
        """
        rng = np.random.default_rng(seed)
        n = int(math.ceil(duration_sec * self.fs))
        t = np.linspace(0, duration_sec, n, endpoint=False)
        dt = 1.0 / self.fs

        if self.state == MotionState.MICROGRAVITY_REST:
            # Baseline floating in zero-g with subtle ISS structural hum
            acc_x = rng.normal(0.005, 0.008, size=n)
            acc_y = rng.normal(-0.004, 0.008, size=n)
            acc_z = rng.normal(0.002, 0.008, size=n)
            gyro_x = rng.normal(0.0, 0.20, size=n)
            gyro_y = rng.normal(0.0, 0.20, size=n)
            gyro_z = rng.normal(0.0, 0.20, size=n)

        elif self.state == MotionState.EARTH_REST:
            # Static 1g Earth gravity vector aligned mostly along Z axis
            acc_x = rng.normal(0.02, 0.01, size=n)
            acc_y = rng.normal(-0.05, 0.01, size=n)
            acc_z = rng.normal(0.98, 0.01, size=n)
            gyro_x = rng.normal(0.0, 0.15, size=n)
            gyro_y = rng.normal(0.0, 0.15, size=n)
            gyro_z = rng.normal(0.0, 0.15, size=n)

        elif self.state == MotionState.LOCOMOTION_EXERCISE:
            # High-intensity periodic motion (cadence ~ 2.0 Hz)
            cadence_hz = 2.0
            phase_steps = 2.0 * math.pi * cadence_hz * dt
            phases = (self._cadence_phase + np.cumsum(np.full(n, phase_steps))) % (2.0 * math.pi)
            self._cadence_phase = float(phases[-1])

            # Vertical and lateral harmonics
            acc_x = 0.6 * np.sin(phases) + rng.normal(0.0, 0.08, size=n)
            acc_y = 0.8 * np.sin(phases * 0.5) + rng.normal(0.0, 0.08, size=n)
            acc_z = 1.5 * np.cos(phases) + rng.normal(0.0, 0.12, size=n)

            gyro_x = 35.0 * np.sin(phases) + rng.normal(0.0, 1.5, size=n)
            gyro_y = 20.0 * np.cos(phases) + rng.normal(0.0, 1.5, size=n)
            gyro_z = 15.0 * np.sin(phases * 2.0) + rng.normal(0.0, 1.5, size=n)

        elif self.state == MotionState.EVA_MANEUVERING:
            # Irregular suit thruster bursts and translational rotations
            phases = np.linspace(0, 4.0 * math.pi, n)
            acc_x = 0.25 * np.sin(phases * 0.3) + rng.normal(0.0, 0.03, size=n)
            acc_y = 0.30 * np.cos(phases * 0.2) + rng.normal(0.0, 0.03, size=n)
            acc_z = 0.40 * np.sin(phases * 0.4) + rng.normal(0.0, 0.04, size=n)

            gyro_x = 12.0 * np.sin(phases * 0.5) + rng.normal(0.0, 0.8, size=n)
            gyro_y = 18.0 * np.cos(phases * 0.3) + rng.normal(0.0, 0.8, size=n)
            gyro_z = 8.0 * np.sin(phases * 0.7) + rng.normal(0.0, 0.8, size=n)

        else:
            acc_x = rng.normal(0.0, 0.01, size=n)
            acc_y = rng.normal(0.0, 0.01, size=n)
            acc_z = rng.normal(0.0, 0.01, size=n)
            gyro_x = rng.normal(0.0, 0.1, size=n)
            gyro_y = rng.normal(0.0, 0.1, size=n)
            gyro_z = rng.normal(0.0, 0.1, size=n)

        acc_data = np.vstack([acc_x, acc_y, acc_z])
        gyro_data = np.vstack([gyro_x, gyro_y, gyro_z])
        return acc_data, gyro_data
