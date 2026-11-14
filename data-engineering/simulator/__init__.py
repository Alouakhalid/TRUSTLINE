"""TRUSTLINE Sensor Simulation & External Hardware Emulation Package."""
from .schemas import (
    SensorType,
    ScenarioType,
    FaultType,
    SensorDefinition,
    FaultInjectionConfig,
    TelemetryPacket,
    SpaceEnvironmentPacket,
    SimulatorStatus
)
from .registry import SensorRegistry, default_sensor_registry

__all__ = [
    "SensorType",
    "ScenarioType",
    "FaultType",
    "SensorDefinition",
    "FaultInjectionConfig",
    "TelemetryPacket",
    "SpaceEnvironmentPacket",
    "SimulatorStatus",
    "SensorRegistry",
    "default_sensor_registry"
]
