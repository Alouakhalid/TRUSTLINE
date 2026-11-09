"""Schemas for astronaut symptom intelligence across multi-modal channels."""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class InputChannel(str, Enum):
    """Input modality through which symptom was reported."""
    CHAT_TEXT = "CHAT_TEXT"
    STRUCTURED_FORM = "STRUCTURED_FORM"
    GROQ_VOICE = "GROQ_VOICE"

class SymptomSeverity(str, Enum):
    """Reported severity level."""
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"

class SymptomCategory(str, Enum):
    """Broad physiological or cognitive symptom domain."""
    CARDIORESPIRATORY = "CARDIORESPIRATORY"
    NEUROLOGICAL = "NEUROLOGICAL"
    GASTROINTESTINAL = "GASTROINTESTINAL"
    MUSCULOSKELETAL = "MUSCULOSKELETAL"
    PSYCHOLOGICAL = "PSYCHOLOGICAL"
    COGNITIVE = "COGNITIVE"
    GENERAL = "GENERAL"

class SymptomAssessmentStatus(str, Enum):
    """Clinical assessment status of astronaut subjective symptoms."""
    NO_SYMPTOMS_REPORTED = "NO_SYMPTOMS_REPORTED"
    CONFIRMED_ABSENCE_OF_SYMPTOMS = "CONFIRMED_ABSENCE_OF_SYMPTOMS"
    SYMPTOMS_NOT_ASSESSED = "SYMPTOMS_NOT_ASSESSED"
    SYMPTOM_DATA_UNAVAILABLE = "SYMPTOM_DATA_UNAVAILABLE"

class SymptomEvent(BaseModel):
    """Normalized symptom event record across text, form, or Groq voice channels."""
    event_id: str
    astronaut_id: str
    session_id: str
    symptom_category: SymptomCategory
    symptom_type: str = Field(..., description="Specific symptom descriptor e.g. chest_tightness, headache, nausea")
    description: str
    severity: Optional[SymptomSeverity] = Field(default=None, description="Reported severity; strictly None if not stated")
    location: Optional[str] = Field(default=None)
    onset_time: Optional[str] = Field(default=None)
    duration: Optional[str] = Field(default=None)
    current_status: str = Field(default="active")
    associated_symptoms: List[str] = Field(default_factory=list)
    potential_triggers: List[str] = Field(default_factory=list)
    input_channel: InputChannel
    original_text_or_transcript: str
    confirmation_status: str = Field(default="confirmed")
    event_timestamp: datetime = Field(default_factory=datetime.utcnow)
    data_provenance: str = Field(default="astronaut_self_report")

class ClarificationRequest(BaseModel):
    """Structured question returned to the Supervisor for ambiguous symptom statements."""
    request_id: str
    symptom_in_question: str
    ambiguity_reason: str
    clarification_prompt: str
    suggested_options: List[str] = Field(default_factory=list)
