"""Medical document gateway: real ingestion pipeline with RBAC and demo refusal.

Uses the EXISTING ai-engine pipeline (PyMuPDF native text extraction for PDFs,
python-docx for DOCX) against a temporary edge database and upload directories.
No OCR/network provider calls occur in these tests (text PDFs only).
"""
import io

import docx
import fitz
import pytest
from fastapi.testclient import TestClient


def _pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def _docx_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    document = docx.Document()
    document.add_paragraph(text)
    document.save(buffer)
    return buffer.getvalue()


PDF_TEXT = (
    "STATION MEDICAL LABORATORY - CREW QUARTERS REPORT\n"
    "Serum Sodium: 138 mmol/L (Reference 135-145)\n"
    "Serum Potassium: 4.2 mmol/L (Reference 3.5-5.1)\n"
)


@pytest.fixture(scope="module")
def documents_environment(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("documents")
    monkey_patch_target = None
    # Configure the stack BEFORE the app serves any document request.
    from backend.api import documents as documents_module
    documents_module.configure_document_stack(
        database_url=f"sqlite:///{tmp / 'edge_documents.db'}",
        upload_dir=str(tmp / "uploads"),
        processed_docs_dir=str(tmp / "processed"),
    )
    monkeypatch_target = None  # engine reconfigured in place
    from backend.api import app as module
    module.store.configure(str(tmp / "mission.db"))
    client = TestClient(module.app)
    users = {}
    for username, role, astro in (
        ("astro1", "ASTRONAUT", "AST-001"),
        ("astro2", "ASTRONAUT", "AST-002"),
        ("medic", "MEDICAL_OFFICER", None),
    ):
        payload = {"username": username, "password": "a-very-strong-password", "role": role}
        if astro:
            payload["astronaut_id"] = astro
        client.post("/auth/register", json=payload)
        users[username] = client.post("/auth/login", json={"username": username, "password": "a-very-strong-password"}).json()["access_token"]
    yield module, client, users, tmp


def test_full_medical_workflow_upload_process_review_confirm(documents_environment):
    module, client, users, tmp = documents_environment
    astro1 = {"Authorization": f"Bearer {users['astro1']}"}
    medic = {"Authorization": f"Bearer {users['medic']}"}

    # Astronaut uploads their own lab report PDF.
    upload = client.post(
        "/documents/upload", headers=astro1,
        files={"file": ("lab_report.pdf", _pdf_bytes(PDF_TEXT), "application/pdf")},
        data={"astronaut_id": "AST-001"},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]

    # Astronaut may NOT run processing (privileged workflow).
    assert client.post(f"/documents/{document_id}/process", headers=astro1).status_code == 403
    assert client.get("/documents/pending/AST-001", headers=astro1).status_code == 403

    # Officer processes it: native PDF text extraction, no OCR needed.
    processed = client.post(f"/documents/{document_id}/process", headers=medic)
    assert processed.status_code == 200, processed.text
    body = processed.json()
    assert body["overall_status"] in {"PROCESSED", "PROCESSED_WITH_WARNINGS", "COMPLETED"}

    # Pending records await human verification.
    pending = client.get("/documents/pending/AST-001", headers=medic).json()
    assert len(pending) >= 1
    record = next(r for r in pending if r["record_id"] and "sodium" in r["test_name"].lower())
    assert record["review_status"] == "PENDING_REVIEW"

    # Astronaut cannot see the pending review queue but can see their own document.
    assert client.get("/documents/pending/AST-001", headers=astro1).status_code == 403
    doc_view = client.get(f"/documents/{document_id}", headers=astro1)
    assert doc_view.status_code == 200 and doc_view.json()["astronaut_id"] == "AST-001"

    # Client-supplied reviewer identity must be ignored -> officer confirms via token identity.
    review = client.post(
        f"/documents/records/{record['record_id']}/review", headers=medic,
        json={"record_id": record["record_id"], "action": "CONFIRMED", "reviewer_id": "FAKE-IDENTITY"},
    )
    assert review.status_code == 200, review.text
    assert review.json()["reviewed_by"] == "medic"

    # Confirmed findings visible to the owner astronaut; hidden from other astronauts.
    confirmed = client.get("/documents/confirmed/AST-001", headers=astro1).json()
    assert any("sodium" in item["test_name"].lower() for item in confirmed)
    # cross-astronaut protection (astro2 token)
    other = client.post("/auth/login", json={"username": "astro2", "password": "a-very-strong-password"}).json()["access_token"]
    astro2_headers = {"Authorization": f"Bearer {other}"}
    assert client.get("/documents/confirmed/AST-001", headers=astro2_headers).status_code == 403
    assert client.get(f"/documents/{document_id}", headers=astro2_headers).status_code == 403
    assert client.get("/documents/confirmed/AST-001", headers=medic).status_code == 200


def test_docx_upload_and_rejection_paths(documents_environment):
    module, client, users, tmp = documents_environment
    astro1 = {"Authorization": f"Bearer {users['astro1']}"}
    medic = {"Authorization": f"Bearer {users['medic']}"}
    upload = client.post(
        "/documents/upload", headers=astro1,
        files={"file": ("notes.docx", _docx_bytes("Resting heart rate documented: 62 bpm"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"astronaut_id": "AST-001"},
    )
    assert upload.status_code == 201
    document_id = upload.json()["document_id"]
    processed = client.post(f"/documents/{document_id}/process", headers=medic)
    assert processed.status_code == 200
    # unknown document -> 404
    assert client.get("/documents/DOC-UNKNOWN", headers=astro1).status_code == 404
    assert client.post("/documents/DOC-UNKNOWN/process", headers=medic).status_code == 404


def test_demo_document_operations_are_refused_to_protect_real_records(documents_environment):
    module, client, users, tmp = documents_environment
    astro1 = {"Authorization": f"Bearer {users['astro1']}"}
    demo = {**astro1, "X-Trustline-Mode": "demo"}
    response = client.post(
        "/documents/upload", headers=demo,
        files={"file": ("demo.pdf", _pdf_bytes("demo"), "application/pdf")},
        data={"astronaut_id": "AST-001"},
    )
    assert response.status_code == 403
    assert "Demo-mode medical document operations are disabled" in response.json()["detail"]


def test_astronaut_cannot_upload_for_someone_else(documents_environment):
    module, client, users, tmp = documents_environment
    astro1 = {"Authorization": f"Bearer {users['astro1']}"}
    response = client.post(
        "/documents/upload", headers=astro1,
        files={"file": ("other.pdf", _pdf_bytes("other crew"), "application/pdf")},
        data={"astronaut_id": "AST-002"},
    )
    assert response.status_code == 403
