"""Structured Pydantic schemas for medical document optical character recognition and intelligence."""
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field

class DocumentType(str, Enum):
    """Supported document types for medical ingestion."""
    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"
    UNKNOWN = "unknown"

class ExtractionMethod(str, Enum):
    """Method used to extract information from document pages or sections."""
    NATIVE_TEXT = "native_text"
    GROQ_VISION_OCR = "groq_vision_ocr"
    HYBRID = "hybrid"
    NO_EXTRACTABLE_CONTENT = "no_extractable_content"

class ValidationStatus(str, Enum):
    """Deterministic validation statuses for extracted medical records."""
    VALIDATED = "VALIDATED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID_FORMAT = "INVALID_FORMAT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CONFLICTING_EXTRACTION = "CONFLICTING_EXTRACTION"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"

class ReviewStatus(str, Enum):
    """Human-in-the-loop review status for pending medical records."""
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"

class ExtractedMedicalRecord(BaseModel):
    """Structured clinical record extracted from a medical document or image."""
    record_id: str = Field(default_factory=lambda: f"REC-{uuid.uuid4().hex[:8].upper()}")
    document_id: str
    document_type: DocumentType = DocumentType.UNKNOWN
    source_type: str = Field(default="document_page", description="page, embedded_image, standalone_image, table")
    source_page_number: Optional[int] = None
    source_image_id: Optional[str] = None
    source_location: Optional[str] = None
    test_name: str
    extracted_value: str
    normalized_value: Optional[float] = None
    original_unit: Optional[str] = None
    normalized_unit: Optional[str] = None
    reference_range: Optional[str] = None
    reference_range_unit: Optional[str] = None
    collection_date: Optional[str] = None
    collection_time: Optional[str] = None
    laboratory_name: Optional[str] = None
    physician_name: Optional[str] = None
    patient_identifier_if_present: Optional[str] = None
    source_text: str = ""
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    validation_status: ValidationStatus = ValidationStatus.NEEDS_REVIEW
    validation_warnings: List[str] = Field(default_factory=list)
    extraction_method: ExtractionMethod = ExtractionMethod.NATIVE_TEXT
    is_historical: bool = Field(default=True, description="Strictly marks document extractions as historical records, not live telemetry")
    abnormality_flag: Optional[str] = Field(default=None, description="Clinical abnormality flag e.g. HIGH, LOW, NORMAL if explicitly documented")
    conflict_detected: bool = Field(default=False, description="True if conflicting source extractions exist for this measurement")
    conflicting_records: List[str] = Field(default_factory=list, description="IDs of conflicting extraction records")
    document_date: Optional[str] = Field(default=None, description="Explicit document creation or report date")
    clinical_observations: List[str] = Field(default_factory=list, description="Documented clinical observations")
    diagnoses: List[str] = Field(default_factory=list, description="Explicitly documented clinical diagnoses")
    medications: List[str] = Field(default_factory=list, description="Explicitly documented medications and dosages")
    allergies: List[str] = Field(default_factory=list, description="Explicitly documented allergies")

class PageProcessingMetadata(BaseModel):
    """Processing metadata associated with an individual document page or section."""
    document_id: str
    page_number: int
    extraction_method: ExtractionMethod
    native_text_available: bool = False
    images_detected: int = 0
    ocr_required: bool = False
    ocr_status: str = "NOT_REQUIRED"
    extraction_warnings: List[str] = Field(default_factory=list)
    processing_timestamp: datetime = Field(default_factory=datetime.utcnow)

class DocumentProcessingResult(BaseModel):
    """Aggregated processing result for an uploaded medical document."""
    document_id: str
    filename: str
    document_type: DocumentType
    file_hash_sha256: str
    file_size_bytes: int
    total_pages_or_images: int = 1
    page_metadata: List[PageProcessingMetadata] = Field(default_factory=list)
    extracted_records: List[ExtractedMedicalRecord] = Field(default_factory=list)
    overall_status: str = "COMPLETED"
    processing_warnings: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
