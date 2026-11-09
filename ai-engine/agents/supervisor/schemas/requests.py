"""Request and input schemas for the TRUSTLINE Supervisor Agent."""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class InputModality(str, Enum):
    """Input modality types supported by the Supervisor intake."""
    TEXT = "TEXT"
    VOICE = "VOICE"
    SENSOR = "SENSOR"
    DOCUMENT = "DOCUMENT"
    MULTIMODAL = "MULTIMODAL"

class AstronautInput(BaseModel):
    """Container for multimodal user/sensor inputs provided to the Supervisor."""
    text_query: Optional[str] = Field(default=None, description="Freeform text query or symptom description")
    voice_audio_path: Optional[str] = Field(default=None, description="Path to voice audio recording file")
    voice_language: Optional[str] = Field(default=None, description="Language code for voice transcription")
    sensor_manifest_path: Optional[str] = Field(default=None, description="Path to sensor acquisition manifest")
    raw_sensor_manifest: Optional[Dict[str, Any]] = Field(default=None, description="In-memory manifest dictionary")
    document_paths: List[str] = Field(default_factory=list, description="Paths to uploaded medical documents")
    mission_context: Optional[Dict[str, Any]] = Field(default=None, description="Mission elapsed time, phase, habitat")

class SupervisorRequest(BaseModel):
    """Top-level structured request initiating a multi-agent Supervisor workflow."""
    request_id: str = Field(..., min_length=1, description="Unique client or transaction request identifier")
    astronaut_id: str = Field(..., min_length=1, description="Astronaut subject identifier e.g. AST-001")
    session_id: str = Field(..., min_length=1, description="Acquisition session identifier e.g. SESSION-001")
    modality: InputModality = Field(default=InputModality.MULTIMODAL, description="Primary modality of input")
    input_data: AstronautInput = Field(default_factory=AstronautInput, description="Multimodal input payload")
    request_metadata: Dict[str, Any] = Field(default_factory=dict, description="Client context and metadata")
