"""Sensor Registry for TRUSTLINE external biomedical monitoring hardware."""
from typing import Dict, List, Optional
from .schemas import SensorType, SensorDefinition


class SensorRegistry:
    """Central repository defining all simulated sensor channels and standards."""

    def __init__(self):
        self._sensors: Dict[SensorType, SensorDefinition] = {}
        self._initialize_default_registry()

    def _initialize_default_registry(self) -> None:
        """Register the baseline clinical and biomechanical astronaut sensors."""
        default_defs = [
            SensorDefinition(
                sensor_type=SensorType.ECG,
                display_name="Electrocardiogram (3-Lead)",
                unit="mV",
                default_sampling_rate_hz=256.0,
                nominal_range_min=-3.0,
                nominal_range_max=3.0,
                noise_floor_std=0.015,
                adc_resolution_bits=16,
                channels_count=3,
                description="3-lead thoracic ECG capturing electrical cardiac depolarization and repolarization."
            ),
            SensorDefinition(
                sensor_type=SensorType.PPG,
                display_name="Photoplethysmogram",
                unit="normalized",
                default_sampling_rate_hz=64.0,
                nominal_range_min=0.0,
                nominal_range_max=1.0,
                noise_floor_std=0.005,
                adc_resolution_bits=16,
                channels_count=1,
                description="Optical wrist/finger plethysmography measuring volumetric blood pulse variation."
            ),
            SensorDefinition(
                sensor_type=SensorType.HR,
                display_name="Instantaneous Heart Rate",
                unit="bpm",
                default_sampling_rate_hz=1.0,
                nominal_range_min=30.0,
                nominal_range_max=220.0,
                noise_floor_std=0.1,
                adc_resolution_bits=12,
                channels_count=1,
                description="Derived instantaneous cardiac frequency in beats per minute."
            ),
            SensorDefinition(
                sensor_type=SensorType.SPO2,
                display_name="Peripheral Blood Oxygen Saturation",
                unit="%",
                default_sampling_rate_hz=1.0,
                nominal_range_min=70.0,
                nominal_range_max=100.0,
                noise_floor_std=0.2,
                adc_resolution_bits=12,
                channels_count=1,
                description="Pulse oximetry estimating arterial blood oxygenation saturation percentage."
            ),
            SensorDefinition(
                sensor_type=SensorType.SKIN_TEMP,
                display_name="Peripheral Skin Surface Temperature",
                unit="°C",
                default_sampling_rate_hz=4.0,
                nominal_range_min=25.0,
                nominal_range_max=42.0,
                noise_floor_std=0.02,
                adc_resolution_bits=14,
                channels_count=1,
                description="Continuous thermistor reading skin temperature on the inner wrist or torso."
            ),
            SensorDefinition(
                sensor_type=SensorType.CORE_TEMP,
                display_name="Core Body Temperature",
                unit="°C",
                default_sampling_rate_hz=1.0,
                nominal_range_min=34.0,
                nominal_range_max=42.0,
                noise_floor_std=0.01,
                adc_resolution_bits=16,
                channels_count=1,
                description="Estimated or measured deep visceral thermal core temperature."
            ),
            SensorDefinition(
                sensor_type=SensorType.EDA,
                display_name="Electrodermal Activity (GSR)",
                unit="µS",
                default_sampling_rate_hz=4.0,
                nominal_range_min=0.05,
                nominal_range_max=40.0,
                noise_floor_std=0.01,
                adc_resolution_bits=16,
                channels_count=1,
                description="Continuous palmar/wrist skin conductance reflecting sympathetic arousal."
            ),
            SensorDefinition(
                sensor_type=SensorType.RESPIRATION,
                display_name="Respiratory Effort Waveform",
                unit="a.u.",
                default_sampling_rate_hz=32.0,
                nominal_range_min=-5.0,
                nominal_range_max=5.0,
                noise_floor_std=0.02,
                adc_resolution_bits=16,
                channels_count=1,
                description="Respiratory inductive plethysmography (RIP) chest belt measuring expansion/contraction."
            ),
            SensorDefinition(
                sensor_type=SensorType.ACCELEROMETER,
                display_name="3-Axis Accelerometer",
                unit="g",
                default_sampling_rate_hz=32.0,
                nominal_range_min=-16.0,
                nominal_range_max=16.0,
                noise_floor_std=0.005,
                adc_resolution_bits=16,
                channels_count=3,
                description="Triaxial linear accelerometer capturing microgravity floating and physical activity."
            ),
            SensorDefinition(
                sensor_type=SensorType.GYROSCOPE,
                display_name="3-Axis Angular Gyroscope",
                unit="deg/s",
                default_sampling_rate_hz=32.0,
                nominal_range_min=-2000.0,
                nominal_range_max=2000.0,
                noise_floor_std=0.05,
                adc_resolution_bits=16,
                channels_count=3,
                description="Triaxial angular velocity sensor tracking body orientation and EVA rotations."
            )
        ]

        for s_def in default_defs:
            self._sensors[s_def.sensor_type] = s_def

    def get_sensor(self, sensor_type: SensorType) -> Optional[SensorDefinition]:
        """Retrieve definition for a sensor type."""
        return self._sensors.get(sensor_type)

    def list_sensors(self) -> List[SensorDefinition]:
        """List all registered sensors."""
        return list(self._sensors.values())

    def get_sampling_rate(self, sensor_type: SensorType) -> float:
        """Fetch default sampling frequency for sensor."""
        sensor = self.get_sensor(sensor_type)
        if not sensor:
            raise KeyError(f"Sensor type '{sensor_type}' not found in registry.")
        return sensor.default_sampling_rate_hz

    def is_value_in_range(self, sensor_type: SensorType, value: float) -> bool:
        """Check if numerical reading lies within nominal physical boundaries."""
        sensor = self.get_sensor(sensor_type)
        if not sensor:
            return False
        return sensor.nominal_range_min <= value <= sensor.nominal_range_max


default_sensor_registry = SensorRegistry()
