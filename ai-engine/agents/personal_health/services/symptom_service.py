"""Symptom intelligence module normalizing text, form, and Groq-transcribed voice."""
import json
import os
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from groq import Groq

from ..config.settings import get_settings
from ..repositories.symptom_repository import SymptomRepository
from ..schemas.symptom_event import (
    SymptomEvent,
    ClarificationRequest,
    InputChannel,
    SymptomSeverity,
    SymptomCategory
)
from .groq_voice_service import GroqVoiceService

SYMPTOM_EXTRACTION_SYSTEM_PROMPT = """You are the TRUSTLINE Symptom Extraction Engine for astronaut health monitoring.
Analyze the user's reported symptom in English or Arabic (including Egyptian and Saudi dialects).
Extract facts strictly reported by the astronaut. Do not infer missing severities, locations, or onsets.

Output ONLY valid JSON with this exact schema:
{
  "symptom_category": "CARDIORESPIRATORY | NEUROLOGICAL | GASTROINTESTINAL | MUSCULOSKELETAL | PSYCHOLOGICAL | COGNITIVE | GENERAL",
  "symptom_type": "string (e.g. chest_pain, headache, dizziness, nausea, fatigue, shortness_of_breath, anxiety)",
  "description": "factual summary of what user reported",
  "severity": "MILD | MODERATE | SEVERE | CRITICAL | null",
  "location": "anatomical location or null",
  "onset_time": "reported onset or null",
  "duration": "reported duration or null",
  "associated_symptoms": ["list of other mentioned symptoms"],
  "potential_triggers": ["list of reported triggers"],
  "is_ambiguous": false,
  "clarification_prompt": "string or null if not ambiguous"
}
"""

class SymptomService:
    """Service ingesting and extracting standardized symptom events."""

    def __init__(
        self,
        repository: Optional[SymptomRepository] = None,
        voice_service: Optional[GroqVoiceService] = None
    ):
        cfg = get_settings()
        self.repository = repository or SymptomRepository()
        self.voice_service = voice_service or GroqVoiceService()
        self.api_key = cfg.groq_api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = cfg.groq_chat_model
        self._groq_client = Groq(api_key=self.api_key) if self.api_key else None

    def process_text_symptom(
        self,
        text: str,
        astronaut_id: str,
        session_id: str,
        channel: InputChannel = InputChannel.CHAT_TEXT
    ) -> Tuple[Optional[SymptomEvent], Optional[ClarificationRequest]]:
        """Extract structured symptom event from unstructured text."""
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("Symptom report text cannot be empty.")

        extracted = self._extract_with_llm(cleaned_text)
        if extracted.get("is_ambiguous") and extracted.get("clarification_prompt"):
            req = ClarificationRequest(
                request_id=f"CLR-{uuid.uuid4().hex[:8].upper()}",
                symptom_in_question=extracted.get("symptom_type", "unspecified"),
                ambiguity_reason="Reported symptoms require clinical clarification",
                clarification_prompt=extracted["clarification_prompt"],
                suggested_options=["MILD", "MODERATE", "SEVERE"]
            )
            return None, req

        severity_val = None
        if extracted.get("severity") in ("MILD", "MODERATE", "SEVERE", "CRITICAL"):
            severity_val = SymptomSeverity(extracted["severity"])

        cat_val = SymptomCategory.GENERAL
        raw_cat = extracted.get("symptom_category", "GENERAL").upper()
        if hasattr(SymptomCategory, raw_cat):
            cat_val = SymptomCategory[raw_cat]

        event = SymptomEvent(
            event_id=f"SYM-{uuid.uuid4().hex[:8].upper()}",
            astronaut_id=astronaut_id,
            session_id=session_id,
            symptom_category=cat_val,
            symptom_type=extracted.get("symptom_type", "general_discomfort"),
            description=extracted.get("description", cleaned_text),
            severity=severity_val,
            location=extracted.get("location"),
            onset_time=extracted.get("onset_time"),
            duration=extracted.get("duration"),
            current_status="active",
            associated_symptoms=extracted.get("associated_symptoms", []),
            potential_triggers=extracted.get("potential_triggers", []),
            input_channel=channel,
            original_text_or_transcript=cleaned_text,
            confirmation_status="confirmed",
            event_timestamp=datetime.utcnow()
        )
        self.repository.save_symptom(event)
        return event, None

    def process_voice_symptom(
        self,
        audio_file_path: str,
        astronaut_id: str,
        session_id: str,
        language: Optional[str] = None
    ) -> Tuple[Optional[SymptomEvent], Optional[ClarificationRequest], Dict[str, Any]]:
        """Transcribe audio via Groq Whisper and extract structured symptom."""
        transcription_res = self.voice_service.transcribe_audio(
            audio_file_path=audio_file_path,
            language=language
        )
        transcript = transcription_res.get("transcription_text", "")
        if not transcript:
            raise ValueError("Groq voice transcription returned empty speech content.")

        event, clarification = self.process_text_symptom(
            text=transcript,
            astronaut_id=astronaut_id,
            session_id=session_id,
            channel=InputChannel.GROQ_VOICE
        )
        return event, clarification, transcription_res

    def process_structured_symptom(
        self,
        data: Dict[str, Any],
        astronaut_id: str,
        session_id: str
    ) -> SymptomEvent:
        """Ingest pre-structured symptom form data."""
        severity = data.get("severity")
        severity_enum = SymptomSeverity(severity) if severity in ("MILD", "MODERATE", "SEVERE", "CRITICAL") else None
        cat = data.get("symptom_category", "GENERAL")
        cat_enum = SymptomCategory(cat) if cat in [c.value for c in SymptomCategory] else SymptomCategory.GENERAL

        event = SymptomEvent(
            event_id=f"SYM-{uuid.uuid4().hex[:8].upper()}",
            astronaut_id=astronaut_id,
            session_id=session_id,
            symptom_category=cat_enum,
            symptom_type=data.get("symptom_type", "unspecified"),
            description=data.get("description", "Structured form symptom report"),
            severity=severity_enum,
            location=data.get("location"),
            onset_time=data.get("onset_time"),
            duration=data.get("duration"),
            current_status="active",
            associated_symptoms=data.get("associated_symptoms", []),
            potential_triggers=data.get("potential_triggers", []),
            input_channel=InputChannel.STRUCTURED_FORM,
            original_text_or_transcript=json.dumps(data),
            confirmation_status="confirmed",
            event_timestamp=datetime.utcnow()
        )
        self.repository.save_symptom(event)
        return event

    def _extract_with_llm(self, text: str) -> Dict[str, Any]:
        """Query Groq LLM with structured output or fallback to deterministic rules."""
        if self._groq_client:
            try:
                resp = self._groq_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYMPTOM_EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Symptom statement: {text}"}
                    ],
                    temperature=0.1,
                    max_tokens=400,
                    response_format={"type": "json_object"}
                )
                raw_json = resp.choices[0].message.content
                return json.loads(raw_json)
            except Exception:
                pass

        return self._rule_based_extraction(text)

    def _rule_based_extraction(self, text: str) -> Dict[str, Any]:
        """Deterministic rule-based extractor for spacecraft edge or offline mode."""
        lower = text.lower()
        cat = "GENERAL"
        s_type = "discomfort"
        severity = None

        if any(w in lower for w in ["chest", "heart", "breath", "breathing", "palpitation", "صدر", "تنفس", "قلب"]):
            cat = "CARDIORESPIRATORY"
            s_type = "chest_discomfort" if "chest" in lower or "صدر" in lower else "dyspnea"
        elif any(w in lower for w in ["headache", "dizzy", "dizziness", "migraine", "صداع", "دوخة"]):
            cat = "NEUROLOGICAL"
            s_type = "headache" if "headache" in lower or "صداع" in lower else "dizziness"
        elif any(w in lower for w in ["nausea", "vomit", "stomach", "غثيان", "معدة"]):
            cat = "GASTROINTESTINAL"
            s_type = "nausea"
        elif any(w in lower for w in ["muscle", "joint", "back", "neck", "عضلات", "مفصل"]):
            cat = "MUSCULOSKELETAL"
            s_type = "muscle_pain"
        elif any(w in lower for w in ["stress", "anxious", "anxiety", "isolated", "قلق", "توتر"]):
            cat = "PSYCHOLOGICAL"
            s_type = "acute_stress"

        if any(w in lower for w in ["severe", "unbearable", "crushing", "شديد", "حاد"]):
            severity = "SEVERE"
        elif any(w in lower for w in ["moderate", "medium", "متوسط"]):
            severity = "MODERATE"
        elif any(w in lower for w in ["mild", "slight", "خفيف"]):
            severity = "MILD"

        return {
            "symptom_category": cat,
            "symptom_type": s_type,
            "description": text,
            "severity": severity,
            "location": None,
            "onset_time": None,
            "duration": None,
            "associated_symptoms": [],
            "potential_triggers": [],
            "is_ambiguous": False,
            "clarification_prompt": None
        }
