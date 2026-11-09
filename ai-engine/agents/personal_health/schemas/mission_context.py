"""Schemas for mission operational and environmental context."""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class MissionPhase(str, Enum):
    """Operational phase of the space mission."""
    PRE_LAUNCH = "PRE_LAUNCH"
    ASCENT = "ASCENT"
    ORBITAL_TRANSIT = "ORBITAL_TRANSIT"
    EXTRAVEHICULAR_ACTIVITY = "EXTRAVEHICULAR_ACTIVITY"
    LUNAR_SURFACE = "LUNAR_SURFACE"
    DEEP_SPACE_CRUISE = "DEEP_SPACE_CRUISE"
    RE_ENTRY = "RE_ENTRY"
    POST_LANDING = "POST_LANDING"

class MissionContext(BaseModel):
    """Structured operational context surrounding health assessment."""
    mission_id: str = Field(default="UNKNOWN_MISSION")
    mission_phase: Optional[MissionPhase] = Field(default=None)
    mission_elapsed_time_hours: Optional[float] = Field(default=None, ge=0.0)
    microgravity_exposure_days: Optional[float] = Field(default=None, ge=0.0)
    radiation_dose_msv: Optional[float] = Field(default=None, ge=0.0)
    current_activity: Optional[str] = Field(default=None)
    planned_sleep_hours: Optional[float] = Field(default=None, ge=0.0, le=24.0)
    actual_sleep_hours: Optional[float] = Field(default=None, ge=0.0, le=24.0)
    cabin_pressure_kpa: Optional[float] = Field(default=None, gt=0.0)
    cabin_o2_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    cabin_co2_percent: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    cabin_temperature_c: Optional[float] = Field(default=None)
    is_eva_active: bool = Field(default=False)
    is_context_supplied: bool = Field(default=False)
