"""Mission operational scenario engine coordinating multi-sensor physiological synthesis."""
import time
import uuid
from typing import Dict, List, Tuple, Optional
import numpy as np

from ..schemas import (
    SensorType,
    ScenarioType,
    FaultType,
    FaultInjectionConfig,
    TelemetryPacket,
    SpaceEnvironmentPacket
)
from ..registry import SensorRegistry, default_sensor_registry
from ..physiological_models.cardiac import CardiacModel
from ..physiological_models.respiratory import RespiratoryModel
from ..physiological_models.autonomic import ElectrodermalModel
from ..physiological_models.thermal import ThermalModel
from ..physiological_models.biomechanical import BiomechanicalModel, MotionState
from ..fault_injector import FaultInjector


class ScenarioEngine:
    """Coordinates coupled physiological and biomechanical models across mission operational scenarios."""

    def __init__(
        self,
        astronaut_id: str = "AST-001",
        session_id: str = "SESSION-SIM-001",
        registry: Optional[SensorRegistry] = None
    ):
        self.astronaut_id = astronaut_id
        self.session_id = session_id
        self.registry = registry or default_sensor_registry

        # Core physiological generator models
        self.cardiac = CardiacModel()
        self.respiratory = RespiratoryModel()
        self.autonomic = ElectrodermalModel()
        self.thermal = ThermalModel()
        self.biomechanical = BiomechanicalModel()
        self.fault_injector = FaultInjector()

        # Engine runtime state
        self.current_scenario = ScenarioType.SCENARIO_A_REST
        self.elapsed_time_sec = 0.0
        self.sequence_counters: Dict[SensorType, int] = {st: 0 for st in SensorType}
        self.current_radiation_packet: Optional[SpaceEnvironmentPacket] = None

        # Apply initial scenario
        self.set_scenario(ScenarioType.SCENARIO_A_REST)

    def set_scenario(self, scenario: ScenarioType) -> None:
        """Configure physiological models and fault injection for the selected operational scenario."""
        self.current_scenario = scenario
        self.fault_injector.clear_faults()

        if scenario == ScenarioType.SCENARIO_A_REST:
            self.cardiac.set_target_state(hr_bpm=68.0, hrv_rmssd_ms=55.0)
            self.respiratory.set_target_rate(14.0)
            self.autonomic.set_target_tonic(2.5)
            self.thermal.set_metabolic_state(1.0)
            self.biomechanical.set_motion_state(MotionState.MICROGRAVITY_REST)

        elif scenario == ScenarioType.SCENARIO_B_EVA_ACTIVITY:
            self.cardiac.set_target_state(hr_bpm=150.0, hrv_rmssd_ms=15.0)
            self.respiratory.set_target_rate(28.0)
            self.autonomic.set_target_tonic(12.0)
            self.thermal.set_metabolic_state(6.5)
            self.biomechanical.set_motion_state(MotionState.LOCOMOTION_EXERCISE)

        elif scenario == ScenarioType.SCENARIO_C_ACUTE_STRESS:
            self.cardiac.set_target_state(hr_bpm=102.0, hrv_rmssd_ms=18.0)
            self.respiratory.set_target_rate(22.0)
            self.autonomic.set_target_tonic(8.5)
            self.thermal.set_metabolic_state(1.5)
            self.biomechanical.set_motion_state(MotionState.MICROGRAVITY_REST)

        elif scenario == ScenarioType.SCENARIO_D_SLEEP_RECOVERY:
            self.cardiac.set_target_state(hr_bpm=52.0, hrv_rmssd_ms=75.0)
            self.respiratory.set_target_rate(11.0)
            self.autonomic.set_target_tonic(0.8)
            self.thermal.set_metabolic_state(0.9)
            self.biomechanical.set_motion_state(MotionState.MICROGRAVITY_REST)

        elif scenario == ScenarioType.SCENARIO_E_HARDWARE_FAULT:
            self.cardiac.set_target_state(hr_bpm=72.0, hrv_rmssd_ms=45.0)
            self.respiratory.set_target_rate(15.0)
            self.autonomic.set_target_tonic(3.0)
            self.thermal.set_metabolic_state(1.0)
            self.biomechanical.set_motion_state(MotionState.MICROGRAVITY_REST)
            # Inject ECG flatline + EDA saturation
            self.fault_injector.add_fault(
                FaultInjectionConfig(
                    fault_type=FaultType.FLATLINE,
                    target_sensor=SensorType.ECG,
                    start_time_sec=0.0,
                    duration_sec=3600.0,
                    severity=1.0
                )
            )
            self.fault_injector.add_fault(
                FaultInjectionConfig(
                    fault_type=FaultType.CLIPPING,
                    target_sensor=SensorType.EDA,
                    start_time_sec=0.0,
                    duration_sec=3600.0,
                    severity=0.9
                )
            )

        elif scenario == ScenarioType.SCENARIO_F_RADIATION_COMPOSITE:
            # Multi-factor event: astronaut acute stress response during active SPE radiation alert
            self.cardiac.set_target_state(hr_bpm=108.0, hrv_rmssd_ms=16.0)
            self.respiratory.set_target_rate(24.0)
            self.autonomic.set_target_tonic(9.0)
            self.thermal.set_metabolic_state(1.8)
            self.biomechanical.set_motion_state(MotionState.EVA_MANEUVERING)

    def generate_step(
        self,
        duration_sec: float = 1.0,
        epoch_ms: Optional[int] = None,
        seed: Optional[int] = None
    ) -> Tuple[List[TelemetryPacket], Optional[SpaceEnvironmentPacket]]:
        """Generate one temporal time step across all sensors and space environment.

        Returns:
            packets: List of framed TelemetryPacket instances
            space_packet: Optional SpaceEnvironmentPacket (if space environment active)
        """
        if epoch_ms is None:
            epoch_ms = int(time.time() * 1000)

        packets: List[TelemetryPacket] = []

        # 1. Respiration first (for RSA coupling with cardiac model)
        resp_data, resp_phase = self.respiratory.generate_segment(duration_sec, seed=seed)
        # 2. Cardiac (ECG, PPG, HR) coupled to respiration phase
        ecg_data, ppg_data, hr_series = self.cardiac.generate_segment(
            duration_sec, respiratory_phase_signal=resp_phase, seed=seed
        )
        # 3. Autonomic (EDA)
        burst_prob = 0.25 if self.current_scenario in {ScenarioType.SCENARIO_C_ACUTE_STRESS, ScenarioType.SCENARIO_F_RADIATION_COMPOSITE} else 0.04
        eda_data = self.autonomic.generate_segment(duration_sec, burst_probability_per_sec=burst_prob, seed=seed)
        # 4. Thermal (Core & Skin Temp)
        core_temp_data, skin_temp_data = self.thermal.generate_segment(duration_sec, seed=seed)
        # 5. Biomechanical (Accelerometer & Gyroscope)
        acc_data, gyro_data = self.biomechanical.generate_segment(duration_sec, seed=seed)
        # 6. SpO2 (arterial saturation derived from respiratory & cardiac state)
        spo2_mean = 94.0 if self.current_scenario == ScenarioType.SCENARIO_B_EVA_ACTIVITY else 98.2
        spo2_data = np.array([[spo2_mean]])
        # Derived HR point sample
        hr_point_data = np.array([[float(np.mean(hr_series))]])

        sensor_arrays: Dict[SensorType, np.ndarray] = {
            SensorType.ECG: ecg_data,
            SensorType.PPG: ppg_data,
            SensorType.HR: hr_point_data,
            SensorType.SPO2: spo2_data,
            SensorType.SKIN_TEMP: skin_temp_data,
            SensorType.CORE_TEMP: core_temp_data,
            SensorType.EDA: eda_data,
            SensorType.RESPIRATION: resp_data,
            SensorType.ACCELEROMETER: acc_data,
            SensorType.GYROSCOPE: gyro_data
        }

        # Apply fault injection and create TelemetryPacket for each sensor
        for s_type, raw_arr in sensor_arrays.items():
            s_def = self.registry.get_sensor(s_type)
            fs = s_def.default_sampling_rate_hz if s_def else 1.0

            # Signal fault transformation
            corrupted_arr = self.fault_injector.apply_signal_faults(
                s_type, raw_arr, fs, self.elapsed_time_sec
            )

            # Transmission packet loss check
            if self.fault_injector.should_drop_packet(s_type, self.elapsed_time_sec):
                continue

            seq = self.sequence_counters[s_type]
            self.sequence_counters[s_type] += 1

            channels_list = corrupted_arr.tolist()
            crc = TelemetryPacket.compute_crc32(s_type.value, seq, epoch_ms, channels_list)

            pkt = TelemetryPacket(
                packet_id=f"PKT-{s_type.value[:3]}-{uuid.uuid4().hex[:8].upper()}",
                sequence_number=seq,
                astronaut_id=self.astronaut_id,
                session_id=self.session_id,
                timestamp_epoch_ms=epoch_ms,
                sensor_type=s_type,
                sample_rate_hz=fs,
                channels_data=channels_list,
                checksum_crc32=crc,
                hardware_metadata={"scenario": self.current_scenario.value}
            )
            packets.append(pkt)

        # Space environment simulation packet (Independent of ML!)
        space_pkt = self._generate_space_packet(epoch_ms)

        self.elapsed_time_sec += duration_sec
        return packets, space_pkt

    def _generate_space_packet(self, epoch_ms: int) -> SpaceEnvironmentPacket:
        """Generate space radiation environment telemetry packet."""
        if self.current_scenario == ScenarioType.SCENARIO_F_RADIATION_COMPOSITE:
            # Active SPE event exceeding action limit (650 µGy/h)
            dose_rate = 650.0
            eq_rate = dose_rate * 0.0022  # mSv/h
            spe_active = True
            alert = "ALARM"
            flux = 1250.0
        elif self.current_scenario == ScenarioType.SCENARIO_B_EVA_ACTIVITY:
            # Outside habitat: slightly higher background dose rate
            dose_rate = 45.0
            eq_rate = dose_rate * 0.0035
            spe_active = False
            alert = "NOMINAL"
            flux = 5.0
        else:
            # Deep space / lunar habitat shielded baseline GCR
            dose_rate = 22.0
            eq_rate = dose_rate * 0.0035
            spe_active = False
            alert = "NOMINAL"
            flux = 1.0

        cum_dose = 35.0 + (self.elapsed_time_sec / 3600.0) * eq_rate

        return SpaceEnvironmentPacket(
            packet_id=f"SPE-ENV-{uuid.uuid4().hex[:8].upper()}",
            timestamp_epoch_ms=epoch_ms,
            dose_rate_microgy_h=round(dose_rate, 2),
            equivalent_dose_rate_msv_h=round(eq_rate, 4),
            cumulative_mission_dose_msv=round(cum_dose, 3),
            spe_active=spe_active,
            spe_flux_pfu=flux,
            shielding_thickness_g_cm2=10.0,
            alert_level=alert
        )
