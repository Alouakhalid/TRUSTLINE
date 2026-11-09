"""FastAPI router exposing endpoints for medical document ingestion, extraction, and review."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, status

from ..services.document_ingestion_service import (
    DocumentIngestionService,
    DocumentSecurityError
)
from ..services.medical_record_review_service import (
    MedicalRecordReviewService,
    RecordNotFoundError
)
from ..schemas.medical_document import (
    DocumentUploadResponse,
    DocumentProcessResponse,
    RecordReviewRequest,
    RecordReviewResponse,
    ConfirmedMedicalFinding,
    ReviewStatus
)
from ..repositories.medical_document_repository import MedicalDocumentRepository

router = APIRouter(prefix="/api/documents", tags=["Medical Document Intelligence"])

_ingestion_service = DocumentIngestionService()
_review_service = MedicalRecordReviewService()
_doc_repo = MedicalDocumentRepository()

@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_medical_document(
    file: UploadFile = File(...),
    astronaut_id: str = Form(...)
):
    """Upload a medical PDF, DOCX, or standalone image document for ingestion."""
    try:
        content = await file.read()
        filename = file.filename or "uploaded_document"
        return _ingestion_service.upload_document(
            file_bytes=content,
            filename=filename,
            astronaut_id=astronaut_id
        )
    except DocumentSecurityError as dse:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(dse))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Upload failed: {str(exc)}")

@router.post("/{document_id}/process", response_model=DocumentProcessResponse)
async def process_medical_document(
    document_id: str,
    force_ocr: bool = Query(default=False)
):
    """Execute text extraction and Groq Vision OCR on uploaded document."""
    try:
        return _ingestion_service.process_document(
            document_id=document_id,
            force_ocr=force_ocr
        )
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnf))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Processing error: {str(exc)}")

@router.get("/{document_id}")
async def get_document_status(document_id: str):
    """Retrieve tracking record and extraction summary for an ingested document."""
    doc = _doc_repo.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")
    import json
    return {
        "document_id": doc.document_id,
        "astronaut_id": doc.astronaut_id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size_bytes": doc.file_size_bytes,
        "processing_status": doc.processing_status,
        "upload_timestamp": doc.upload_timestamp.isoformat() if doc.upload_timestamp else None,
        "extraction_summary": json.loads(doc.extraction_summary_json or "{}"),
        "error_message": doc.error_message
    }

@router.get("/{document_id}/records")
async def get_document_records(document_id: str):
    """Query all extracted records associated with a specific document."""
    records = _doc_repo.get_records_by_document(document_id)
    import json
    return [
        {
            "record_id": r.record_id,
            "document_id": r.document_id,
            "astronaut_id": r.astronaut_id,
            "test_name": r.test_name,
            "extracted_value": r.extracted_value,
            "normalized_value": r.normalized_value,
            "original_unit": r.original_unit,
            "reference_range": r.reference_range,
            "source_type": r.source_type,
            "source_location": r.source_location,
            "extraction_confidence": r.extraction_confidence,
            "validation_status": r.validation_status,
            "validation_warnings": json.loads(r.validation_warnings_json or "[]"),
            "review_status": r.review_status
        }
        for r in records
    ]

@router.get("/pending/{astronaut_id}")
async def get_pending_records(astronaut_id: str):
    """Retrieve all pending medical records awaiting reviewer confirmation for an astronaut."""
    return _review_service.get_pending_records(astronaut_id)

@router.post("/records/{record_id}/review", response_model=RecordReviewResponse)
async def review_medical_record(
    record_id: str,
    request: RecordReviewRequest
):
    """Submit clinical reviewer decision (CONFIRMED, REJECTED, EDITED) for an extracted record."""
    if record_id != request.record_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Record ID in path does not match request body."
        )
    try:
        return _review_service.review_record(request)
    except RecordNotFoundError as rne:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(rne))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Review failed: {str(exc)}")

@router.post("/{document_id}/retry", response_model=DocumentProcessResponse)
async def retry_document_processing(document_id: str):
    """Retry extraction with forced Groq Vision OCR on a document."""
    try:
        return _ingestion_service.retry_document(document_id)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnf))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Retry error: {str(exc)}")

@router.get("/confirmed/{astronaut_id}", response_model=List[ConfirmedMedicalFinding])
async def get_confirmed_medical_findings(astronaut_id: str):
    """Retrieve confirmed clinical findings merged into astronaut health records."""
    return _review_service.get_confirmed_findings(astronaut_id)
