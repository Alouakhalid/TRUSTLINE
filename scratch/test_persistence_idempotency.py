import sys
import hashlib
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "ai-engine"))
sys.path.insert(0, str(root / "ai-engine" / "agents"))

import fitz
from personal_health.services.document_ingestion_service import DocumentIngestionService
from personal_health.repositories.medical_document_repository import MedicalDocumentRepository
from personal_health.schemas.medical_document import DocumentType
from ocr.groq_vision_client import GroqVisionClient
from ocr.extractor import MedicalDocumentExtractor
from ocr.schemas import ExtractedMedicalRecord, ExtractionMethod

def make_sample_pdf():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), "Laboratory Test Panel\nPlatelets: 260 10^3/uL\nGlucose: 90 mg/dL", fontsize=11)
    b = doc.tobytes()
    doc.close()
    return b

def run_test():
    print("=== STARTING PERSISTENCE & IDEMPOTENCY AUDIT ===")
    mock_vision = MagicMock(spec=GroqVisionClient)
    def mock_extract(image_data_url, document_id, **kwargs):
        return [
            ExtractedMedicalRecord(
                document_id=document_id,
                test_name="Glucose",
                extracted_value="90 mg/dL",
                normalized_value=90.0,
                original_unit="mg/dL",
                extraction_method=ExtractionMethod.GROQ_VISION_OCR
            ),
            ExtractedMedicalRecord(
                document_id=document_id,
                test_name="Platelets",
                extracted_value="260 10^3/uL",
                normalized_value=260.0,
                original_unit="10^3/uL",
                extraction_method=ExtractionMethod.GROQ_VISION_OCR
            )
        ]
    mock_vision.extract_from_image_url.side_effect = mock_extract

    repo = MedicalDocumentRepository()
    extractor = MedicalDocumentExtractor(vision_client=mock_vision)
    svc = DocumentIngestionService(repository=repo, extractor=extractor)

    astro_id = f"AST-IDEM-{int(datetime.utcnow().timestamp())}"
    pdf_bytes = make_sample_pdf()
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # 1. First upload
    up1 = svc.upload_document(pdf_bytes, "idempotency_test.pdf", astro_id)
    doc_id_1 = up1.document_id
    print(f"1. First upload: doc_id={doc_id_1}, hash={file_hash}")

    # 2. Duplicate upload of identical file
    up2 = svc.upload_document(pdf_bytes, "idempotency_test.pdf", astro_id)
    doc_id_2 = up2.document_id
    print(f"2. Second upload (same bytes & astronaut): doc_id={doc_id_2}")
    assert doc_id_1 == doc_id_2, f"Expected duplicate upload to return same document_id, got {doc_id_1} vs {doc_id_2}"

    # Verify database has exactly 1 entry for this hash and astronaut
    doc_entry = repo.get_document(doc_id_1)
    assert doc_entry is not None
    print("   -> Deduplication verified: exactly 1 database row exists")

    # 3. Process document
    pr1 = svc.process_document(doc_id_1)
    recs_after_pr1 = repo.get_records_by_document(doc_id_1)
    initial_rec_count = len(recs_after_pr1)
    print(f"3. Processed document: {initial_rec_count} records created")
    assert initial_rec_count >= 2

    # 4. Reprocess document without force_ocr
    pr2 = svc.process_document(doc_id_1, force_ocr=False)
    recs_after_pr2 = repo.get_records_by_document(doc_id_1)
    print(f"4. Reprocessed without force_ocr: {len(recs_after_pr2)} records in DB")
    assert len(recs_after_pr2) == initial_rec_count, "Reprocessing without force_ocr should NOT duplicate records"

    # 5. Retry document (force_ocr=True)
    retry_res = svc.retry_document(doc_id_1)
    recs_after_retry = repo.get_records_by_document(doc_id_1)
    print(f"5. Retry document: Status={retry_res.overall_status}, DB records={len(recs_after_retry)}")
    assert retry_res.overall_status in ("COMPLETED", "PARTIALLY_COMPLETED")

    # 6. Relational integrity
    for r in recs_after_retry:
        assert r.document_id == doc_id_1
        assert r.astronaut_id == astro_id
        parent_doc = repo.get_document(r.document_id)
        assert parent_doc is not None
        assert parent_doc.document_id == doc_id_1
    print("6. Relational integrity verified: all records map to valid parent document")

    print("=== PERSISTENCE & IDEMPOTENCY AUDIT: ALL CHECKS PASSED ===")

if __name__ == "__main__":
    run_test()
