"""Schemas for medical document ingestion, review workflow, and health profile linkage."""
from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

from ocr.schemas import (
    DocumentType,
    ExtractionMethod,
    ValidationStatus,
    ReviewStatus,
    ExtractedMedicalRecord,
    PageProcessingMetadata,
    DocumentProcessingResult
)

class DocumentUploadResponse(BaseModel):
    """Response returned upon successful medical document upload."""
    document_id: str
    astronaut_id: str
    filename: str
    file_hash_sha256: str
    file_type: DocumentType
    file_size_bytes: int
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = "UPLOADED"

class DocumentProcessResponse(BaseModel):
    """Response summarizing the extraction and deterministic validation results."""
    document_id: str
    astronaut_id: str
    filename: str
    document_type: DocumentType
    overall_status: str
    total_pages_or_images: int
    total_extracted_records: int
    pending_records_count: int
    validated_records_count: int
    flagged_records_count: int
    processing_warnings: List[str] = Field(default_factory=list)

class RecordReviewRequest(BaseModel):
    """Payload submitted by clinical reviewer to confirm, edit, or reject a pending record."""
    record_id: str
    action: ReviewStatus = Field(..., description="CONFIRMED, REJECTED, or EDITED")
    reviewer_id: str = Field(..., min_length=1)
    review_notes: Optional[str] = None
    edited_test_name: Optional[str] = None
    edited_value: Optional[str] = None
    edited_unit: Optional[str] = None
    edited_reference_range: Optional[str] = None
    edited_collection_date: Optional[str] = None

class RecordReviewResponse(BaseModel):
    """Response acknowledging reviewer decision on an extracted medical record."""
    record_id: str
    document_id: str
    astronaut_id: str
    review_status: ReviewStatus
    reviewed_by: str
    review_timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str

class ConfirmedMedicalFinding(BaseModel):
    """Confirmed clinical laboratory measurement integrated into astronaut health history."""
    record_id: str
    document_id: str
    astronaut_id: str
    test_name: str
    value_string: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    collection_date: Optional[str] = None
    laboratory_name: Optional[str] = None
    confirmation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    confirmed_by: str
