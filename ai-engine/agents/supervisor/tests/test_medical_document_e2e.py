"""End-to-end medical document integration test suite for TRUSTLINE Supervisor Agent."""
import io
import sys
import uuid
from pathlib import Path

cur_file = Path(__file__).resolve()
engine_path = cur_file.parents[3]
agents_path = engine_path / "agents"
for p in (engine_path, agents_path):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import fitz
import docx
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from ocr.schemas import (
    DocumentType,
    ExtractionMethod,
    ValidationStatus,
    ExtractedMedicalRecord,
    DocumentProcessingResult,
    PageProcessingMetadata
)
from ocr.groq_vision_client import GroqVisionClient, GroqVisionAPIError
from ocr.validator import MedicalDocumentValidator
from personal_health.services.document_ingestion_service import DocumentIngestionService, DocumentSecurityError
from personal_health.services.medical_record_review_service import MedicalRecordReviewService
from personal_health.repositories.medical_document_repository import (
    MedicalDocumentRepository,
    MedicalDocumentModel,
    PendingMedicalRecordModel
)
from personal_health.schemas.medical_document import (
    ReviewStatus,
    ConfirmedMedicalFinding,
    RecordReviewRequest
)
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.workflow.nodes import persistence_node
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
from supervisor.services.evidence_registry_service import EvidenceRegistryService
from supervisor.schemas.assessment import EvidenceRegistryItem

def make_test_pdf(text: str = "", add_table: bool = False, add_image: bool = False, pages: int = 1) -> bytes:
    """Create in-memory PDF fixture with optional text, tables, and images."""
    doc = fitz.open()
    for idx in range(pages):
        page = doc.new_page(width=595, height=842)
        if text:
            page.insert_text((50, 72), f"{text} (Page {idx + 1})", fontsize=11)
        if add_table:
            page.insert_text((50, 150), "Test Name | Value | Unit | Reference Range\nGlucose | 95 | mg/dL | 70-99\nHemoglobin | 14.8 | g/dL | 13.5-17.5", fontsize=10)
        if add_image:
            img = Image.new("RGB", (100, 100), color=(180, 40, 40))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            rect = fitz.Rect(50, 300, 200, 450)
            page.insert_image(rect, stream=buf.getvalue())
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def make_test_docx(paragraphs=None, tables=None) -> bytes:
    """Create in-memory DOCX fixture with paragraphs and tables."""
    doc = docx.Document()
    if paragraphs:
        for p in paragraphs:
            doc.add_paragraph(p)
    if tables:
        for t in tables:
            table = doc.add_table(rows=len(t), cols=len(t[0]))
            for r_idx, row in enumerate(t):
                for c_idx, val in enumerate(row):
                    table.cell(r_idx, c_idx).text = str(val)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def test_01_native_pdf_extraction_without_unnecessary_ocr(tmp_path):
    """TEST 01: Verify native text PDF is extracted directly without calling Groq Vision OCR."""
    pdf_bytes = make_test_pdf(
        text="Clinical Laboratory Panel\nHemoglobin: 15.2 g/dL\nPlatelets: 250 10^3/uL",
        add_table=False,
        add_image=False,
        pages=1
    )
    doc_path = tmp_path / "native_report.pdf"
    doc_path.write_bytes(pdf_bytes)

    mock_vision = MagicMock(spec=GroqVisionClient)
    from ocr.extractor import MedicalDocumentExtractor
    extractor = MedicalDocumentExtractor(vision_client=mock_vision)
    repo = MedicalDocumentRepository()
    service = DocumentIngestionService(repository=repo, extractor=extractor)

    upload_res = service.upload_document(pdf_bytes, "native_report.pdf", "AST-TEST-001")
    proc_res = service.process_document(upload_res.document_id)

    assert proc_res.overall_status in ("COMPLETED", "PARTIALLY_COMPLETED")
    assert proc_res.document_type == DocumentType.PDF
    assert proc_res.total_extracted_records >= 1
    mock_vision.extract_from_image_url.assert_not_called()

def test_02_scanned_pdf_groq_vision_ocr(tmp_path):
    """TEST 02: Verify scanned image PDF triggers Groq Vision OCR extraction."""
    pdf_bytes = make_test_pdf(text="", add_image=True, pages=1)
    doc_path = tmp_path / "scanned_report.pdf"
    doc_path.write_bytes(pdf_bytes)

    mock_vision = MagicMock(spec=GroqVisionClient)
    def mock_extract(image_data_url, document_id, **kwargs):
        return [
            ExtractedMedicalRecord(
                document_id=document_id,
                source_type="scanned_page",
                source_page_number=1,
                test_name="Glucose",
                extracted_value="92 mg/dL",
                normalized_value=92.0,
                original_unit="mg/dL",
                extraction_method=ExtractionMethod.GROQ_VISION_OCR
            ),
            ExtractedMedicalRecord(
                document_id=document_id,
                source_type="scanned_page",
                source_page_number=1,
                test_name="Hemoglobin",
                extracted_value="14.1 g/dL",
                normalized_value=14.1,
                original_unit="g/dL",
                extraction_method=ExtractionMethod.GROQ_VISION_OCR
            )
        ]
    mock_vision.extract_from_image_url.side_effect = mock_extract

    from ocr.extractor import MedicalDocumentExtractor
    extractor = MedicalDocumentExtractor(vision_client=mock_vision)
    repo = MedicalDocumentRepository()
    service = DocumentIngestionService(repository=repo, extractor=extractor)

    upload_res = service.upload_document(pdf_bytes, "scanned_report.pdf", "AST-TEST-002")
    proc_res = service.process_document(upload_res.document_id)

    assert proc_res.document_type == DocumentType.PDF
    assert mock_vision.extract_from_image_url.called
    records = repo.get_records_by_document(upload_res.document_id)
    assert len(records) >= 1
    test_names = [r.test_name.lower() for r in records]
    assert any("hemoglobin" in t or "glucose" in t for t in test_names)

def test_03_mixed_pdf_hybrid_extraction(tmp_path):
    """TEST 03: Verify mixed PDF extracts text page natively and scanned page via OCR."""
    unique_run_id = uuid.uuid4().hex[:8]
    doc = fitz.open()
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 72), f"Laboratory Panel Page 1 {unique_run_id}\nHemoglobin: 15.5 g/dL", fontsize=12)

    page2 = doc.new_page(width=595, height=842)
    img = Image.new("RGB", (100, 100), color=(10, 100, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    page2.insert_image(fitz.Rect(50, 50, 250, 250), stream=buf.getvalue())
    mixed_bytes = doc.tobytes()
    doc.close()

    mock_vision = MagicMock(spec=GroqVisionClient)
    def mock_extract_p2(image_data_url, document_id, **kwargs):
        return [
            ExtractedMedicalRecord(
                document_id=document_id,
                source_type="scanned_page",
                source_page_number=2,
                test_name="Glucose",
                extracted_value="104 mg/dL",
                normalized_value=104.0,
                original_unit="mg/dL",
                extraction_method=ExtractionMethod.GROQ_VISION_OCR
            )
        ]
    mock_vision.extract_from_image_url.side_effect = mock_extract_p2

    from ocr.extractor import MedicalDocumentExtractor
    extractor = MedicalDocumentExtractor(vision_client=mock_vision)
    repo = MedicalDocumentRepository()
    service = DocumentIngestionService(repository=repo, extractor=extractor)

    upload_res = service.upload_document(mixed_bytes, "mixed_report.pdf", "AST-TEST-003")
    proc_res = service.process_document(upload_res.document_id)

    assert proc_res.document_type == DocumentType.PDF
    assert proc_res.total_pages_or_images == 2
    assert mock_vision.extract_from_image_url.call_count == 1
    records = repo.get_records_by_document(upload_res.document_id)
    test_names = [r.test_name.lower() for r in records]
    assert any("hemoglobin" in t for t in test_names)
    assert any("glucose" in t for t in test_names)

def test_04_docx_paragraphs_and_tables_extraction(tmp_path):
    """TEST 04: Verify DOCX extracts paragraphs and structured tables with coordinates."""
    table_data = [
        ["Test Name", "Value", "Unit", "Reference Interval"],
        ["Glucose", "95", "mg/dL", "70-99"],
        ["Hematocrit", "45.0", "%", "38.0-50.0"]
    ]
    docx_bytes = make_test_docx(
        paragraphs=["Annual Flight Surgeon Medical Summary", "Routine Mission Periodic Examination."],
        tables=[table_data]
    )

    from ocr.extractor import MedicalDocumentExtractor
    extractor = MedicalDocumentExtractor()
    repo = MedicalDocumentRepository()
    service = DocumentIngestionService(repository=repo, extractor=extractor)

    upload_res = service.upload_document(docx_bytes, "clinical_summary.docx", "AST-TEST-004")
    proc_res = service.process_document(upload_res.document_id)

    assert proc_res.document_type == DocumentType.DOCX
    assert proc_res.total_extracted_records >= 2
    records = repo.get_records_by_document(upload_res.document_id)
    table_records = [r for r in records if r.source_type == "table"]
    assert len(table_records) >= 2
    for tr in table_records:
        assert "row" in tr.source_location.lower()

def test_05_historical_medical_information_preserves_telemetry(tmp_path):
    """TEST 05: Verify historical lab values reach PHA and RA without overwriting sensor telemetry."""
    repo = MedicalDocumentRepository()
    doc_id = f"DOC-HIST-{tmp_path.name[:6].upper()}"
    rec_id = f"REC-GLUC-{tmp_path.name[:6].upper()}"

    repo.save_document(
        document_id=doc_id,
        astronaut_id="AST-001",
        filename="baseline_labs.pdf",
        file_hash="dummyhash12345",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path=str(tmp_path / "dummy.pdf"),
        processing_status="COMPLETED"
    )

    extracted = ExtractedMedicalRecord(
        record_id=rec_id,
        document_id=doc_id,
        source_type="page",
        source_page_number=1,
        source_location="page 1",
        test_name="Glucose",
        extracted_value="95 mg/dL",
        normalized_value=95.0,
        original_unit="mg/dL",
        normalized_unit="mg/dl",
        reference_range="70-99",
        collection_date="2026-01-15",
        extraction_method=ExtractionMethod.NATIVE_TEXT,
        is_historical=True
    )
    repo.save_extracted_records([extracted], "AST-001")

    review_svc = MedicalRecordReviewService(document_repo=repo)
    review_svc.review_record(
        RecordReviewRequest(
            record_id=rec_id,
            action=ReviewStatus.CONFIRMED,
            reviewer_id="FLIGHT_SURGEON_01",
            review_notes="Verified baseline"
        )
    )

    confirmed_findings = repo.get_confirmed_records("AST-001")
    assert any(cf.record_id == rec_id for cf in confirmed_findings)
    finding = next(cf for cf in confirmed_findings if cf.record_id == rec_id)
    assert finding.is_historical is True

    from supervisor.config.settings import get_supervisor_settings
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-HIST-TEST-001",
        astronaut_id="AST-001",
        session_id="SESSION-HIST-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Flight Surgeon historical records integration audit.",
            sensor_manifest_path=str(manifest_file)
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    registry = result.get("evidence_registry") or []
    med_ev = next((e for e in registry if e.get("evidence_id") == f"EV-MED-CONFIRMED-{rec_id}"), None)
    assert med_ev is not None
    assert med_ev["observed_value"] == 95.0

    hr_ev = next((e for e in registry if e.get("evidence_id") == "EV-PHY-HR-MEAN"), None)
    assert hr_ev is not None
    assert hr_ev["observed_value"] != 95.0

    resp_text = result.get("final_response") or ""
    assert "Confirmed Historical Medical Records" in resp_text
    assert "baseline clinical history and not current real-time telemetry" in resp_text

def test_06_evidence_rejection_missing_or_malformed_provenance():
    """TEST 06: Verify evidence item with missing or malformed provenance is strictly quarantined."""
    state = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "injected_evidence": [
            {
                "evidence_id": "EV-INJ-MALFORMED",
                "source_agent": "UNKNOWN",
                "domain": "CARDIOVASCULAR",
                "metric_name": "heart_rate_mean",
                "observed_value": 75.0,
                "provenance": ""
            }
        ]
    }
    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    item = next((i for i in registry if i.evidence_id == "EV-INJ-MALFORMED"), None)
    assert item is not None
    assert item.is_quarantined is True
    assert item.validity_status == "INVALID"
    assert "Provenance audit failure" in item.quarantine_reason

def test_07_duplicate_upload_idempotency_prevents_duplicate_rows(tmp_path):
    """TEST 07: Verify repeated upload of identical file hash returns existing document without duplicate rows."""
    pdf_bytes = make_test_pdf("Standard Laboratory Results Hemoglobin: 14.5 g/dL")
    repo = MedicalDocumentRepository()
    service = DocumentIngestionService(repository=repo)

    upload_1 = service.upload_document(pdf_bytes, "unique_panel.pdf", "AST-TEST-007")
    proc_1 = service.process_document(upload_1.document_id)

    records_before = repo.get_records_by_document(upload_1.document_id)
    count_before = len(records_before)

    upload_2 = service.upload_document(pdf_bytes, "unique_panel.pdf", "AST-TEST-007")
    assert upload_2.document_id == upload_1.document_id

    proc_2 = service.process_document(upload_2.document_id)
    records_after = repo.get_records_by_document(upload_2.document_id)
    assert len(records_after) == count_before

def test_08_ocr_failure_propagates_truthfully_without_fabrication(tmp_path):
    """TEST 08: Verify OCR service failure propagates as FAILED and never fabricates vitals."""
    pdf_bytes = make_test_pdf(text="", add_image=True)

    mock_vision = MagicMock(spec=GroqVisionClient)
    mock_vision.extract_from_image_url.side_effect = GroqVisionAPIError("Simulated Groq Vision API Rate Limit 429")

    from ocr.extractor import MedicalDocumentExtractor
    extractor = MedicalDocumentExtractor(vision_client=mock_vision)
    repo = MedicalDocumentRepository()
    service = DocumentIngestionService(repository=repo, extractor=extractor)

    upload_res = service.upload_document(pdf_bytes, "failing_scan.pdf", "AST-TEST-008")
    proc_res = service.process_document(upload_res.document_id)

    assert proc_res.total_extracted_records == 0
    assert any("Groq Vision OCR failed" in w for w in proc_res.processing_warnings)

    extracted_records = repo.get_records_by_document(upload_res.document_id)
    assert len(extracted_records) == 0

def test_09_unknown_identity_quarantined_and_requires_review(tmp_path):
    """TEST 09: Verify explicit UNKNOWN, missing (None, empty), and cross-astronaut identities are quarantined."""
    repo = MedicalDocumentRepository()
    service = DocumentIngestionService(repository=repo)
    pdf_bytes = make_test_pdf("Unidentified Clinical Report\nHemoglobin: 13.9 g/dL")

    upload_unknown = service.upload_document(pdf_bytes, "unknown_doc.pdf", "UNKNOWN")
    assert upload_unknown.astronaut_id == "UNKNOWN"
    assert upload_unknown.status == "NEEDS_IDENTITY_REVIEW"
    proc_unknown = service.process_document(upload_unknown.document_id)
    assert proc_unknown.overall_status == "NEEDS_IDENTITY_REVIEW"
    records_unk = repo.get_records_by_document(upload_unknown.document_id)
    assert len(records_unk) >= 1
    for r in records_unk:
        assert r.astronaut_id == "UNKNOWN"
        assert r.astronaut_id != "AST-001"
        assert r.validation_status in ("NEEDS_REVIEW", "FLAGGED")
        assert "Quarantined: unverified astronaut identity" in r.validation_warnings_json

    upload_none = service.upload_document(pdf_bytes, "none_doc.pdf", None)
    assert upload_none.astronaut_id == "UNKNOWN"
    assert upload_none.status == "NEEDS_IDENTITY_REVIEW"
    assert upload_none.astronaut_id != "AST-001"

    upload_empty = service.upload_document(pdf_bytes, "empty_doc.pdf", "")
    assert upload_empty.astronaut_id == "UNKNOWN"
    assert upload_empty.status == "NEEDS_IDENTITY_REVIEW"
    assert upload_empty.astronaut_id != "AST-001"

    upload_ws = service.upload_document(pdf_bytes, "ws_doc.pdf", "   ")
    assert upload_ws.astronaut_id == "UNKNOWN"
    assert upload_ws.status == "NEEDS_IDENTITY_REVIEW"
    assert upload_ws.astronaut_id != "AST-001"

    pdf_beta = make_test_pdf("Clinical Report for Crew Member Beta\nHemoglobin: 16.1 g/dL")
    upload_beta = service.upload_document(pdf_beta, "beta_panel.pdf", "AST-BETA-777")
    proc_beta = service.process_document(upload_beta.document_id)
    assert proc_beta.astronaut_id == "AST-BETA-777"
    records_beta = repo.get_records_by_document(upload_beta.document_id)
    assert len(records_beta) >= 1
    assert records_beta[0].astronaut_id == "AST-BETA-777"

    review_svc = MedicalRecordReviewService(document_repo=repo)
    review_svc.review_record(RecordReviewRequest(
        record_id=records_beta[0].record_id,
        action=ReviewStatus.CONFIRMED,
        reviewer_id="SURGEON-TEST",
        review_notes="Confirmed for Beta"
    ))

    ast_001_confirmed = repo.get_confirmed_records("AST-001")
    assert not any(cr.record_id == records_beta[0].record_id for cr in ast_001_confirmed)

    state_cross = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-CROSS-TEST",
        "confirmed_medical_records": [
            {
                "record_id": records_beta[0].record_id,
                "astronaut_id": "AST-BETA-777",
                "test_name": records_beta[0].test_name,
                "numeric_value": records_beta[0].normalized_value,
                "value_string": records_beta[0].extracted_value,
                "collection_date": "2026-02-01",
                "confirmed_by": "SURGEON-TEST"
            }
        ]
    }
    registry_cross = EvidenceRegistryService.compile_and_audit_registry(state_cross)
    item_cross = next((i for i in registry_cross if i.evidence_id == f"EV-MED-CONFIRMED-{records_beta[0].record_id}"), None)
    assert item_cross is not None
    assert item_cross.is_quarantined is True
    assert item_cross.validity_status == "INVALID"
    assert "unverified or mismatching astronaut identity" in item_cross.quarantine_reason

def test_10_conflicting_measurements_preserved_and_flagged(tmp_path):
    """TEST 10: Verify conflicting extractions across pages of a real PDF are detected, preserved, and quarantined."""
    doc = fitz.open()
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((50, 72), "Preflight Baseline Laboratory Panel\nDate: 2026-03-01\nGlucose: 95 mg/dL (Reference: 70-99)", fontsize=11)
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((50, 72), "Post-Exercise Re-test Laboratory Panel\nDate: 2026-03-01\nGlucose: 185 mg/dL (Reference: 70-99)", fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()

    doc_file = tmp_path / "multipage_conflict.pdf"
    doc_file.write_bytes(pdf_bytes)

    repo = MedicalDocumentRepository()
    service = DocumentIngestionService(repository=repo)
    upload_res = service.upload_document(pdf_bytes, "multipage_conflict.pdf", "AST-CONF-001")
    assert upload_res.document_id is not None

    proc_res = service.process_document(upload_res.document_id)
    assert proc_res.total_pages_or_images == 2
    assert proc_res.total_extracted_records >= 2

    records = repo.get_records_by_document(upload_res.document_id)
    glucose_records = [r for r in records if "glucose" in r.test_name.lower()]
    assert len(glucose_records) == 2

    rec1 = next(r for r in glucose_records if r.source_page_number == 1)
    rec2 = next(r for r in glucose_records if r.source_page_number == 2)
    assert rec1.normalized_value == 95.0
    assert rec2.normalized_value == 185.0
    assert rec1.source_page_number == 1
    assert rec2.source_page_number == 2
    assert rec1.conflict_detected is True
    assert rec2.conflict_detected is True
    assert rec1.validation_status == "CONFLICTING_EXTRACTION"
    assert rec2.validation_status == "CONFLICTING_EXTRACTION"

    confirmed_findings = repo.get_confirmed_records("AST-CONF-001")
    assert len(confirmed_findings) == 0

    fresh_repo = MedicalDocumentRepository()
    reloaded_records = fresh_repo.get_records_by_document(upload_res.document_id)
    reloaded_glucose = [r for r in reloaded_records if "glucose" in r.test_name.lower()]
    assert len(reloaded_glucose) == 2
    assert all(r.conflict_detected is True for r in reloaded_glucose)

    state = {
        "astronaut_id": "AST-CONF-001",
        "session_id": "SESSION-CONF-001",
        "pending_medical_records": [
            {
                "record_id": r.record_id,
                "document_id": r.document_id,
                "test_name": r.test_name,
                "extracted_value": r.extracted_value,
                "normalized_value": r.normalized_value,
                "validation_status": r.validation_status
            }
            for r in reloaded_glucose
        ]
    }
    registry = EvidenceRegistryService.compile_and_audit_registry(state)
    for r in reloaded_glucose:
        ev = next((e for e in registry if e.evidence_id == f"EV-DOC-PENDING-{r.record_id}"), None)
        assert ev is not None
        assert ev.is_quarantined is True
        assert ev.validity_status == "PENDING_REVIEW"

def test_11_pha_failure_reports_assessment_incomplete():
    """TEST 11: Verify that when PHA fails, workflow reports ASSESSMENT_INCOMPLETE without pretending success."""
    from supervisor.config.settings import get_supervisor_settings
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-FAIL-PHA-001",
        astronaut_id="AST-001",
        session_id="SESSION-FAIL-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Testing upstream PHA crash handling.",
            sensor_manifest_path=str(manifest_file)
        )
    )

    with patch("supervisor.adapters.personal_health_adapter.PersonalHealthAdapter.run") as mock_run:
        mock_run.side_effect = RuntimeError("Fatal GPU Out of Memory in FeatureExtractionService")
        runner = SupervisorWorkflowRunner()
        result = runner.run_pipeline(request=request)

    assert result.get("workflow_status") == "PARTIALLY_COMPLETED"
    assert result.get("escalation_state") == "ASSESSMENT_INCOMPLETE"
    assert result.get("overall_risk") == "INSUFFICIENT_DATA"

    resp = result.get("final_response") or ""
    assert "Health Assessment Incomplete" in resp

def test_12_persistence_failure_reports_failure_truthfully():
    """TEST 12: Verify database persistence failure reports failure truthfully without crashing the process."""
    mock_state = {
        "workflow_id": "WF-PERSIST-FAIL",
        "astronaut_id": "AST-001",
        "session_id": "SESSION-PERSIST-FAIL",
        "workflow_status": "COMPLETED",
        "final_assessment": {
            "assessment_id": "SUP-TEST-FAIL",
            "astronaut_id": "AST-001",
            "session_id": "SESSION-PERSIST-FAIL",
            "workflow_id": "WF-PERSIST-FAIL",
            "workflow_completion_status": "COMPLETED",
            "timing_breakdown": {}
        },
        "errors": [],
        "warnings": [],
        "durations_ms": {}
    }

    with patch("supervisor.services.persistence_service.PersistenceService.save_final_assessment") as mock_save:
        mock_save.return_value = (False, None, ["Simulated SQLite I/O disk quota exceeded"])
        res = persistence_node(mock_state)

    assert res["workflow_status"] == "PARTIALLY_COMPLETED"
    assert any("Persistence Failure" in e for e in res["errors"])
    assert any("Simulated SQLite I/O disk quota exceeded" in w for w in res["warnings"])

def test_13_complete_workflow_upload_to_persistence(tmp_path):
    """TEST 13: Execute complete end-to-end integration: upload -> extract -> review -> supervisor -> database."""
    pdf_bytes = make_test_pdf(
        text="Annual Astronaut Baseline Laboratory Examination\nHemoglobin: 15.4 g/dL\nPlatelets: 240 10^3/uL",
        add_table=True,
        pages=1
    )
    doc_file = tmp_path / "astronaut_baseline_panel.pdf"
    doc_file.write_bytes(pdf_bytes)

    repo = MedicalDocumentRepository()
    service = DocumentIngestionService(repository=repo)
    upload_res = service.upload_document(pdf_bytes, "astronaut_baseline_panel.pdf", "AST-001")
    proc_res = service.process_document(upload_res.document_id)
    assert proc_res.overall_status in ("COMPLETED", "PARTIALLY_COMPLETED")

    records = repo.get_records_by_document(upload_res.document_id)
    assert len(records) >= 1
    rec = records[0]

    review_svc = MedicalRecordReviewService(document_repo=repo)
    review_svc.review_record(
        RecordReviewRequest(
            record_id=rec.record_id,
            action=ReviewStatus.CONFIRMED,
            reviewer_id="FLIGHT_SURGEON_CHIEF",
            review_notes="Approved for baseline comparison."
        )
    )

    from supervisor.config.settings import get_supervisor_settings
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-E2E-MED-013",
        astronaut_id="AST-001",
        session_id="SESSION-E2E-MED-013",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Routine medical evaluation with uploaded baseline laboratory document.",
            sensor_manifest_path=str(manifest_file),
            document_paths=[str(doc_file)]
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    assert result.get("workflow_status") in ("COMPLETED", "PARTIALLY_COMPLETED")
    assert result.get("astronaut_id") == "AST-001"
    assert "personal_health_agent" in result.get("agent_execution_status", {})
    assert "risk_assessment_agent" in result.get("agent_execution_status", {})

    registry = result.get("evidence_registry") or []
    confirmed_item = next((e for e in registry if e.get("evidence_id") == f"EV-MED-CONFIRMED-{rec.record_id}"), None)
    assert confirmed_item is not None
    assert confirmed_item["validity_status"] == "VALID"
    assert confirmed_item["is_quarantined"] is False

    final_resp = result.get("final_response") or ""
    assert "Confirmed Historical Medical Records" in final_resp

    final_assessment = result.get("final_assessment")
    assert final_assessment is not None
    assert final_assessment["astronaut_id"] == "AST-001"
