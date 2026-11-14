"""Schemas and data models for TRUSTLINE external sensor simulator."""
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
import zlib
from pydantic import BaseModel, Field, field_validator


class SensorType(str, Enum):
    """Supported physiological and biomechanical sensor types."""
    ECG = "ECG"
    PPG = "PPG"
    HR = "HR"
    SPO2 = "SPO2"
    SKIN_TEMP = "SKIN_TEMP"
    CORE_TEMP = "CORE_TEMP"
    EDA = "EDA"
    RESPIRATION = "RESPIRATION"
    ACCELEROMETER = "ACCELEROMETER"
    GYROSCOPE = "GYROSCOPE"


class ScenarioType(str, Enum):
    """Standardized mission operational scenarios A through F."""
    SCENARIO_A_REST = "SCENARIO_A_REST"
    SCENARIO_B_EVA_ACTIVITY = "SCENARIO_B_EVA_ACTIVITY"
    SCENARIO_C_ACUTE_STRESS = "SCENARIO_C_ACUTE_STRESS"
    SCENARIO_D_SLEEP_RECOVERY = "SCENARIO_D_SLEEP_RECOVERY"
    SCENARIO_E_HARDWARE_FAULT = "SCENARIO_E_HARDWARE_FAULT"
    SCENARIO_F_RADIATION_COMPOSITE = "SCENARIO_F_RADIATION_COMPOSITE"


class FaultType(str, Enum):
    """Hardware and transmission fault injection modes."""
    NONE = "NONE"
    FLATLINE = "FLATLINE"
    BASELINE_WANDER = "BASELINE_WANDER"
    POWERLINE_NOISE = "POWERLINE_NOISE"
    CLIPPING = "CLIPPING"
    PACKET_LOSS = "PACKET_LOSS"
    JITTER = "JITTER"


class SensorDefinition(BaseModel):
    """Aerospace-grade specification for an individual sensor channel."""
    sensor_type: SensorType
    display_name: str
    unit: str
    default_sampling_rate_hz: float = Field(..., gt=0.0)
    nominal_range_min: float
    nominal_range_max: float
    noise_floor_std: float = Field(default=0.01, ge=0.0)
    adc_resolution_bits: int = Field(default=16, ge=8, le=32)
    channels_count: int = Field(default=1, ge=1)
    description: str = ""

    @field_validator("nominal_range_max")
    @classmethod
    def validate_range(cls, v: float, info: Any) -> float:
        min_val = info.data.get("nominal_range_min")
        if min_val is not None and v <= min_val:
            raise ValueError(f"nominal_range_max ({v}) must be greater than nominal_range_min ({min_val})")
        return v


class FaultInjectionConfig(BaseModel):
    """Configuration for deterministic or stochastic fault injection."""
    fault_type: FaultType = FaultType.NONE
    target_sensor: Optional[SensorType] = None
    start_time_sec: float = Field(default=0.0, ge=0.0)
    duration_sec: float = Field(default=10.0, gt=0.0)
    severity: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_hz: Optional[float] = Field(default=50.0, description="For powerline/wander noise")
    loss_rate: Optional[float] = Field(default=0.15, ge=0.0, le=1.0, description="For packet loss")


class TelemetryPacket(BaseModel):
    """Framed packet transmitting physiological data from external hardware."""
    packet_id: str
    sequence_number: int = Field(..., ge=0)
    astronaut_id: str = Field(..., description="Unique subject ID or AST-UNKNOWN")
    session_id: str = Field(..., description="Unique mission acquisition session")
    timestamp_epoch_ms: int = Field(..., gt=0)
    sensor_type: SensorType
    sample_rate_hz: float = Field(..., gt=0.0)
    channels_data: List[List[float]] = Field(..., description="Data array per channel")
    checksum_crc32: int
    hardware_metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("astronaut_id")
    @classmethod
    def validate_astro_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Astronaut ID cannot be empty string.")
        return s

    @classmethod
    def compute_crc32(cls, sensor_type: str, seq: int, ts: int, data: List[List[float]]) -> int:
        """Compute deterministic CRC32 checksum over packet contents."""
        serialized = f"{sensor_type}:{seq}:{ts}:{data}".encode("utf-8")
        return zlib.crc32(serialized) & 0xFFFFFFFF

    def verify_checksum(self) -> bool:
        """Verify transmission integrity of this packet."""
        expected = self.compute_crc32(
            self.sensor_type.value,
            self.sequence_number,
            self.timestamp_epoch_ms,
            self.channels_data
        )
        return self.checksum_crc32 == expected


class SpaceEnvironmentPacket(BaseModel):
    """Telemetry packet from external spacecraft radiation monitoring instrumentation."""
    packet_id: str
    timestamp_epoch_ms: int = Field(..., gt=0)
    dose_rate_microgy_h: float = Field(..., ge=0.0, description="Absorbed dose rate in silicon/tissue (µGy/h)")
    equivalent_dose_rate_msv_h: float = Field(..., ge=0.0, description="Equivalent dose rate (mSv/h)")
    cumulative_mission_dose_msv: float = Field(..., ge=0.0, description="Cumulative mission exposure (mSv)")
    spe_active: bool = Field(default=False, description="Solar Particle Event in progress flag")
    spe_flux_pfu: float = Field(default=0.0, ge=0.0, description="Proton flux >10 MeV (pfu: protons/cm2-s-sr)")
    shielding_thickness_g_cm2: float = Field(default=10.0, gt=0.0, description="Equivalent aluminum shielding thickness")
    alert_level: str = Field(default="NOMINAL", description="NOMINAL, ADVISORY, WARNING, ALARM")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SimulatorStatus(BaseModel):
    """Overall runtime status of the sensor simulation environment."""
    is_running: bool
    current_scenario: ScenarioType
    elapsed_seconds: float
    total_packets_sent: int
    total_bytes_sent: int
    active_sensors: List[SensorType]
    active_faults: List[FaultType]
    space_environment_active: bool
