"""Input schema for the TRUSTLINE Risk Assessment Agent."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from sensor_quality.schemas.output_schema import SensorQualityReport
from personal_health.schemas.assessment import PersonalHealthAssessment
from personal_health.schemas.medical_document import ConfirmedMedicalFinding
from personal_health.schemas.symptom_event import SymptomEvent
from personal_health.schemas.health_profile import HealthEvent
from personal_health.schemas.mission_context import MissionContext
from personal_health.schemas.rag_evidence import RAGEvidenceItem

class RiskAssessmentInput(BaseModel):
    """Complete upstream telemetry and context payload ingested by Risk Assessment Agent."""
    assessment_id: str = Field(default_factory=lambda: f"RA-{uuid.uuid4().hex[:8].upper()}")
    astronaut_id: str = Field(default="", description="Astronaut subject identifier")
    session_id: str = Field(default="", description="Monitoring session identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Evaluation timestamp")
    sensor_quality_report: Optional[SensorQualityReport] = Field(default=None, description="Report from Sensor Quality Agent")
    personal_health_assessment: Optional[PersonalHealthAssessment] = Field(default=None, description="Assessment from Personal Health Agent")
    confirmed_medical_records: List[ConfirmedMedicalFinding] = Field(default_factory=list, description="Only human-confirmed laboratory records")
    reported_symptoms: List[SymptomEvent] = Field(default_factory=list, description="Explicit subjective symptom complaints")
    health_events: List[HealthEvent] = Field(default_factory=list, description="Historical clinical occurrences")
    mission_context: Optional[MissionContext] = Field(default=None, description="Current spaceflight mission phase and environment")
    applicable_protocols: List[RAGEvidenceItem] = Field(default_factory=list, description="Approved mission medical protocol excerpts")
    previous_assessment_reference: Optional[str] = Field(default=None, description="Pointer to preceding risk assessment ID")
