"""Comprehensive Personal Health Assessment output schema."""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from .sensor_input import SensorIngestionContext
from .physiological_features import ExtractedFeature, Core14Features, HRVDiagnosticReport
from .ml_prediction import MLInferenceResult
from .symptom_event import SymptomEvent, ClarificationRequest, SymptomAssessmentStatus
from .rag_evidence import RAGEvidenceItem
from .mission_context import MissionContext

class AssessmentStatus(str, Enum):
    """Lifecycle execution status of the health assessment."""
    COMPLETED = "COMPLETED"
    URGENT_ESCALATION = "URGENT_ESCALATION"
    REQUIRES_CLARIFICATION = "REQUIRES_CLARIFICATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PROCESSING_FAILED = "PROCESSING_FAILED"

class EmergencyAssessmentStatus(str, Enum):
    """Deterministic scientific status of emergency safety evaluation."""
    NO_TRIGGER_DETECTED = "NO_TRIGGER_DETECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    ASSESSMENT_FAILED = "ASSESSMENT_FAILED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"

class BaselineStatus(str, Enum):
    """Availability of astronaut individualized baseline data."""
    NOT_AVAILABLE = "not_available"
    INSUFFICIENT_DATA = "insufficient_data"
    AVAILABLE = "available"
    INVALID = "invalid"

class EscalationDetails(BaseModel):
    """Emergency or urgent safety escalation parameters."""
    status: EmergencyAssessmentStatus = Field(default=EmergencyAssessmentStatus.NO_TRIGGER_DETECTED)
    required: bool = Field(default=False)
    urgency_level: str = Field(default="NOMINAL")
    reason_codes: List[str] = Field(default_factory=list)
    triggers: List[str] = Field(default_factory=list)
    immediate_actions: List[str] = Field(default_factory=list)
    protocol_reference: Optional[str] = None
    uncertainty_notes: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)

class EvidenceConflict(BaseModel):
    """Identified inconsistency between clinical, subjective, or sensor modalities."""
    conflict_type: str
    modality_a: str
    finding_a: str
    modality_b: str
    finding_b: str
    clinical_resolution: str

class PersonalHealthAssessment(BaseModel):
    """Structured assessment produced by Personal Health Agent for Supervisor."""
    assessment_id: str
    astronaut_id: str
    session_id: str
    execution_timestamp: datetime = Field(default_factory=datetime.utcnow)
    assessment_status: AssessmentStatus
    baseline_status: BaselineStatus = Field(default=BaselineStatus.NOT_AVAILABLE)

    sensor_quality_summary: Optional[SensorIngestionContext] = None
    core_features: Optional[Core14Features] = None
    physiological_findings: List[ExtractedFeature] = Field(default_factory=list)
    hrv_diagnostics: Optional[HRVDiagnosticReport] = None
    ml_findings: List[MLInferenceResult] = Field(default_factory=list)
    symptom_findings: List[SymptomEvent] = Field(default_factory=list)
    symptom_assessment_status: SymptomAssessmentStatus = Field(default=SymptomAssessmentStatus.NO_SYMPTOMS_REPORTED)
    health_profile_summary: Dict[str, Any] = Field(default_factory=dict)
    mission_context: Optional[MissionContext] = None
    retrieved_evidence: List[RAGEvidenceItem] = Field(default_factory=list)

    possible_explanations: List[str] = Field(default_factory=list)
    evidence_conflicts: List[EvidenceConflict] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    recommended_follow_up: List[str] = Field(default_factory=list)
    clarification_requests: List[ClarificationRequest] = Field(default_factory=list)

    escalation: EscalationDetails = Field(default_factory=EscalationDetails)
    next_agent: str = Field(default="risk_assessment_agent")
    llm_executive_synthesis: Optional[str] = None
