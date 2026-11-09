"""Groq Vision OCR client with retry handling, schema enforcement, and non-Groq prohibition."""
import json
import os
import re
import time
from typing import Dict, List, Optional, Any, Union
from groq import Groq, APIError, RateLimitError, APITimeoutError

from .schemas import ExtractedMedicalRecord, ExtractionMethod, ValidationStatus

class NonGroqProviderDisallowedError(RuntimeError):
    """Raised when an attempt is made to invoke an unauthorized OCR provider."""
    pass

class GroqVisionAPIError(Exception):
    """Raised on unrecoverable Groq Vision API failures."""
    pass

class GroqVisionClient:
    """Client for Groq Vision models handling medical document OCR."""

    MEDICAL_EXTRACTION_SYSTEM_PROMPT: str = (
        "You are an expert medical document intelligence and optical character recognition system. "
        "Your sole task is to accurately extract visible medical information from the provided document image. "
        "\n"
        "STRICT EXTRACTION GUIDELINES:\n"
        "1. Extract medical test names, visible numerical values, original units, reference ranges, dates, times, and laboratory/physician names.\n"
        "2. Preserve the EXACT visible text and language. If text is Arabic, extract in Arabic. If English, extract in English.\n"
        "3. DO NOT diagnose diseases, assess medical condition, or provide clinical opinions.\n"
        "4. DO NOT invent or infer missing units. If no unit is visible, set original_unit to null.\n"
        "5. DO NOT invent reference ranges or dates. If not explicitly present, set to null.\n"
        "6. DO NOT guess unclear or ambiguous digits. If a digit or value is ambiguous or smudged, record it as best visible, set extraction_status to 'AMBIGUOUS', and list the ambiguity in warnings.\n"
        "7. For tables, extract each row as an individual record preserving column values.\n"
        "8. Return ONLY valid, parseable JSON with the structure: "
        '{"records": [{"test_name": "...", "extracted_value": "...", "original_unit": "...", "reference_range": "...", "collection_date": "...", "collection_time": "...", "laboratory_name": "...", "physician_name": "...", "patient_identifier": "...", "source_text": "...", "confidence": 0.95, "is_ambiguous": false, "warnings": []}]}'
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = model or os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
        self.timeout = float(os.environ.get("GROQ_VISION_TIMEOUT", str(timeout)))
        self.max_retries = int(os.environ.get("GROQ_VISION_MAX_RETRIES", str(max_retries)))

        self._client: Optional[Groq] = None
        if self.api_key:
            self._client = Groq(api_key=self.api_key, timeout=self.timeout)

    def _ensure_groq_exclusivity(self, provider_hint: Optional[str] = None) -> None:
        """Enforce strict architectural constraint prohibiting alternative OCR providers."""
        if provider_hint and provider_hint.lower() not in ("groq", "groq_vision"):
            raise NonGroqProviderDisallowedError(
                f"Unauthorized OCR provider '{provider_hint}' requested. "
                "TRUSTLINE strictly enforces Groq Vision API exclusivity. "
                "PaddleOCR, Tesseract, EasyOCR, and other fallbacks are prohibited."
            )

    def is_available(self) -> bool:
        """Verify whether Groq client has credentials configured."""
        return self._client is not None and bool(self.api_key)

    def extract_from_image_url(
        self,
        image_data_url: str,
        document_id: str,
        source_type: str = "image",
        source_page_number: Optional[int] = None,
        source_image_id: Optional[str] = None,
        source_location: Optional[str] = None
    ) -> List[ExtractedMedicalRecord]:
        """Send image Data URL to Groq Vision and parse structured medical records."""
        self._ensure_groq_exclusivity("groq")

        if not self.is_available():
            raise GroqVisionAPIError("Groq API key not configured or client initialization failed.")

        user_content: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": "Extract all medical test results, laboratory values, units, reference ranges, and dates from this document image into structured JSON."
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": image_data_url
                }
            }
        ]

        attempt = 0
        last_error: Optional[Exception] = None
        backoff_delay = 1.0

        while attempt <= self.max_retries:
            attempt += 1
            try:
                assert self._client is not None
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.MEDICAL_EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.05,
                    max_tokens=2048,
                    response_format={"type": "json_object"} if "qwen" in self.model.lower() else None
                )

                content = response.choices[0].message.content or ""
                return self._parse_vision_response(
                    content=content,
                    document_id=document_id,
                    source_type=source_type,
                    source_page_number=source_page_number,
                    source_image_id=source_image_id,
                    source_location=source_location
                )

            except (RateLimitError, APITimeoutError) as transient_err:
                last_error = transient_err
                if attempt > self.max_retries:
                    break
                time.sleep(backoff_delay)
                backoff_delay *= 2.0
            except APIError as api_err:
                last_error = api_err
                break
            except Exception as gen_err:
                last_error = gen_err
                break

        raise GroqVisionAPIError(
            f"Groq Vision extraction failed after {attempt} attempts using model '{self.model}': {str(last_error)}"
        ) from last_error

    def _parse_vision_response(
        self,
        content: str,
        document_id: str,
        source_type: str,
        source_page_number: Optional[int],
        source_image_id: Optional[str],
        source_location: Optional[str]
    ) -> List[ExtractedMedicalRecord]:
        """Parse structured JSON from model response text into ExtractedMedicalRecord instances."""
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):].strip()
        if cleaned.startswith("```"):
            cleaned = cleaned[len("```"):].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-len("```")].strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as jde:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                except Exception:
                    raise GroqVisionAPIError(f"Malformed JSON from Groq Vision response: {str(jde)}") from jde
            else:
                raise GroqVisionAPIError(f"Failed to decode JSON from Groq Vision response: {str(jde)}") from jde

        raw_items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            raw_items = data
        elif isinstance(data, dict):
            if "records" in data and isinstance(data["records"], list):
                raw_items = data["records"]
            elif "results" in data and isinstance(data["results"], list):
                raw_items = data["results"]
            elif "tests" in data and isinstance(data["tests"], list):
                raw_items = data["tests"]
            else:
                for k, v in data.items():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        raw_items = v
                        break
                if not raw_items and "test_name" in data:
                    raw_items = [data]

        results: List[ExtractedMedicalRecord] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            test_name = str(item.get("test_name") or item.get("name") or item.get("parameter") or "").strip()
            val_str = str(item.get("extracted_value") or item.get("value") or item.get("result") or "").strip()
            if not test_name and not val_str:
                continue

            unit = item.get("original_unit") or item.get("unit")
            unit_str = str(unit).strip() if unit else None
            ref_range = item.get("reference_range") or item.get("normal_range") or item.get("reference")
            ref_range_str = str(ref_range).strip() if ref_range else None
            coll_date = item.get("collection_date") or item.get("date")
            coll_date_str = str(coll_date).strip() if coll_date else None
            coll_time = item.get("collection_time") or item.get("time")
            coll_time_str = str(coll_time).strip() if coll_time else None
            lab_name = item.get("laboratory_name") or item.get("lab")
            lab_str = str(lab_name).strip() if lab_name else None
            phys_name = item.get("physician_name") or item.get("doctor")
            phys_str = str(phys_name).strip() if phys_name else None
            patient_id = item.get("patient_identifier") or item.get("patient_id")
            patient_str = str(patient_id).strip() if patient_id else None

            confidence = float(item.get("confidence", 0.90))
            is_ambiguous = bool(item.get("is_ambiguous", False))
            warnings = list(item.get("warnings", []))

            status = ValidationStatus.NEEDS_REVIEW
            if is_ambiguous:
                status = ValidationStatus.AMBIGUOUS
                warnings.append("Ambiguous character or value reported by vision model.")
            elif confidence < 0.60:
                status = ValidationStatus.LOW_CONFIDENCE
                warnings.append(f"Low vision extraction confidence ({confidence:.2f}).")

            rec = ExtractedMedicalRecord(
                document_id=document_id,
                source_type=source_type,
                source_page_number=source_page_number,
                source_image_id=source_image_id,
                source_location=source_location,
                test_name=test_name,
                extracted_value=val_str,
                original_unit=unit_str,
                reference_range=ref_range_str,
                collection_date=coll_date_str,
                collection_time=coll_time_str,
                laboratory_name=lab_str,
                physician_name=phys_str,
                patient_identifier_if_present=patient_str,
                source_text=str(item.get("source_text") or f"{test_name}: {val_str} {unit_str or ''}").strip(),
                extraction_confidence=confidence,
                validation_status=status,
                validation_warnings=warnings,
                extraction_method=ExtractionMethod.GROQ_VISION_OCR
            )
            results.append(rec)

        return results
