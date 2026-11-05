"""Signal dataclasses and fundamental schemas."""
from enum import Enum
from typing import Optional, List, Dict, Any
import numpy as np
from pydantic import BaseModel, Field, ConfigDict

class QualityStatus(str, Enum):
    VALID = "VALID"
    ACCEPTABLE_WITH_WARNING = "ACCEPTABLE_WITH_WARNING"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

class IssueSeverity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class SensorType(str, Enum):
    ECG = "ECG"
    EDA = "EDA"
    RESP = "RESP"
    EMG = "EMG"
    ACC = "ACC"
    TEMP = "TEMP"

class TimeInterval(BaseModel):
    start: float = Field(..., description="Start timestamp in seconds")
    end: float = Field(..., description="End timestamp in seconds")

class SignalWindow(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    sensor: str
    window_index: int
    start_time: float
    end_time: float
    sampling_rate: float
    data: Any
    timestamps: Any

class SensorStreamData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    sensor: str
    sampling_rate: float
    unit: str
    data: np.ndarray
    timestamps: np.ndarray
    duration_seconds: float
    total_samples: int
