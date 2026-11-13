"""Comprehensive Eligibility and Security Tests for TRUSTLINE Medical RAG (Phase 4A).

Verifies P01 review lifecycle gating, astronaut identity isolation, cross-astronaut defenses,
provenance preservation, and duplicate handling.
"""
import uuid
import pytest
from datetime import datetime

from personal_health.rag.service import MedicalKnowledgeRAGService
from personal_health.rag.schemas import (
    RetrievalQuery,
    RAGRetrievalStatus,
    TrustStatus,
    EvidenceType
)
from personal_health.repositories.medical_document_repository import (
    MedicalDocumentRepository,
    ReviewStatus
)
from personal_health.schemas.medical_document import (
    ExtractedMedicalRecord,
    ValidationStatus,
    ExtractionMethod
)

@pytest.fixture(scope="module")
def rag_service():
    return MedicalKnowledgeRAGService()

@pytest.fixture(scope="module")
def doc_repo():
    return MedicalDocumentRepository()

def test_01_confirmed_document_retrieval(rag_service, doc_repo):
    """Test 4A.1: Confirmed P01 medical records are retrievable with correct clinical provenance."""
    astro_id = f"AST-CONF-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-CONF-{uuid.uuid4().hex[:6].upper()}"
    rec_id = f"REC-CONF-{uuid.uuid4().hex[:6].upper()}"

    doc_repo.save_document(
        document_id=doc_id,
        astronaut_id=astro_id,
        filename="confirmed_lab.pdf",
        file_hash=f"hash_{doc_id}",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path=f"/tmp/{doc_id}.pdf"
    )

    rec = ExtractedMedicalRecord(
        record_id=rec_id,
        document_id=doc_id,
        source_type="page",
        source_page_number=1,
        source_location="Page 1 Table 1",
        test_name="Serum Hemoglobin",
        extracted_value="15.8",
        normalized_value=15.8,
        original_unit="g/dL",
        normalized_unit="g/dl",
        reference_range="13.5 - 17.5 g/dL",
        collection_date="2026-10-15",
        laboratory_name="Spaceflight Core Biochemistry Lab",
        extraction_confidence=0.99,
        validation_status=ValidationStatus.VALIDATED,
        extraction_method=ExtractionMethod.NATIVE_TEXT,
        source_text="Hemoglobin: 15.8 g/dL (Normal Range: 13.5 - 17.5 g/dL)"
    )
    doc_repo.save_extracted_records([rec], astronaut_id=astro_id)

    # Confirm the record via Flight Surgeon review lifecycle
    doc_repo.update_record_review(
        record_id=rec_id,
        action=ReviewStatus.CONFIRMED,
        reviewer_id="SURGEON-DR-SMITH",
        review_notes="Clinically valid pre-EVA baseline"
    )

    # Query Medical RAG for this astronaut
    query = RetrievalQuery(
        query_id="QRY-ELIG-01",
        query_text="What is the confirmed Serum Hemoglobin level for astronaut?",
        astronaut_id=astro_id,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)

    assert status == RAGRetrievalStatus.SUCCESS
    assert len(passages) >= 1
    target_passage = next((p for p in passages if p.chunk_id == f"REC-{rec_id}"), None)
    assert target_passage is not None
    assert target_passage.astronaut_id == astro_id
    assert target_passage.document_id == doc_id
    assert target_passage.review_status == "CONFIRMED"
    assert "15.8" in target_passage.excerpt
    assert "SURGEON-DR-SMITH" in target_passage.excerpt
    assert target_passage.source_timestamp == "2026-10-15"
    assert target_passage.is_historical is True

def test_02_pending_document_exclusion(rag_service, doc_repo):
    """Test 4A.2: Pending P01 medical records are NOT eligible and strictly excluded from answers."""
    astro_id = f"AST-PEND-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-PEND-{uuid.uuid4().hex[:6].upper()}"
    rec_id = f"REC-PEND-{uuid.uuid4().hex[:6].upper()}"

    doc_repo.save_document(
        document_id=doc_id,
        astronaut_id=astro_id,
        filename="pending_lab.pdf",
        file_hash=f"hash_{doc_id}",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path=f"/tmp/{doc_id}.pdf"
    )

    rec = ExtractedMedicalRecord(
        record_id=rec_id,
        document_id=doc_id,
        source_type="page",
        source_page_number=1,
        source_location="Page 1 Table 1",
        test_name="Unreviewed Ferritin",
        extracted_value="350.0",
        normalized_value=350.0,
        original_unit="ng/mL",
        normalized_unit="ng/ml",
        reference_range="30 - 400 ng/mL",
        collection_date="2026-10-18",
        extraction_confidence=0.85,
        validation_status=ValidationStatus.NEEDS_REVIEW,
        extraction_method=ExtractionMethod.NATIVE_TEXT,
        source_text="Ferritin: 350.0 ng/mL"
    )
    # Save as pending (default review_status=PENDING_REVIEW)
    doc_repo.save_extracted_records([rec], astronaut_id=astro_id)

    query = RetrievalQuery(
        query_id="QRY-ELIG-02",
        query_text="What is the Unreviewed Ferritin level for astronaut?",
        astronaut_id=astro_id,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)

    # Pending record must NEVER be returned as a confirmed passage
    assert not any(p.chunk_id == f"REC-{rec_id}" for p in passages)

def test_03_rejected_document_exclusion(rag_service, doc_repo):
    """Test 4A.3: Rejected P01 medical records are completely excluded from medical RAG."""
    astro_id = f"AST-REJ-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-REJ-{uuid.uuid4().hex[:6].upper()}"
    rec_id = f"REC-REJ-{uuid.uuid4().hex[:6].upper()}"

    doc_repo.save_document(
        document_id=doc_id,
        astronaut_id=astro_id,
        filename="rejected_scan.pdf",
        file_hash=f"hash_{doc_id}",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path=f"/tmp/{doc_id}.pdf"
    )

    rec = ExtractedMedicalRecord(
        record_id=rec_id,
        document_id=doc_id,
        source_type="page",
        source_page_number=1,
        source_location="Page 1",
        test_name="Artifactual Heart Rate",
        extracted_value="280.0",
        normalized_value=280.0,
        original_unit="bpm",
        normalized_unit="bpm",
        collection_date="2026-10-19",
        validation_status=ValidationStatus.NEEDS_REVIEW,
        extraction_method=ExtractionMethod.GROQ_VISION_OCR,
        source_text="Heart Rate: 280 bpm (Motion artifact)"
    )
    doc_repo.save_extracted_records([rec], astronaut_id=astro_id)

    # Flight Surgeon explicitly REJECTS the artifactual record
    doc_repo.update_record_review(
        record_id=rec_id,
        action=ReviewStatus.REJECTED,
        reviewer_id="SURGEON-DR-JONES",
        review_notes="Rejected due to severe motion artifact on sensor"
    )

    query = RetrievalQuery(
        query_id="QRY-ELIG-03",
        query_text="Show Artifactual Heart Rate for astronaut",
        astronaut_id=astro_id,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)

    assert not any(p.chunk_id == f"REC-{rec_id}" for p in passages)

def test_04_quarantined_document_exclusion(rag_service, doc_repo):
    """Test 4A.4: Quarantined records with conflicting extractions are flagged or excluded from trusted facts."""
    astro_id = f"AST-QUAR-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-QUAR-{uuid.uuid4().hex[:6].upper()}"
    rec_id = f"REC-QUAR-{uuid.uuid4().hex[:6].upper()}"

    doc_repo.save_document(
        document_id=doc_id,
        astronaut_id=astro_id,
        filename="conflict_panel.pdf",
        file_hash=f"hash_{doc_id}",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path=f"/tmp/{doc_id}.pdf"
    )

    rec = ExtractedMedicalRecord(
        record_id=rec_id,
        document_id=doc_id,
        source_type="page",
        source_page_number=1,
        source_location="Page 1 vs Page 2",
        test_name="Disputed Blood Glucose",
        extracted_value="185.0",
        normalized_value=185.0,
        original_unit="mg/dL",
        normalized_unit="mg/dl",
        collection_date="2026-10-20",
        validation_status=ValidationStatus.CONFLICTING_EXTRACTION,
        validation_warnings=["Conflicting extraction between page 1 (95) and page 2 (185)"],
        extraction_method=ExtractionMethod.NATIVE_TEXT,
        source_text="Glucose: 185 mg/dL (Conflicting)"
    )
    doc_repo.save_extracted_records([rec], astronaut_id=astro_id)

    doc_repo.update_record_review(
        record_id=rec_id,
        action=ReviewStatus.CONFIRMED,
        reviewer_id="SURGEON-DR-LEE",
        review_notes="Confirmed as conflicting"
    )

    query = RetrievalQuery(
        query_id="QRY-ELIG-04",
        query_text="What is the Disputed Blood Glucose level?",
        astronaut_id=astro_id,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)

    # If returned, must be flagged conflict_detected or status CONFLICT_DETECTED
    target = next((p for p in passages if p.chunk_id == f"REC-{rec_id}"), None)
    if target:
        assert target.conflict_detected is True
        assert status == RAGRetrievalStatus.CONFLICT_DETECTED

def test_05_missing_astronaut_identity(rag_service):
    """Test 4A.5: Missing/Unknown astronaut identity must produce safe abstention, never default to AST-001."""
    query = RetrievalQuery(
        query_id="QRY-ELIG-05",
        query_text="Show personal medical records and platelet counts from last week",
        astronaut_id=None,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)

    assert status == RAGRetrievalStatus.ISOLATION_VIOLATION
    assert len(passages) == 0

def test_06_cross_astronaut_isolation(rag_service, doc_repo):
    """Test 4A.6: Cross-astronaut queries (AST-001 session querying AST-002) are strictly blocked."""
    session_astro = "AST-001"
    target_astro = "AST-002"

    query = RetrievalQuery(
        query_id="QRY-ELIG-06",
        query_text=f"Retrieve blood panel history and confirmed records for astronaut {target_astro}",
        astronaut_id=session_astro,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)

    assert status == RAGRetrievalStatus.ISOLATION_VIOLATION
    assert len(passages) == 0

def test_07_missing_document_provenance(rag_service, doc_repo):
    """Test 4A.7: Retrieved clinical records must preserve non-empty document_id and record provenance."""
    astro_id = f"AST-PROV-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-PROV-{uuid.uuid4().hex[:6].upper()}"
    rec_id = f"REC-PROV-{uuid.uuid4().hex[:6].upper()}"

    doc_repo.save_document(
        document_id=doc_id,
        astronaut_id=astro_id,
        filename="lab_provenance.pdf",
        file_hash=f"hash_{doc_id}",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path=f"/tmp/{doc_id}.pdf"
    )

    rec = ExtractedMedicalRecord(
        record_id=rec_id,
        document_id=doc_id,
        source_type="page",
        source_page_number=2,
        source_location="Page 2 Section B",
        test_name="Plasma Cortisol",
        extracted_value="14.2",
        normalized_value=14.2,
        original_unit="ug/dL",
        normalized_unit="ug/dl",
        reference_range="5.0 - 25.0 ug/dL",
        collection_date="2026-10-22",
        laboratory_name="ESA Biomedical Laboratory",
        validation_status=ValidationStatus.VALIDATED,
        extraction_method=ExtractionMethod.NATIVE_TEXT,
        source_text="Cortisol: 14.2 ug/dL"
    )
    doc_repo.save_extracted_records([rec], astronaut_id=astro_id)
    doc_repo.update_record_review(
        record_id=rec_id,
        action=ReviewStatus.CONFIRMED,
        reviewer_id="SURGEON-DR-SCHMIDT",
        review_notes="Verified provenance"
    )

    query = RetrievalQuery(
        query_id="QRY-ELIG-07",
        query_text="What was the Plasma Cortisol level for astronaut?",
        astronaut_id=astro_id,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)
    target = next((p for p in passages if p.chunk_id == f"REC-{rec_id}"), None)

    assert target is not None
    assert target.document_id == doc_id
    assert target.astronaut_id == astro_id
    assert target.citation_reference == f"{doc_id}:PLASMA_CORTISOL"
    assert target.source_timestamp == "2026-10-22"

def test_08_document_status_changed_after_indexing(rag_service, doc_repo):
    """Test 4A.8: If a confirmed record is subsequently rejected, retrieval immediately excludes it."""
    astro_id = f"AST-MUT-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-MUT-{uuid.uuid4().hex[:6].upper()}"
    rec_id = f"REC-MUT-{uuid.uuid4().hex[:6].upper()}"

    doc_repo.save_document(
        document_id=doc_id,
        astronaut_id=astro_id,
        filename="mutation_lab.pdf",
        file_hash=f"hash_{doc_id}",
        file_type="pdf",
        file_size_bytes=1024,
        storage_path=f"/tmp/{doc_id}.pdf"
    )

    rec = ExtractedMedicalRecord(
        record_id=rec_id,
        document_id=doc_id,
        test_name="Serum Potassium",
        extracted_value="4.2",
        normalized_value=4.2,
        original_unit="mmol/L",
        validation_status=ValidationStatus.VALIDATED,
        extraction_method=ExtractionMethod.NATIVE_TEXT,
        source_text="Potassium: 4.2 mmol/L"
    )
    doc_repo.save_extracted_records([rec], astronaut_id=astro_id)

    # Initial confirmation
    doc_repo.update_record_review(record_id=rec_id, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-A")
    query = RetrievalQuery(query_id="Q-M-1", query_text="Serum Potassium", astronaut_id=astro_id)
    p1, _ = rag_service.retriever.retrieve(query)
    assert any(p.chunk_id == f"REC-{rec_id}" for p in p1)

    # Review decision changed to REJECTED (e.g. lab reported contamination)
    doc_repo.update_record_review(record_id=rec_id, action=ReviewStatus.REJECTED, reviewer_id="SURGEON-A", review_notes="Specimen contaminated")
    query2 = RetrievalQuery(query_id="Q-M-2", query_text="Serum Potassium", astronaut_id=astro_id)
    p2, _ = rag_service.retriever.retrieve(query2)
    assert not any(p.chunk_id == f"REC-{rec_id}" for p in p2)

def test_09_cache_isolation_between_astronauts(rag_service, doc_repo):
    """Test 4A.9: Sequential requests for AST-A and AST-B never leak cached clinical findings."""
    astro_a = f"AST-ISOA-{uuid.uuid4().hex[:6].upper()}"
    astro_b = f"AST-ISOB-{uuid.uuid4().hex[:6].upper()}"

    # Ingest record for A
    doc_a = f"DOC-A-{uuid.uuid4().hex[:6]}"
    rec_a = f"REC-A-{uuid.uuid4().hex[:6]}"
    doc_repo.save_document(document_id=doc_a, astronaut_id=astro_a, filename="a.pdf", file_hash=f"h_{doc_a}", file_type="pdf", file_size_bytes=100, storage_path="/tmp/a.pdf")
    doc_repo.save_extracted_records([
        ExtractedMedicalRecord(record_id=rec_a, document_id=doc_a, test_name="Unique Analyte A", extracted_value="99.9", normalized_value=99.9, validation_status=ValidationStatus.VALIDATED, extraction_method=ExtractionMethod.NATIVE_TEXT)
    ], astronaut_id=astro_a)
    doc_repo.update_record_review(record_id=rec_a, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-A")

    # Ingest record for B
    doc_b = f"DOC-B-{uuid.uuid4().hex[:6]}"
    rec_b = f"REC-B-{uuid.uuid4().hex[:6]}"
    doc_repo.save_document(document_id=doc_b, astronaut_id=astro_b, filename="b.pdf", file_hash=f"h_{doc_b}", file_type="pdf", file_size_bytes=100, storage_path="/tmp/b.pdf")
    doc_repo.save_extracted_records([
        ExtractedMedicalRecord(record_id=rec_b, document_id=doc_b, test_name="Unique Analyte B", extracted_value="11.1", normalized_value=11.1, validation_status=ValidationStatus.VALIDATED, extraction_method=ExtractionMethod.NATIVE_TEXT)
    ], astronaut_id=astro_b)
    doc_repo.update_record_review(record_id=rec_b, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-B")

    # Query A: should get Analyte A, never Analyte B
    qa = RetrievalQuery(query_id="QA", query_text="lab results and confirmed records", astronaut_id=astro_a)
    pass_a, _ = rag_service.retriever.retrieve(qa)
    assert any(p.chunk_id == f"REC-{rec_a}" for p in pass_a)
    assert not any(p.chunk_id == f"REC-{rec_b}" for p in pass_a)

    # Query B: should get Analyte B, never Analyte A
    qb = RetrievalQuery(query_id="QB", query_text="lab results and confirmed records", astronaut_id=astro_b)
    pass_b, _ = rag_service.retriever.retrieve(qb)
    assert any(p.chunk_id == f"REC-{rec_b}" for p in pass_b)
    assert not any(p.chunk_id == f"REC-{rec_a}" for p in pass_b)

def test_10_re_ingestion_and_duplicate_document_behavior(rag_service):
    """Test 4A.10: Re-ingesting an identical file returns the existing document ID via SHA-256 deduplication."""
    content = b"CRITICAL MEDICAL PROTOCOL FOR EXTRAVEHICULAR HYPOXIA RECOVERY: Maintain 100% O2 flush."
    filename = "test_duplicate_protocol.txt"

    doc1 = rag_service.ingest_document(file_bytes=content, filename=filename)
    doc2 = rag_service.ingest_document(file_bytes=content, filename=filename)

    assert doc1.document_id == doc2.document_id
    assert doc1.content_hash == doc2.content_hash
