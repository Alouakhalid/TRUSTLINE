import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "ai-engine"))
sys.path.insert(0, str(root / "ai-engine" / "agents"))

import fitz
import docx
from PIL import Image

from ocr.schemas import DocumentType, ExtractionMethod, ValidationStatus, ExtractedMedicalRecord
from ocr.groq_vision_client import GroqVisionClient, NonGroqProviderDisallowedError, GroqVisionAPIError
from ocr.extractor import MedicalDocumentExtractor
from ocr.validator import MedicalDocumentValidator
from personal_health.services.document_ingestion_service import DocumentIngestionService, DocumentSecurityError
from personal_health.services.medical_record_review_service import MedicalRecordReviewService
from personal_health.repositories.medical_document_repository import (
    MedicalDocumentRepository,
    SessionFactory,
    MedicalDocumentModel,
    PendingMedicalRecordModel
)
from personal_health.schemas.medical_document import RecordReviewRequest, ReviewStatus
from personal_health.services.health_profile_service import HealthProfileService
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.workflow.nodes import persistence_node
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
from supervisor.services.evidence_registry_service import EvidenceRegistryService
from supervisor.config.settings import get_supervisor_settings

def make_test_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), text, fontsize=11)
    b = doc.tobytes()
    doc.close()
    return b

def run_invariants_verification():
    print("=" * 80)
    print("TRUSTLINE MEDICAL DOCUMENT INTEGRATION: NINE SAFETY INVARIANTS AUDIT")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print("=" * 80)

    repo = MedicalDocumentRepository()
    mock_vision = MagicMock(spec=GroqVisionClient)
    extractor = MedicalDocumentExtractor(vision_client=mock_vision)
    ingest_svc = DocumentIngestionService(repository=repo, extractor=extractor)
    review_svc = MedicalRecordReviewService(document_repo=repo)
    profile_svc = HealthProfileService()

    ts = int(datetime.utcnow().timestamp())
    astro_id = f"AST-E2E-{ts}"

    # -------------------------------------------------------------------------
    # INVARIANT 1: Duplicate upload creates exactly one document row
    # -------------------------------------------------------------------------
    print("\n--- INVARIANT 1: Duplicate upload creates exactly one document row ---")
    pdf_bytes = make_test_pdf("Aerospace Medical Center\nGlucose: 96 mg/dL\nHemoglobin: 15.0 g/dL\nPlatelets: 240 10^3/uL")
    up1 = ingest_svc.upload_document(pdf_bytes, "panel.pdf", astro_id)
    up2 = ingest_svc.upload_document(pdf_bytes, "panel.pdf", astro_id)
    assert up1.document_id == up2.document_id, f"Document ID mismatch: {up1.document_id} vs {up2.document_id}"

    session = SessionFactory()
    try:
        persisted_docs = session.query(MedicalDocumentModel).filter_by(file_hash=up1.file_hash_sha256, astronaut_id=astro_id).all()
        assert len(persisted_docs) == 1, f"Expected exactly 1 persisted document row, found {len(persisted_docs)}"
    finally:
        session.close()

    print(f"Assertion 1.1: up1.document_id == up2.document_id ({up1.document_id}) [OK]")
    print(f"Assertion 1.2: Exactly 1 row in medical_documents for hash {up1.file_hash_sha256[:12]}... [OK]")
    print("[PASS] INVARIANT 1: Duplicate upload creates exactly one document row.")

    # -------------------------------------------------------------------------
    # INVARIANT 2: Reprocessing creates no duplicate extracted records
    # -------------------------------------------------------------------------
    print("\n--- INVARIANT 2: Reprocessing creates no duplicate extracted records ---")
    proc1 = ingest_svc.process_document(up1.document_id)
    proc2 = ingest_svc.process_document(up1.document_id, force_ocr=False)
    assert proc1.total_extracted_records == proc2.total_extracted_records, "Record count changed on reprocessing"

    session = SessionFactory()
    try:
        extracted_rows = session.query(PendingMedicalRecordModel).filter_by(document_id=up1.document_id).all()
        assert len(extracted_rows) == proc1.total_extracted_records, f"Duplicate rows in pending_medical_records: {len(extracted_rows)} vs {proc1.total_extracted_records}"
    finally:
        session.close()

    pending_records = review_svc.get_pending_records(astro_id)
    assert len(pending_records) == proc1.total_extracted_records
    print(f"Assertion 2.1: proc1.records == proc2.records ({proc1.total_extracted_records}) [OK]")
    print(f"Assertion 2.2: Exactly {len(extracted_rows)} rows in pending_medical_records (0 duplicate rows) [OK]")
    print("[PASS] INVARIANT 2: Reprocessing creates no duplicate extracted records.")

    # -------------------------------------------------------------------------
    # INVARIANT 3: Pending records remain quarantined and cannot enter confirmed findings
    # -------------------------------------------------------------------------
    print("\n--- INVARIANT 3: Pending records remain quarantined and cannot enter confirmed findings ---")
    # Verify confirmed findings is strictly empty
    confirmed_before = review_svc.get_confirmed_findings(astro_id)
    assert len(confirmed_before) == 0, f"Expected 0 confirmed findings prior to review, found {len(confirmed_before)}"

    # Run supervisor workflow with document path
    doc_entry = repo.get_document(up1.document_id)
    runner = SupervisorWorkflowRunner()
    req_pending = SupervisorRequest(
        request_id=f"REQ-PEND-{ts}",
        astronaut_id=astro_id,
        session_id=f"SES-PEND-{ts}",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Intake examination with uploaded document.",
            document_paths=[doc_entry.storage_path]
        )
    )
    res_pending = runner.run_pipeline(req_pending)
    ev_registry = res_pending.get("evidence_registry") or []

    # Inspect each pending record item in evidence registry
    pending_ev_items = [e for e in ev_registry if "EV-DOC-PENDING-" in (e.get("evidence_id") if isinstance(e, dict) else e.evidence_id)]
    assert len(pending_ev_items) > 0, "Pending records must be registered in Evidence Registry"
    for item in pending_ev_items:
        is_q = item.get("is_quarantined") if isinstance(item, dict) else item.is_quarantined
        v_status = item.get("validity_status") if isinstance(item, dict) else item.validity_status
        q_reason = item.get("quarantine_reason") if isinstance(item, dict) else item.quarantine_reason
        assert is_q is True, f"Pending item {item} is NOT quarantined"
        assert v_status == "PENDING_REVIEW", f"Unexpected validity status: {v_status}"
        assert "Pending clinical" in (q_reason or ""), f"Unexpected quarantine reason: {q_reason}"

    # Assert no EV-MED-CONFIRMED exists for pending records
    for pr in pending_records:
        rec_id = pr["record_id"]
        assert not any(f"EV-MED-CONFIRMED-{rec_id}" in (e.get("evidence_id") if isinstance(e, dict) else e.evidence_id) for e in ev_registry)

    print(f"Assertion 3.1: get_confirmed_records returned 0 findings [OK]")
    print(f"Assertion 3.2: Found {len(pending_ev_items)} pending items; all have is_quarantined=True and validity_status=PENDING_REVIEW [OK]")
    print(f"Assertion 3.3: Zero EV-MED-CONFIRMED items entered Evidence Registry [OK]")
    print("[PASS] INVARIANT 3: Pending records remain quarantined and cannot enter confirmed findings.")

    # -------------------------------------------------------------------------
    # INVARIANT 4: CONFIRM, EDIT, and REJECT persist after database reload
    # -------------------------------------------------------------------------
    print("\n--- INVARIANT 4: CONFIRM, EDIT, and REJECT persist after database reload ---")
    rec_glucose = [r for r in pending_records if "glucose" in r["test_name"].lower()][0]
    rec_hemo = [r for r in pending_records if "hemoglobin" in r["test_name"].lower()][0]
    rec_plat = [r for r in pending_records if "platelet" in r["test_name"].lower()][0]

    # Action 1: CONFIRM
    conf_res = review_svc.review_record(RecordReviewRequest(
        record_id=rec_glucose["record_id"],
        action=ReviewStatus.CONFIRMED,
        reviewer_id="SURGEON-ALPHA",
        review_notes="Laboratory reference verified."
    ))
    assert conf_res.review_status == ReviewStatus.CONFIRMED
    assert conf_res.reviewed_by == "SURGEON-ALPHA"

    # Action 2: EDIT
    edit_res = review_svc.review_record(RecordReviewRequest(
        record_id=rec_hemo["record_id"],
        action=ReviewStatus.EDITED,
        reviewer_id="SURGEON-BETA",
        review_notes="Corrected OCR value from 15.0 to 15.2",
        edited_value="15.2",
        edited_unit="g/dL"
    ))
    assert edit_res.review_status == ReviewStatus.CONFIRMED

    # Action 3: REJECT
    rej_res = review_svc.review_record(RecordReviewRequest(
        record_id=rec_plat["record_id"],
        action=ReviewStatus.REJECTED,
        reviewer_id="SURGEON-GAMMA",
        review_notes="Visual smudge on page."
    ))
    assert rej_res.review_status == ReviewStatus.REJECTED

    # Discard existing repository instance; create a brand-new instance to test persistence across DB reload
    fresh_repo = MedicalDocumentRepository()
    db_rec_g = fresh_repo.get_record(rec_glucose["record_id"])
    assert db_rec_g.review_status == "CONFIRMED"
    assert db_rec_g.reviewed_by == "SURGEON-ALPHA"
    assert db_rec_g.review_notes == "Laboratory reference verified."
    assert db_rec_g.review_timestamp is not None

    db_rec_h = fresh_repo.get_record(rec_hemo["record_id"])
    assert db_rec_h.review_status == "CONFIRMED"
    assert db_rec_h.extracted_value == "15.2"
    assert db_rec_h.normalized_value == 15.2
    assert db_rec_h.reviewed_by == "SURGEON-BETA"

    db_rec_p = fresh_repo.get_record(rec_plat["record_id"])
    assert db_rec_p.review_status == "REJECTED"
    assert db_rec_p.reviewed_by == "SURGEON-GAMMA"
    assert db_rec_p.review_notes == "Visual smudge on page."

    print(f"Assertion 4.1: CONFIRM action persisted on DB reload (reviewed_by='SURGEON-ALPHA', status='CONFIRMED') [OK]")
    print(f"Assertion 4.2: EDIT action persisted on DB reload (value='15.2', status='CONFIRMED') [OK]")
    print(f"Assertion 4.3: REJECT action persisted on DB reload (status='REJECTED') [OK]")
    print("[PASS] INVARIANT 4: CONFIRM, EDIT, and REJECT persist after database reload.")

    # -------------------------------------------------------------------------
    # INVARIANT 5: Rejected records cannot reach downstream HealthProfile events
    # -------------------------------------------------------------------------
    print("\n--- INVARIANT 5: Rejected records cannot reach downstream HealthProfile events ---")
    confirmed_after = review_svc.get_confirmed_findings(astro_id)
    confirmed_ids = [c.record_id for c in confirmed_after]
    assert rec_glucose["record_id"] in confirmed_ids, "Confirmed glucose record missing"
    assert rec_hemo["record_id"] in confirmed_ids, "Confirmed hemoglobin record missing"
    assert rec_plat["record_id"] not in confirmed_ids, "Rejected platelet record MUST NOT be in confirmed findings!"

    # Assert rejected record never entered HealthProfile events
    events = profile_svc.get_recent_health_events(astro_id, limit=50)
    for evt in events:
        assert rec_plat["record_id"] not in evt.description, "Rejected record found in HealthProfile event!"
        assert "Platelet" not in evt.description or "240" not in evt.description

    # Assert confirmed records ARE present in HealthProfile events
    assert any("Glucose" in evt.description for evt in events), "Confirmed Glucose missing from HealthProfile"
    assert any("Hemoglobin" in evt.description for evt in events), "Confirmed Hemoglobin missing from HealthProfile"

    print(f"Assertion 5.1: Rejected record {rec_plat['record_id']} excluded from get_confirmed_records() [OK]")
    print(f"Assertion 5.2: Rejected record {rec_plat['record_id']} completely absent from HealthProfile events [OK]")
    print(f"Assertion 5.3: Confirmed records verified present in HealthProfile events [OK]")
    print("[PASS] INVARIANT 5: Rejected records cannot reach downstream HealthProfile events.")

    # -------------------------------------------------------------------------
    # INVARIANT 6: UNKNOWN, missing, and mismatching astronaut identities are quarantined
    # -------------------------------------------------------------------------
    print("\n--- INVARIANT 6: UNKNOWN, missing, and mismatching astronaut identities are quarantined ---")
    # Case A: Explicit UNKNOWN astronaut identity upon upload
    up_unk = ingest_svc.upload_document(pdf_bytes, "unverified.pdf", astronaut_id="UNKNOWN")
    assert up_unk.status == "NEEDS_IDENTITY_REVIEW"
    assert up_unk.astronaut_id == "UNKNOWN"
    proc_unk = ingest_svc.process_document(up_unk.document_id)
    assert proc_unk.overall_status == "NEEDS_IDENTITY_REVIEW"
    unk_records = repo.get_records_by_document(up_unk.document_id)
    for ur in unk_records:
        assert ur.astronaut_id == "UNKNOWN"
        assert ur.astronaut_id != "AST-001"
        assert "Quarantined: unverified astronaut identity" in ur.validation_warnings_json

    # Case B: Missing astronaut identity (None, empty string, whitespace string)
    up_none = ingest_svc.upload_document(pdf_bytes, "none_doc.pdf", None)
    assert up_none.astronaut_id == "UNKNOWN"
    assert up_none.status == "NEEDS_IDENTITY_REVIEW"
    assert up_none.astronaut_id != "AST-001"

    up_empty = ingest_svc.upload_document(pdf_bytes, "empty_doc.pdf", "")
    assert up_empty.astronaut_id == "UNKNOWN"
    assert up_empty.status == "NEEDS_IDENTITY_REVIEW"
    assert up_empty.astronaut_id != "AST-001"

    up_ws = ingest_svc.upload_document(pdf_bytes, "ws_doc.pdf", "   ")
    assert up_ws.astronaut_id == "UNKNOWN"
    assert up_ws.status == "NEEDS_IDENTITY_REVIEW"
    assert up_ws.astronaut_id != "AST-001"

    # Case C: Cross-astronaut identity mismatch (record belongs to AST-OTHER-999, session belongs to AST-001)
    state_mismatch = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-INV6-MISMATCH",
        "confirmed_medical_records": [
            {
                "record_id": "REC-MISMATCH-999",
                "astronaut_id": "AST-OTHER-999",
                "test_name": "Hemoglobin",
                "numeric_value": 14.0,
                "value_string": "14.0 g/dL",
                "collection_date": "2026-02-01",
                "confirmed_by": "Flight Surgeon"
            }
        ]
    }
    registry_mismatch = EvidenceRegistryService.compile_and_audit_registry(state_mismatch)
    item_mismatch = next((i for i in registry_mismatch if i.evidence_id == "EV-MED-CONFIRMED-REC-MISMATCH-999"), None)
    assert item_mismatch is not None
    assert item_mismatch.is_quarantined is True, "Mismatched astronaut record was NOT quarantined!"
    assert item_mismatch.validity_status == "INVALID", f"Expected INVALID, got: {item_mismatch.validity_status}"
    assert "unverified or mismatching astronaut identity" in item_mismatch.quarantine_reason

    # Case D: Genuine Multi-page PDF conflict detection E2E workflow
    doc_conflict = fitz.open()
    p1 = doc_conflict.new_page(width=595, height=842)
    p1.insert_text((50, 72), "Preflight Baseline Laboratory Panel\nDate: 2026-03-01\nGlucose: 95 mg/dL (Reference: 70-99)", fontsize=11)
    p2 = doc_conflict.new_page(width=595, height=842)
    p2.insert_text((50, 72), "Post-Exercise Re-test Laboratory Panel\nDate: 2026-03-01\nGlucose: 185 mg/dL (Reference: 70-99)", fontsize=11)
    pdf_conflict_bytes = doc_conflict.tobytes()
    doc_conflict.close()

    up_conf = ingest_svc.upload_document(pdf_conflict_bytes, "multipage_conflict.pdf", "AST-CONF-001")
    proc_conf = ingest_svc.process_document(up_conf.document_id)
    assert proc_conf.total_pages_or_images == 2
    assert proc_conf.total_extracted_records >= 2

    conf_records = repo.get_records_by_document(up_conf.document_id)
    glucose_recs = [r for r in conf_records if "glucose" in r.test_name.lower()]
    assert len(glucose_recs) == 2
    r_p1 = next(r for r in glucose_recs if r.source_page_number == 1)
    r_p2 = next(r for r in glucose_recs if r.source_page_number == 2)
    assert r_p1.normalized_value == 95.0
    assert r_p2.normalized_value == 185.0
    assert r_p1.conflict_detected is True
    assert r_p2.conflict_detected is True
    assert r_p1.validation_status == "CONFLICTING_EXTRACTION"
    assert r_p2.validation_status == "CONFLICTING_EXTRACTION"

    # Conflicting findings never become confirmed automatically
    assert len(repo.get_confirmed_records("AST-CONF-001")) == 0

    print(f"Assertion 6.1: UNKNOWN, None, and empty string identities set NEEDS_IDENTITY_REVIEW and not AST-001 [OK]")
    print(f"Assertion 6.2: Mismatched identity (AST-OTHER-999 in AST-001 session) sets is_quarantined=True and validity_status=INVALID [OK]")
    print(f"Assertion 6.3: Multi-page PDF conflict detection: 2 pages retained, both traceable, conflict_detected=True, 0 auto-confirmed [OK]")
    print("[PASS] INVARIANT 6: UNKNOWN, missing, and mismatching astronaut identities are quarantined.")

    # -------------------------------------------------------------------------
    # INVARIANT 7: Historical documents cannot modify live telemetry (Numerical before/after comparison)
    # -------------------------------------------------------------------------
    print("\n--- INVARIANT 7: Historical documents cannot modify live telemetry ---")
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    # Step A: Run baseline supervisor workflow with live telemetry only
    req_live_only = SupervisorRequest(
        request_id=f"REQ-LIVE-ONLY-{ts}",
        astronaut_id="AST-001",
        session_id=f"SES-LIVE-ONLY-{ts}",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Live telemetry baseline check.",
            sensor_manifest_path=str(manifest_file)
        )
    )
    res_live_only = runner.run_pipeline(req_live_only)
    ev_live_only = res_live_only.get("evidence_registry") or []

    def get_ev_val(registry, eid):
        for e in registry:
            cur_id = e.get("evidence_id") if isinstance(e, dict) else e.evidence_id
            if cur_id == eid:
                return e.get("observed_value") if isinstance(e, dict) else e.observed_value
        return None

    hr_before = get_ev_val(ev_live_only, "EV-PHY-HR-MEAN")
    resp_before = get_ev_val(ev_live_only, "EV-PHY-RESP-RATE")
    assert hr_before is not None, "Live HR must be present in baseline run"
    assert resp_before is not None, "Live Respiration must be present in baseline run"

    # Step B: Confirm a historical baseline record for AST-001
    doc_id_ast1 = f"DOC-HIST-AST001-{ts}"
    rec_id_ast1 = f"REC-GLUC-AST001-{ts}"
    repo.save_document(
        document_id=doc_id_ast1,
        astronaut_id="AST-001",
        filename="baseline_labs_ast1.pdf",
        file_hash=f"hash_ast1_{ts}",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path="/tmp/dummy.pdf",
        processing_status="COMPLETED"
    )
    rec_ast1 = ExtractedMedicalRecord(
        record_id=rec_id_ast1,
        document_id=doc_id_ast1,
        source_type="page",
        source_page_number=1,
        source_location="page 1",
        test_name="Glucose",
        extracted_value="95 mg/dL",
        normalized_value=95.0,
        original_unit="mg/dL",
        reference_range="70-99",
        is_historical=True
    )
    repo.save_extracted_records([rec_ast1], "AST-001")
    review_svc.review_record(RecordReviewRequest(
        record_id=rec_id_ast1,
        action=ReviewStatus.CONFIRMED,
        reviewer_id="SURGEON-ALPHA",
        review_notes="Confirmed AST-001 baseline"
    ))

    # Step C: Run supervisor workflow with SAME live telemetry PLUS confirmed historical document
    req_with_hist = SupervisorRequest(
        request_id=f"REQ-WITH-HIST-{ts}",
        astronaut_id="AST-001",
        session_id=f"SES-WITH-HIST-{ts}",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Live telemetry with historical medical document.",
            sensor_manifest_path=str(manifest_file)
        )
    )
    res_with_hist = runner.run_pipeline(req_with_hist)
    ev_with_hist = res_with_hist.get("evidence_registry") or []

    hr_after = get_ev_val(ev_with_hist, "EV-PHY-HR-MEAN")
    resp_after = get_ev_val(ev_with_hist, "EV-PHY-RESP-RATE")

    # Step D: Numerical comparison before and after
    assert hr_after == hr_before, f"Live HR mutated! Before: {hr_before}, After: {hr_after}"
    assert resp_after == resp_before, f"Live Respiration mutated! Before: {resp_before}, After: {resp_after}"

    # Step E: Confirm historical tag and provenance
    confirmed_findings_ast1 = repo.get_confirmed_records("AST-001")
    finding_ast1 = next(cf for cf in confirmed_findings_ast1 if cf.record_id == rec_id_ast1)
    assert finding_ast1.is_historical is True, f"Historical finding {rec_id_ast1} not tagged is_historical=True"

    med_ev = next((e for e in ev_with_hist if (e.get("evidence_id") if isinstance(e, dict) else e.evidence_id) == f"EV-MED-CONFIRMED-{rec_id_ast1}"), None)
    assert med_ev is not None, f"Expected EV-MED-CONFIRMED-{rec_id_ast1} in evidence registry"
    assert "Historical Clinical Record" in (med_ev.get("provenance") if isinstance(med_ev, dict) else med_ev.provenance)
    assert (med_ev.get("source_agent") if isinstance(med_ev, dict) else med_ev.source_agent) == "medical_records_repository"

    print(f"Assertion 7.1: Live HR before ({hr_before:.4f}) == Live HR after ({hr_after:.4f}) [OK]")
    print(f"Assertion 7.2: Live Respiration before ({resp_before:.4f}) == Live Respiration after ({resp_after:.4f}) [OK]")
    print(f"Assertion 7.3: Historical finding tagged is_historical=True in repository [OK]")
    print(f"Assertion 7.4: Historical evidence separated under source_agent='medical_records_repository' [OK]")

    # Machine-readable telemetry immutability evidence output
    immutability_dump = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "astronaut_id": "AST-001",
        "session_before": f"SES-LIVE-ONLY-{ts}",
        "session_after": f"SES-WITH-HIST-{ts}",
        "live_metrics_before": {
            "EV-PHY-HR-MEAN": hr_before,
            "EV-PHY-RESP-RATE": resp_before
        },
        "live_metrics_after": {
            "EV-PHY-HR-MEAN": hr_after,
            "EV-PHY-RESP-RATE": resp_after
        },
        "delta": {
            "hr_delta": abs(float(hr_after) - float(hr_before)),
            "resp_delta": abs(float(resp_after) - float(resp_before))
        },
        "historical_record_added": {
            "evidence_id": f"EV-MED-CONFIRMED-{rec_id_ast1}",
            "is_historical": True,
            "source_agent": "medical_records_repository"
        },
        "immutability_verified": True
    }
    with open("scratch/telemetry_immutability_evidence.json", "w", encoding="utf-8") as f_imm:
        json.dump(immutability_dump, f_imm, indent=2)

    print("[PASS] INVARIANT 7: Historical documents cannot modify live telemetry.")

    # -------------------------------------------------------------------------
    # INVARIANT 8: Missing physiological evidence results in INSUFFICIENT_DATA
    # -------------------------------------------------------------------------
    print("\n--- INVARIANT 8: Missing physiological evidence results in INSUFFICIENT_DATA ---")
    req_missing = SupervisorRequest(
        request_id=f"REQ-MISSING-{ts}",
        astronaut_id="AST-001",
        session_id=f"SES-MISSING-{ts}",
        modality=InputModality.TEXT,
        input_data=AstronautInput(text_query="Routine query without any sensor telemetry.")
    )
    res_missing = runner.run_pipeline(req_missing)
    raw_risk = res_missing.get("overall_risk")
    risk_val = raw_risk.value if hasattr(raw_risk, "value") else str(raw_risk)
    fa_missing = res_missing.get("final_assessment") or {}
    fa_risk = fa_missing.get("overall_risk")

    assert risk_val == "INSUFFICIENT_DATA", f"Expected exactly INSUFFICIENT_DATA, got: {risk_val}"
    assert fa_risk == "INSUFFICIENT_DATA", f"Final assessment overall_risk expected exactly INSUFFICIENT_DATA, got: {fa_risk}"
    assert risk_val != "LOW", "Missing evidence must NEVER evaluate to LOW risk"
    assert risk_val != "MODERATE", "Missing evidence must NEVER evaluate to MODERATE risk without symptoms"
    assert risk_val != "HIGH", "Missing evidence must NEVER evaluate to HIGH risk without symptoms"

    print(f"Assertion 8.1: Workflow overall_risk == 'INSUFFICIENT_DATA' ({risk_val}) [OK]")
    print(f"Assertion 8.2: Final assessment overall_risk == 'INSUFFICIENT_DATA' ({fa_risk}) [OK]")
    print(f"Assertion 8.3: Rejected LOW, MODERATE, and HIGH [OK]")
    print("[PASS] INVARIANT 8: Missing physiological evidence results in INSUFFICIENT_DATA.")

    # -------------------------------------------------------------------------
    # INVARIANT 9: OCR, parsing, and persistence failures propagate truthful failure states
    # -------------------------------------------------------------------------
    print("\n--- INVARIANT 9: Failure propagation (mocked vs external failure distinction) ---")
    failing_pdf = make_test_pdf("") # empty text forces visual OCR

    # Mode 9a: Simulated Provider Timeout
    with patch.object(mock_vision, "extract_from_image_url", side_effect=Exception("Simulated APITimeoutError: Connection timed out")):
        up_to = ingest_svc.upload_document(failing_pdf, "timeout.pdf", astro_id)
        proc_to = ingest_svc.process_document(up_to.document_id)
        assert proc_to.overall_status == "FAILED"
        assert proc_to.total_extracted_records == 0
        assert any("timed out" in w.lower() or "failed" in w.lower() for w in proc_to.processing_warnings)
    print("Assertion 9a: Simulated APITimeoutError handled -> overall_status='FAILED', 0 records [OK]")

    # Mode 9b: Simulated Provider Rate Limit (429)
    with patch.object(mock_vision, "extract_from_image_url", side_effect=GroqVisionAPIError("Simulated RateLimitError: 429 Too Many Requests")):
        up_rl = ingest_svc.upload_document(failing_pdf, "ratelimit.pdf", astro_id)
        proc_rl = ingest_svc.process_document(up_rl.document_id)
        assert proc_rl.overall_status == "FAILED"
        assert proc_rl.total_extracted_records == 0
    print("Assertion 9b: Simulated 429 RateLimit handled -> overall_status='FAILED', 0 records [OK]")

    # Mode 9c: Simulated Malformed JSON Response
    with patch.object(mock_vision, "extract_from_image_url", side_effect=GroqVisionAPIError("Malformed JSON from Groq Vision response")):
        up_json = ingest_svc.upload_document(failing_pdf, "malformed.pdf", astro_id)
        proc_json = ingest_svc.process_document(up_json.document_id)
        assert proc_json.overall_status == "FAILED"
        assert proc_json.total_extracted_records == 0
    print("Assertion 9c: Simulated Malformed JSON handled -> overall_status='FAILED', 0 records [OK]")

    # Mode 9d: Simulated Database Persistence Failure
    mock_fail_state = {
        "workflow_id": "WF-FAIL-PERSIST",
        "astronaut_id": "AST-001",
        "session_id": "SES-FAIL-PERSIST",
        "workflow_status": "COMPLETED",
        "final_assessment": {
            "assessment_id": "SUP-FAIL-01",
            "astronaut_id": "AST-001",
            "session_id": "SES-FAIL-PERSIST",
            "workflow_id": "WF-FAIL-PERSIST",
            "workflow_completion_status": "COMPLETED",
            "timing_breakdown": {}
        },
        "errors": [],
        "warnings": [],
        "durations_ms": {}
    }
    with patch("supervisor.services.persistence_service.PersistenceService.save_final_assessment") as mock_save:
        mock_save.return_value = (False, None, ["Disk I/O full error"])
        res_fail_p = persistence_node(mock_fail_state)
        assert res_fail_p["workflow_status"] == "PARTIALLY_COMPLETED"
        assert any("Persistence Failure" in e for e in res_fail_p["errors"])
    print("Assertion 9d: Simulated Database Failure handled -> workflow_status='PARTIALLY_COMPLETED' [OK]")

    # Mode 9e: Empty Extraction (no extractable vitals in scanned image)
    with patch.object(mock_vision, "extract_from_image_url", return_value=[]):
        up_empty_ocr = ingest_svc.upload_document(failing_pdf, "empty_ocr.pdf", astro_id)
        proc_empty_ocr = ingest_svc.process_document(up_empty_ocr.document_id)
        assert proc_empty_ocr.total_extracted_records == 0
        assert len(repo.get_records_by_document(up_empty_ocr.document_id)) == 0
    print("Assertion 9e: Empty extraction handled truthfully -> 0 records, 0 vitals fabricated [OK]")

    print(f"Assertion 9.5: Zero fabricated clinical measurements generated across all 4 failure modes [OK]")
    print("[PASS] INVARIANT 9: OCR, parsing, and persistence failures propagate truthful failure states.")

    print("\n" + "=" * 80)
    print("ALL NINE SAFETY INVARIANTS INDEPENDENTLY REPRODUCED AND VERIFIED: PASS")
    print("=" * 80)

if __name__ == "__main__":
    run_invariants_verification()
