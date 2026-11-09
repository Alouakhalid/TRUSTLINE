"""Schemas for ingesting and validating upstream Sensor Quality outputs."""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class QuarantinedSensorInfo(BaseModel):
    """Information regarding a sensor rejected by Sensor Quality Agent."""
    sensor: str
    rejection_reason: str
    quality_score: float

class SensorIngestionContext(BaseModel):
    """Normalized upstream sensor quality status and metadata."""
    astronaut_id: str
    session_id: str
    recording_id: Optional[str] = None
    overall_quality_score: float
    overall_quality_status: str
    can_proceed: bool
    valid_sensors: List[str] = Field(default_factory=list)
    degraded_sensors: List[str] = Field(default_factory=list)
    quarantined_sensors: List[QuarantinedSensorInfo] = Field(default_factory=list)
    upstream_warnings: List[str] = Field(default_factory=list)
    upstream_llm_briefing: Optional[str] = None
