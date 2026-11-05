"""Input schemas for the Sensor Quality Agent."""
from pathlib import Path
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator

class RecordingMetadata(BaseModel):
    astronaut_id: str = Field(..., min_length=1, description="Unique identifier for astronaut")
    session_id: str = Field(..., min_length=1, description="Unique identifier for acquisition session")
    recording_id: Optional[str] = Field(default=None, description="Identifier for specific recording segment")
    data_source: str = Field(default="wearable_sensors", description="Source description")
    device_id: Optional[str] = Field(default=None, description="Identifier of hardware device")
    environment: Optional[str] = Field(default="analog_mission", description="Mission or test environment")

class SensorSignalConfig(BaseModel):
    file: str = Field(..., description="Relative path to raw signal array file")
    sampling_rate: float = Field(..., gt=0.0, description="Sampling rate in Hertz")
    unit: str = Field(..., min_length=1, description="Physical unit of measurement")
    timestamp_file: Optional[str] = Field(default=None, description="Relative path to timestamp array file")
    channels: Optional[int] = Field(default=1, ge=1, description="Number of channels")
    missing_value_marker: Optional[float] = Field(default=None, description="Specific marker used for missing samples")
    calibration_factor: Optional[float] = Field(default=1.0, description="Calibration multiplier")

    @field_validator("file", "timestamp_file")
    @classmethod
    def prevent_path_traversal(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean_path = str(v).replace("\\", "/")
        if ".." in clean_path.split("/") or clean_path.startswith("/"):
            raise ValueError(f"Security validation failure: path traversal prohibited: {v}")
        return clean_path

class AstronautHealthManifest(BaseModel):
    metadata: RecordingMetadata
    signals: Dict[str, SensorSignalConfig] = Field(..., min_length=1)

    @field_validator("signals")
    @classmethod
    def validate_sensors(cls, v: Dict[str, SensorSignalConfig]) -> Dict[str, SensorSignalConfig]:
        valid_sensors = {"ECG", "EDA", "RESP", "EMG", "ACC", "TEMP"}
        for sensor_name in v.keys():
            normalized = sensor_name.upper()
            if normalized not in valid_sensors:
                raise ValueError(f"Unsupported sensor identifier: {sensor_name}. Allowed: {valid_sensors}")
        return v
