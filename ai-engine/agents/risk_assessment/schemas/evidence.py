"""Evidence schemas for normalized cross-agent evidence items in TRUSTLINE."""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class RiskDomain(str, Enum):
    """Physiological, environmental, and data-integrity risk domains."""
    CARDIOVASCULAR = "CARDIOVASCULAR"
    RESPIRATORY = "RESPIRATORY"
    NEUROLOGICAL = "NEUROLOGICAL"
    SLEEP_AND_FATIGUE = "SLEEP_AND_FATIGUE"
    PSYCHOLOGICAL_AND_COGNITIVE = "PSYCHOLOGICAL_AND_COGNITIVE"
    THERMOREGULATORY = "THERMOREGULATORY"
    HYDRATION_AND_FLUID_BALANCE = "HYDRATION_AND_FLUID_BALANCE"
    MUSCULOSKELETAL = "MUSCULOSKELETAL"
    GENERAL_PHYSIOLOGICAL = "GENERAL_PHYSIOLOGICAL"
    DATA_QUALITY_RELATED = "DATA_QUALITY_RELATED"

class EvidenceSourceType(str, Enum):
    """Categorical source origins for ingested evidence."""
    SENSOR_QUALITY = "sensor_quality"
    PHYSIOLOGICAL_MEASUREMENT = "physiological_measurement"
    EXPERIMENTAL_ML_CLASSIFIER = "experimental_ml_classifier"
    REPORTED_SYMPTOM = "reported_symptom"
    CONFIRMED_MEDICAL_RECORD = "confirmed_medical_record"
    HEALTH_EVENT = "health_event"
    MISSION_CONTEXT = "mission_context"
    RETRIEVED_PROTOCOL = "retrieved_protocol"
    RETRIEVED_LITERATURE = "retrieved_literature"

class EvidenceValidity(str, Enum):
    """Epistemic validity rating of observed evidence item."""
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"
    UNCERTAIN = "UNCERTAIN"
    NOT_AVAILABLE = "NOT_AVAILABLE"

class NormalizedEvidenceItem(BaseModel):
    """Unified cross-agent evidence item preserving provenance and observational context."""
    evidence_id: str = Field(..., description="Unique deterministic evidence identifier")
    source_agent: str = Field(..., description="Agent or subsystem originating the evidence")
    source_type: EvidenceSourceType = Field(..., description="Modality or type of source evidence")
    domain: RiskDomain = Field(..., description="Primary risk domain associated with metric")
    metric_name: str = Field(..., description="Standardized physiological or operational metric")
    observed_value: Any = Field(..., description="Observed numerical or categorical reading")
    unit: Optional[str] = Field(default=None, description="Physical measurement unit")
    timestamp: Optional[datetime] = Field(default=None, description="Observation or acquisition timestamp")
    observation_window: Optional[str] = Field(default=None, description="Temporal acquisition duration or window")
    validity_status: EvidenceValidity = Field(default=EvidenceValidity.VALID, description="Data validity state")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Evidential certainty score")
    quality_status: Optional[str] = Field(default=None, description="Underlying sensor quality status")
    source_reference: str = Field(..., description="Pointer to source document, sensor channel, or report ID")
    evidence_description: str = Field(..., description="Human-readable factual summary of the evidence")
    is_confirmed: bool = Field(default=False, description="True only if verified by medical personnel or valid telemetry")
    is_historical: bool = Field(default=False, description="True if evidence represents prior longitudinal context")
    evidence_classification: str = Field(default="CLINICAL_OBSERVATION", description="Contextual classification e.g. CLINICAL_OBSERVATION, EXPERIMENTAL_CONTEXT, DATA_INTEGRITY")
    is_eligible_for_risk: bool = Field(default=True, description="True if evidence can support positive risk bounds or confidence")
    raw_context: Dict[str, Any] = Field(default_factory=dict, description="Original unmutated payload context")
