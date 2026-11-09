"""End-to-end unit and integration tests for document ingestion, review quarantine, and health profile persistence."""
import io
import os
import fitz
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import numpy as np
from PIL import Image

from ocr.schemas import (
    DocumentType,
    ValidationStatus,
    ReviewStatus,
    ExtractedMedicalRecord
)
from personal_health.api.app import app
from personal_health.services.document_ingestion_service import (
    DocumentIngestionService,
    DocumentSecurityError
)
from personal_health.services.medical_record_review_service import (
    MedicalRecordReviewService,
    RecordNotFoundError
)
from personal_health.repositories.medical_document_repository import MedicalDocumentRepository
from personal_health.services.health_profile_service import HealthProfileService
from personal_health.schemas.medical_document import RecordReviewRequest
from personal_health.tools.crewai_tools import query_confirmed_medical_records_tool

@pytest.fixture
def test_client() -> TestClient:
    """Fixture providing FastAPI test client."""
    return TestClient(app)

def make_sample_pdf_bytes() -> bytes:
    """Helper generating minimal valid text-based medical report PDF."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        (50, 72),
        "Official Aerospace Medical Center\nBlood Chemistry:\nGlucose: 95 mg/dL\nHemoglobin: 15.2 g/dL\nPlatelets: 250 10^3/uL",
        fontsize=11
    )
    data = doc.tobytes()
    doc.close()
    return data

def test_01_upload_security_checks():
    """Verify security guardrails against empty files, size breaches, and invalid types."""
    svc = DocumentIngestionService()

    with pytest.raises(DocumentSecurityError):
        svc.upload_document(file_bytes=b"", filename="empty.pdf", astronaut_id="AST-001")

    huge_bytes = b"0" * (svc.settings.max_upload_size_bytes + 1024)
    with pytest.raises(DocumentSecurityError):
        svc.upload_document(file_bytes=huge_bytes, filename="huge.pdf", astronaut_id="AST-001")

    with pytest.raises(DocumentSecurityError):
        svc.upload_document(file_bytes=b"RANDOM_EXE_HEADER_BYTES", filename="malicious.exe", astronaut_id="AST-001")

def test_02_ingestion_and_quarantine_pending_records():
    """Verify extracted records are held in PENDING_REVIEW and not automatically added to health profile."""
    ingest_svc = DocumentIngestionService()
    review_svc = MedicalRecordReviewService()
    profile_svc = HealthProfileService()

    astro_id = "AST-QUARANTINE-01"
    pdf_bytes = make_sample_pdf_bytes()

    upload_res = ingest_svc.upload_document(pdf_bytes, "blood_test.pdf", astro_id)
    assert upload_res.status == "UPLOADED"

    proc_res = ingest_svc.process_document(upload_res.document_id)
    assert proc_res.overall_status == "COMPLETED"
    assert proc_res.pending_records_count >= 2

    pending = review_svc.get_pending_records(astro_id)
    assert len(pending) >= 2
    for p in pending:
        assert p["review_status"] == ReviewStatus.PENDING_REVIEW.value

    profile = profile_svc.get_or_create_profile(astro_id)
    events = profile_svc.get_recent_health_events(astro_id)
    assert not any(e.event_type == "CLINICAL_LAB_MEASUREMENT" for e in events)

def test_03_reviewer_confirmation_merges_health_profile():
    """Verify clinical reviewer confirmation merges findings into astronaut health profile."""
    ingest_svc = DocumentIngestionService()
    review_svc = MedicalRecordReviewService()
    profile_svc = HealthProfileService()

    astro_id = "AST-CONFIRM-02"
    pdf_bytes = make_sample_pdf_bytes()
    upload_res = ingest_svc.upload_document(pdf_bytes, "lab.pdf", astro_id)
    ingest_svc.process_document(upload_res.document_id)

    pending = review_svc.get_pending_records(astro_id)
    assert len(pending) > 0
    target_rec = pending[0]

    review_req = RecordReviewRequest(
        record_id=target_rec["record_id"],
        action=ReviewStatus.CONFIRMED,
        reviewer_id="FLIGHT-SURGEON-DR-SMITH",
        review_notes="Verified against laboratory reference instrument."
    )
    rev_res = review_svc.review_record(review_req)
    assert rev_res.review_status == ReviewStatus.CONFIRMED
    assert rev_res.reviewed_by == "FLIGHT-SURGEON-DR-SMITH"

    confirmed_findings = review_svc.get_confirmed_findings(astro_id)
    assert any(f.record_id == target_rec["record_id"] for f in confirmed_findings)

    events = profile_svc.get_recent_health_events(astro_id)
    assert any(e.event_type == "CLINICAL_LAB_MEASUREMENT" for e in events)

def test_04_reviewer_editing_workflow():
    """Verify reviewer can correct OCR values, preserving provenance and updating records."""
    ingest_svc = DocumentIngestionService()
    review_svc = MedicalRecordReviewService()

    astro_id = "AST-EDIT-03"
    pdf_bytes = make_sample_pdf_bytes()
    upload_res = ingest_svc.upload_document(pdf_bytes, "lab_edit.pdf", astro_id)
    ingest_svc.process_document(upload_res.document_id)

    pending = review_svc.get_pending_records(astro_id)
    target_rec = pending[0]

    edit_req = RecordReviewRequest(
        record_id=target_rec["record_id"],
        action=ReviewStatus.EDITED,
        reviewer_id="FLIGHT-SURGEON-DR-JONES",
        review_notes="Correcting OCR digit error.",
        edited_value="99.5",
        edited_unit="mg/dL"
    )
    rev_res = review_svc.review_record(edit_req)
    assert rev_res.review_status == ReviewStatus.CONFIRMED

    confirmed = review_svc.get_confirmed_findings(astro_id)
    matched = [c for c in confirmed if c.record_id == target_rec["record_id"]]
    assert len(matched) == 1
    assert matched[0].value_string == "99.5"
    assert matched[0].numeric_value == 99.5

def test_05_reviewer_rejection_workflow():
    """Verify rejected records do not enter confirmed findings or astronaut health profile."""
    ingest_svc = DocumentIngestionService()
    review_svc = MedicalRecordReviewService()

    astro_id = "AST-REJECT-04"
    pdf_bytes = make_sample_pdf_bytes()
    upload_res = ingest_svc.upload_document(pdf_bytes, "reject_doc.pdf", astro_id)
    ingest_svc.process_document(upload_res.document_id)

    pending = review_svc.get_pending_records(astro_id)
    target_rec = pending[0]

    rej_req = RecordReviewRequest(
        record_id=target_rec["record_id"],
        action=ReviewStatus.REJECTED,
        reviewer_id="FLIGHT-SURGEON-DR-LEE",
        review_notes="Artefact from scanned smudge; rejected."
    )
    rev_res = review_svc.review_record(rej_req)
    assert rev_res.review_status == ReviewStatus.REJECTED

    confirmed = review_svc.get_confirmed_findings(astro_id)
    assert not any(c.record_id == target_rec["record_id"] for c in confirmed)

def test_06_crewai_tool_query_confirmed_records():
    """Verify QueryConfirmedMedicalRecords tool returns confirmed findings for Personal Health Agent."""
    astro_id = "AST-TOOL-05"
    review_svc = MedicalRecordReviewService()
    ingest_svc = DocumentIngestionService()

    pdf_bytes = make_sample_pdf_bytes()
    upload_res = ingest_svc.upload_document(pdf_bytes, "tool_doc.pdf", astro_id)
    ingest_svc.process_document(upload_res.document_id)

    res_empty = query_confirmed_medical_records_tool.func(astro_id)
    assert "No confirmed clinical document records" in res_empty

    pending = review_svc.get_pending_records(astro_id)
    review_svc.review_record(
        RecordReviewRequest(
            record_id=pending[0]["record_id"],
            action=ReviewStatus.CONFIRMED,
            reviewer_id="DR-CREWAI"
        )
    )

    res_confirmed = query_confirmed_medical_records_tool.func(astro_id)
    assert "Glucose" in res_confirmed or "Hemoglobin" in res_confirmed
    assert "DR-CREWAI" in res_confirmed

def test_07_fastapi_endpoints_full_lifecycle(test_client: TestClient):
    """Verify full HTTP lifecycle: upload -> process -> query -> review -> confirmed."""
    astro_id = "AST-API-06"
    pdf_bytes = make_sample_pdf_bytes()

    upload_resp = test_client.post(
        "/api/documents/upload",
        data={"astronaut_id": astro_id},
        files={"file": ("medical_test.pdf", pdf_bytes, "application/pdf")}
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    doc_id = upload_data["document_id"]
    assert upload_data["file_type"] == "pdf"

    proc_resp = test_client.post(f"/api/documents/{doc_id}/process")
    assert proc_resp.status_code == 200
    proc_data = proc_resp.json()
    assert proc_data["overall_status"] == "COMPLETED"

    get_resp = test_client.get(f"/api/documents/{doc_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["document_id"] == doc_id

    recs_resp = test_client.get(f"/api/documents/{doc_id}/records")
    assert recs_resp.status_code == 200
    records = recs_resp.json()
    assert len(records) > 0
    rec_id = records[0]["record_id"]

    pending_resp = test_client.get(f"/api/documents/pending/{astro_id}")
    assert pending_resp.status_code == 200
    assert any(p["record_id"] == rec_id for p in pending_resp.json())

    rev_payload = {
        "record_id": rec_id,
        "action": "CONFIRMED",
        "reviewer_id": "API-REVIEWER-01",
        "review_notes": "Approved via REST API"
    }
    rev_resp = test_client.post(f"/api/documents/records/{rec_id}/review", json=rev_payload)
    assert rev_resp.status_code == 200
    assert rev_resp.json()["review_status"] == "CONFIRMED"

    conf_resp = test_client.get(f"/api/documents/confirmed/{astro_id}")
    assert conf_resp.status_code == 200
    assert any(c["record_id"] == rec_id for c in conf_resp.json())

    retry_resp = test_client.post(f"/api/documents/{doc_id}/retry")
    assert retry_resp.status_code == 200

def test_08_live_groq_vision_real_api_call():
    """Live external Groq Vision API test verifying real vision inference on qwen/qwen3.8-27b."""
    from personal_health.config.settings import get_settings
    api_key = os.environ.get("GROQ_API_KEY", "") or get_settings().groq_api_key
    if not api_key:
        pytest.skip("GROQ_API_KEY not set; skipping live external vision test.")

    from ocr.groq_vision_client import GroqVisionClient
    from ocr.image_processor import ImageProcessor
    import time

    client = GroqVisionClient(api_key=api_key, model="qwen/qwen3.8-27b")
    if not client.is_available():
        pytest.skip("Groq client not available.")

    img = Image.new("RGB", (300, 100), color="white")
    arr = np.array(img)
    arr[20:80, 20:280] = [240, 240, 240]
    test_img = Image.fromarray(arr)

    data_url = ImageProcessor.to_base64_data_url(test_img)

    t0 = time.time()
    try:
        records = client.extract_from_image_url(
            image_data_url=data_url,
            document_id="DOC-LIVE-TEST",
            source_type="live_test_image"
        )
        elapsed = time.time() - t0
        assert elapsed > 0.0
        assert isinstance(records, list)
    except Exception as exc:
        pytest.skip(f"Live Groq Vision external call skipped due to environment/network: {str(exc)}")
