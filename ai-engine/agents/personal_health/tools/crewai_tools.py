"""CrewAI and LangChain tools exposing deterministic clinical intelligence modules."""
import json
from typing import Dict, List, Optional, Type, Any
from crewai.tools import tool
from pydantic import BaseModel, Field

from ..services.health_profile_service import HealthProfileService
from ..services.feature_extraction_service import FeatureExtractionService
from ..services.ml_inference_service import MLInferenceService
from ..services.symptom_service import SymptomService
from ..services.groq_voice_service import GroqVoiceService
from ..services.rag_service import MedicalRAGService
from ..services.escalation_service import EmergencyEscalationService
from ..services.medical_record_review_service import MedicalRecordReviewService

_health_profile_service = HealthProfileService()
_ml_service = None
_symptom_service = SymptomService()
_rag_service = MedicalRAGService()
_escalation_service = EmergencyEscalationService()
_review_service = MedicalRecordReviewService()

def get_ml_service() -> MLInferenceService:
    """Lazy initialize ML inference service."""
    global _ml_service
    if _ml_service is None:
        _ml_service = MLInferenceService()
    return _ml_service

@tool("QueryAstronautHealthProfile")
def query_health_profile_tool(astronaut_id: str) -> str:
    """Retrieve verified medical history, medications, and physical fitness profile for astronaut."""
    try:
        profile = _health_profile_service.get_or_create_profile(astronaut_id)
        return profile.model_dump_json(indent=2)
    except Exception as exc:
        return f"Error retrieving health profile: {str(exc)}"

@tool("RunStressInference")
def run_stress_inference_tool(features_json: str) -> str:
    """Execute WESAD HistGradientBoosting stress classifier on Core 14 physiological features JSON."""
    try:
        feat_dict = json.loads(features_json)
        svc = get_ml_service()
        res = svc.predict_from_dict(feat_dict)
        if res:
            return res.model_dump_json(indent=2)
        return "Failed to run inference: Missing required Core 14 features."
    except Exception as exc:
        return f"Inference execution error: {str(exc)}"

@tool("TranscribeGroqVoice")
def transcribe_groq_voice_tool(audio_path: str, language: str = "en") -> str:
    """Transcribe speech audio file strictly using Groq Whisper large-v3 API."""
    try:
        voice = GroqVoiceService()
        lang = language if language in ("en", "ar") else None
        res = voice.transcribe_audio(audio_file_path=audio_path, language=lang)
        return json.dumps(res, indent=2)
    except Exception as exc:
        return f"Groq voice transcription error: {str(exc)}"

@tool("ExtractSymptomReport")
def extract_symptom_report_tool(symptom_text: str, astronaut_id: str, session_id: str) -> str:
    """Extract structured SymptomEvent from text statement in Arabic or English."""
    try:
        event, clar = _symptom_service.process_text_symptom(
            text=symptom_text,
            astronaut_id=astronaut_id,
            session_id=session_id
        )
        if event:
            return event.model_dump_json(indent=2)
        if clar:
            return clar.model_dump_json(indent=2)
        return "No symptom detected."
    except Exception as exc:
        return f"Symptom extraction error: {str(exc)}"

@tool("QueryMedicalRAG")
def query_medical_rag_tool(query: str) -> str:
    """Retrieve evidence-based aerospace medical research and approved mission protocols."""
    try:
        items = _rag_service.query_medical_evidence(query=query, top_k=2)
        return json.dumps([item.model_dump() for item in items], default=str, indent=2)
    except Exception as exc:
        return f"Medical RAG search error: {str(exc)}"

@tool("QueryConfirmedMedicalRecords")
def query_confirmed_medical_records_tool(astronaut_id: str) -> str:
    """Retrieve verified laboratory findings and confirmed medical document records for an astronaut."""
    try:
        findings = _review_service.get_confirmed_findings(astronaut_id)
        if not findings:
            return "No confirmed clinical document records on file."
        return json.dumps([f.model_dump() for f in findings], default=str, indent=2)
    except Exception as exc:
        return f"Error querying confirmed medical records: {str(exc)}"

def get_personal_health_crewai_tools() -> List[Any]:
    """Return all CrewAI clinical tools."""
    return [
        query_health_profile_tool,
        run_stress_inference_tool,
        transcribe_groq_voice_tool,
        extract_symptom_report_tool,
        query_medical_rag_tool,
        query_confirmed_medical_records_tool
    ]
