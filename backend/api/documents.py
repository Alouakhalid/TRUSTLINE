"""Medical document intelligence gateway: RBAC-protected access to the existing
ai-engine document pipeline (upload -> extract -> pending review -> confirm).

Authorization model (enforced at the API boundary, never client-supplied):
- ASTRONAUT: upload documents for their OWN astronaut id; read own document
  status, extracted records, and confirmed findings. May NOT process, retry,
  review, or list pending records.
- MEDICAL_OFFICER / ADMINISTRATOR: full document workflow for any astronaut.
  The reviewer identity recorded on every review is taken from the signed
  token, never from the request body.

Demo isolation: the underlying document store (ai-engine SQLAlchemy edge DB)
does not currently carry a demo partition. Rather than risk polluting real
medical records, demo-mode document operations are REFUSED with an explicit
message. This is a documented limitation, not a silent bypass.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from backend.auth.modes import demo_mode
from backend.auth.rbac import current_user, require_privileged
from backend.services import audit
from backend.services.integrations import import_attribute

router = APIRouter(prefix="/documents", tags=["Medical Document Intelligence"])

_LOCK = threading.Lock()
_state: dict[str, Any] = {"services": None}


class RecordReviewBody(BaseModel):
    """Gateway-side shape validation for a reviewer decision."""

    record_id: str = Field(min_length=1, max_length=64)
    action: Literal["CONFIRMED", "REJECTED", "EDITED"]
    review_notes: Optional[str] = Field(default=None, max_length=4000)
    edited_test_name: Optional[str] = Field(default=None, max_length=128)
    edited_value: Optional[str] = Field(default=None, max_length=128)
    edited_unit: Optional[str] = Field(default=None, max_length=64)
    edited_reference_range: Optional[str] = Field(default=None, max_length=128)
    edited_collection_date: Optional[str] = Field(default=None, max_length=32)


def configure_document_stack(database_url: str | None = None, upload_dir: str | None = None, processed_docs_dir: str | None = None) -> None:
    """Deployment/test seam: point the document stack at explicit locations.

    Rebinds the ai-engine SQLAlchemy engine in place and re-creates the gateway
    services so they pick up the new settings. Never used to bypass validation.
    """
    with _LOCK:
        if database_url:
            reconfigure = import_attribute("agents.personal_health.repositories.base", "reconfigure_engine")
            init_db = import_attribute("agents.personal_health.repositories.base", "init_db")
            reconfigure(database_url)
            init_db()
            settings = import_attribute("agents.personal_health.config.settings", "get_settings")()
            settings.database_url = database_url
        settings = import_attribute("agents.personal_health.config.settings", "get_settings")()
        if upload_dir:
            settings.upload_dir = Path(upload_dir)
        if processed_docs_dir:
            settings.processed_docs_dir = Path(processed_docs_dir)
        _state["services"] = None  # force re-construction with the new settings


def _services() -> dict[str, Any]:
    with _LOCK:
        if _state["services"] is None:
            ingestion_cls = import_attribute("agents.personal_health.services.document_ingestion_service", "DocumentIngestionService")
            review_cls = import_attribute("agents.personal_health.services.medical_record_review_service", "MedicalRecordReviewService")
            repo_cls = import_attribute("agents.personal_health.repositories.medical_document_repository", "MedicalDocumentRepository")
            init_db = import_attribute("agents.personal_health.repositories.base", "init_db")
            init_db()
            _state["services"] = {
                "ingestion": ingestion_cls(),
                "review": review_cls(),
                "repo": repo_cls(),
            }
        return _state["services"]


def _guard_operational(is_demo: bool) -> None:
    if is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo-mode medical document operations are disabled: the document pipeline currently persists to the operational medical store only, and demo isolation there is not implemented.",
        )


def _can_access(user: dict[str, Any], astronaut_id: str) -> bool:
    if user.get("role") in {"MEDICAL_OFFICER", "ADMINISTRATOR"}:
        return True
    return user.get("role") == "ASTRONAUT" and user.get("astronaut_id") == astronaut_id


def _dump(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json") if hasattr(model, "model_dump") else dict(model)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    astronaut_id: str = Form(...),
    is_demo: bool = Depends(demo_mode),
    user: dict[str, Any] = Depends(current_user),
) -> Any:
    _guard_operational(is_demo)
    if not _can_access(user, astronaut_id):
        raise HTTPException(status_code=403, detail="Astronauts may only upload their own medical documents")
    try:
        content = await file.read()
        result = _services()["ingestion"].upload_document(
            file_bytes=content, filename=file.filename or "uploaded_document", astronaut_id=astronaut_id,
        )
    except Exception as exc:
        security_error = import_attribute("agents.personal_health.services.document_ingestion_service", "DocumentSecurityError")
        if isinstance(exc, security_error):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=f"Upload failed: {type(exc).__name__}") from exc
    audit.record(user, "UPLOAD", "MEDICAL_DOCUMENT", result.document_id, is_demo)
    return _dump(result)


@router.post("/{document_id}/process")
def process_document(
    document_id: str,
    force_ocr: bool = Query(default=False),
    is_demo: bool = Depends(demo_mode),
    user: dict[str, Any] = Depends(require_privileged),
) -> Any:
    _guard_operational(is_demo)
    try:
        result = _services()["ingestion"].process_document(document_id=document_id, force_ocr=force_ocr)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing error: {type(exc).__name__}") from exc
    audit.record(user, "PROCESS", "MEDICAL_DOCUMENT", document_id, is_demo)
    return _dump(result)


@router.get("/{document_id}")
def get_document(
    document_id: str,
    is_demo: bool = Depends(demo_mode),
    user: dict[str, Any] = Depends(current_user),
) -> Any:
    _guard_operational(is_demo)
    doc = _services()["repo"].get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _can_access(user, doc.astronaut_id):
        raise HTTPException(status_code=403, detail="Document belongs to another astronaut")
    return {
        "document_id": doc.document_id,
        "astronaut_id": doc.astronaut_id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size_bytes": doc.file_size_bytes,
        "processing_status": doc.processing_status,
        "upload_timestamp": doc.upload_timestamp.isoformat() if doc.upload_timestamp else None,
        "extraction_summary": json.loads(doc.extraction_summary_json or "{}"),
        "error_message": doc.error_message,
    }


@router.get("/{document_id}/records")
def get_document_records(
    document_id: str,
    is_demo: bool = Depends(demo_mode),
    user: dict[str, Any] = Depends(current_user),
) -> Any:
    _guard_operational(is_demo)
    doc = _services()["repo"].get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _can_access(user, doc.astronaut_id):
        raise HTTPException(status_code=403, detail="Document belongs to another astronaut")
    records = _services()["repo"].get_records_by_document(document_id)
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
            "review_status": r.review_status,
        }
        for r in records
    ]


@router.get("/pending/{astronaut_id}")
def get_pending_records(
    astronaut_id: str,
    is_demo: bool = Depends(demo_mode),
    user: dict[str, Any] = Depends(require_privileged),
) -> Any:
    _guard_operational(is_demo)
    return [_dump(item) for item in _services()["review"].get_pending_records(astronaut_id)]


@router.post("/records/{record_id}/review")
def review_record(
    record_id: str,
    request: RecordReviewBody,
    is_demo: bool = Depends(demo_mode),
    user: dict[str, Any] = Depends(require_privileged),
) -> Any:
    _guard_operational(is_demo)
    if record_id != request.record_id:
        raise HTTPException(status_code=400, detail="Record ID in path does not match request body")
    request_cls = import_attribute("agents.personal_health.schemas.medical_document", "RecordReviewRequest")
    # Reviewer identity comes from the signed token, never from the client body.
    authorized_request = request_cls(
        record_id=request.record_id,
        action=request.action,
        reviewer_id=user.get("username") or user.get("sub", "unknown"),
        review_notes=request.review_notes,
        edited_test_name=request.edited_test_name,
        edited_value=request.edited_value,
        edited_unit=request.edited_unit,
        edited_reference_range=request.edited_reference_range,
        edited_collection_date=request.edited_collection_date,
    )
    try:
        result = _services()["review"].review_record(authorized_request)
    except Exception as exc:
        not_found = import_attribute("agents.personal_health.services.medical_record_review_service", "RecordNotFoundError")
        if isinstance(exc, not_found):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=f"Review failed: {type(exc).__name__}") from exc
    audit.record(user, "REVIEW", "MEDICAL_RECORD", record_id, is_demo, metadata={"action": request.action})
    return _dump(result)


@router.post("/{document_id}/retry")
def retry_document(
    document_id: str,
    is_demo: bool = Depends(demo_mode),
    user: dict[str, Any] = Depends(require_privileged),
) -> Any:
    _guard_operational(is_demo)
    try:
        result = _services()["ingestion"].retry_document(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retry error: {type(exc).__name__}") from exc
    audit.record(user, "RETRY", "MEDICAL_DOCUMENT", document_id, is_demo)
    return _dump(result)


@router.get("/confirmed/{astronaut_id}")
def get_confirmed_findings(
    astronaut_id: str,
    is_demo: bool = Depends(demo_mode),
    user: dict[str, Any] = Depends(current_user),
) -> Any:
    _guard_operational(is_demo)
    if not _can_access(user, astronaut_id):
        raise HTTPException(status_code=403, detail="Confirmed findings are identity-isolated")
    return [_dump(item) for item in _services()["review"].get_confirmed_findings(astronaut_id)]
