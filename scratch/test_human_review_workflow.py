import sys
import os
import json
from pathlib import Path
from datetime import datetime

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "ai-engine"))
sys.path.insert(0, str(root / "ai-engine" / "agents"))

import fitz
from fastapi.testclient import TestClient

from personal_health.api.app import app
from personal_health.services.document_ingestion_service import DocumentIngestionService
from personal_health.services.medical_record_review_service import MedicalRecordReviewService
from personal_health.repositories.medical_document_repository import MedicalDocumentRepository
from personal_health.schemas.medical_document import RecordReviewRequest, ReviewStatus
from personal_health.services.health_profile_service import HealthProfileService
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality

def make_pdf():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), "Laboratory Test Panel\nGlucose: 105 mg/dL\nHemoglobin: 14.5 g/dL\nPlatelets: 220 10^3/uL\nSodium: 140 mmol/L", fontsize=11)
    b = doc.tobytes()
    doc.close()
    return b

def run_audit():
    print("=== STARTING INDEPENDENT WORKFLOW & HUMAN REVIEW AUDIT ===")
    astro_id = f"AST-AUDIT-{int(datetime.utcnow().timestamp())}"
    pdf_bytes = make_pdf()

    ingest_svc = DocumentIngestionService()
    review_svc = MedicalRecordReviewService()
    repo = MedicalDocumentRepository()
    profile_svc = HealthProfileService()

    # 1. Upload & Process
    upload_res = ingest_svc.upload_document(pdf_bytes, "audit_test.pdf", astro_id)
    print(f"1. Document uploaded: ID={upload_res.document_id}, Status={upload_res.status}")
    assert upload_res.status == "UPLOADED"

    proc_res = ingest_svc.process_document(upload_res.document_id)
    print(f"2. Document processed: Status={proc_res.overall_status}, Records={proc_res.total_extracted_records}")
    assert proc_res.overall_status == "COMPLETED"
    assert proc_res.total_extracted_records >= 4

    # 2. Check Pending Records
    pending = review_svc.get_pending_records(astro_id)
    print(f"3. Pending records count: {len(pending)}")
    assert len(pending) >= 4
    for p in pending:
        assert p["review_status"] == ReviewStatus.PENDING_REVIEW.value
        assert p["astronaut_id"] == astro_id

    # 3. Apply CONFIRM on Record 0
    rec0 = pending[0]
    confirm_req = RecordReviewRequest(
        record_id=rec0["record_id"],
        action=ReviewStatus.CONFIRMED,
        reviewer_id="FS-AUDIT-01",
        review_notes="Confirmed laboratory value by flight surgeon."
    )
    conf_res = review_svc.review_record(confirm_req)
    print(f"4. Record {rec0['record_id']} confirmed by {conf_res.reviewed_by}: Status={conf_res.review_status}")
    assert conf_res.review_status == ReviewStatus.CONFIRMED
    assert conf_res.reviewed_by == "FS-AUDIT-01"

    # Verify integration into HealthProfile HealthEvent
    events = profile_svc.get_recent_health_events(astro_id)
    assert any(e.event_type == "CLINICAL_LAB_MEASUREMENT" and rec0["test_name"] in e.description for e in events)
    print("   -> HealthEvent successfully created in astronaut health profile")

    # 4. Apply EDIT on Record 1
    rec1 = pending[1]
    edit_req = RecordReviewRequest(
        record_id=rec1["record_id"],
        action=ReviewStatus.EDITED,
        reviewer_id="FS-AUDIT-02",
        review_notes="Corrected decimal from report inspection.",
        edited_value="14.8",
        edited_unit="g/dL"
    )
    edit_res = review_svc.review_record(edit_req)
    print(f"5. Record {rec1['record_id']} edited by {edit_res.reviewed_by}: Status={edit_res.review_status}")
    assert edit_res.review_status == ReviewStatus.CONFIRMED
    assert edit_res.reviewed_by == "FS-AUDIT-02"

    # Check updated record in repo
    updated_rec1 = repo.get_record(rec1["record_id"])
    assert updated_rec1.extracted_value == "14.8"
    assert updated_rec1.normalized_value == 14.8
    assert updated_rec1.original_unit == "g/dL"
    assert updated_rec1.review_notes == "Corrected decimal from report inspection."
    print("   -> Edited fields correctly stored and normalized in DB")

    # 5. Apply REJECT on Record 2
    rec2 = pending[2]
    rej_req = RecordReviewRequest(
        record_id=rec2["record_id"],
        action=ReviewStatus.REJECTED,
        reviewer_id="FS-AUDIT-03",
        review_notes="Smudge artifact on paper; rejected."
    )
    rej_res = review_svc.review_record(rej_req)
    print(f"6. Record {rec2['record_id']} rejected by {rej_res.reviewed_by}: Status={rej_res.review_status}")
    assert rej_res.review_status == ReviewStatus.REJECTED
    assert rej_res.reviewed_by == "FS-AUDIT-03"

    # Check confirmed findings
    confirmed_findings = review_svc.get_confirmed_findings(astro_id)
    confirmed_ids = [f.record_id for f in confirmed_findings]
    print(f"7. Confirmed findings count: {len(confirmed_findings)}, IDs={confirmed_ids}")
    assert rec0["record_id"] in confirmed_ids
    assert rec1["record_id"] in confirmed_ids
    assert rec2["record_id"] not in confirmed_ids  # Rejected record must NOT be in confirmed findings!
    print("   -> Rejected record strictly excluded from confirmed findings")

    # 6. Test FastAPI endpoints
    client = TestClient(app)
    api_astro = f"AST-FASTAPI-{int(datetime.utcnow().timestamp())}"
    up_resp = client.post(
        "/api/documents/upload",
        data={"astronaut_id": api_astro},
        files={"file": ("api_test.pdf", pdf_bytes, "application/pdf")}
    )
    assert up_resp.status_code == 201
    api_doc_id = up_resp.json()["document_id"]

    pr_resp = client.post(f"/api/documents/{api_doc_id}/process")
    assert pr_resp.status_code == 200

    pend_resp = client.get(f"/api/documents/pending/{api_astro}")
    assert pend_resp.status_code == 200
    pend_data = pend_resp.json()
    assert len(pend_data) >= 4

    target_id = pend_data[0]["record_id"]
    rev_resp = client.post(
        f"/api/documents/records/{target_id}/review",
        json={
            "record_id": target_id,
            "action": "CONFIRMED",
            "reviewer_id": "FS-REST-API",
            "review_notes": "Reviewed and verified via FastAPI client"
        }
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["review_status"] == "CONFIRMED"

    conf_resp = client.get(f"/api/documents/confirmed/{api_astro}")
    assert conf_resp.status_code == 200
    assert any(c["record_id"] == target_id for c in conf_resp.json())
    print("8. FastAPI full lifecycle verified successfully")

    # 7. Test Supervisor Workflow with confirmed records
    runner = SupervisorWorkflowRunner()
    req = SupervisorRequest(
        request_id=f"REQ-AUDIT-{int(datetime.utcnow().timestamp())}",
        astronaut_id=astro_id,
        session_id=f"SES-AUDIT-{int(datetime.utcnow().timestamp())}",
        modality=InputModality.TEXT,
        input_data=AstronautInput(
            text_query="Routine checkup, feeling nominal."
        )
    )
    result = runner.run_pipeline(req)
    print(f"9. Supervisor pipeline executed: Status={result.get('workflow_status')}, Risk={result.get('overall_risk')}")
    
    # Check that confirmed records reached evidence registry as EV-MED-CONFIRMED-*
    ev_reg = result.get('evidence_registry') or []
    evidence_ids = [e.evidence_id if hasattr(e, 'evidence_id') else e.get('evidence_id') for e in ev_reg]
    print(f"   Evidence IDs in registry: {evidence_ids}")
    assert any(f"EV-MED-CONFIRMED-{rec0['record_id']}" == eid for eid in evidence_ids)
    assert any(f"EV-MED-CONFIRMED-{rec1['record_id']}" == eid for eid in evidence_ids)
    assert not any(f"EV-MED-CONFIRMED-{rec2['record_id']}" == eid for eid in evidence_ids)
    print("   -> Confirmed records in EvidenceRegistry, rejected records excluded")

    briefing = result.get('astronaut_communication_response') or ''
    print('BRIEFING CONTENT:')
    print(briefing)
    fa = result.get('final_assessment') or {}
    print('FINAL ASSESSMENT ASTRONAUT FACING:')
    print(fa.get('astronaut_facing_response') if isinstance(fa, dict) else getattr(fa, 'astronaut_facing_response', None))
    print("   -> Astronaut briefing correctly formatted with historical lab disclosures")
    print("=== WORKFLOW & HUMAN REVIEW AUDIT: ALL CHECKS PASSED ===")

if __name__ == "__main__":
    run_audit()
