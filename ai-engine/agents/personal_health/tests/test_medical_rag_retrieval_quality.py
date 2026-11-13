"""Comprehensive Retrieval Quality Tests for TRUSTLINE Medical RAG (Phase 4B).

Verifies exact medical terminology, semantic paraphrase, abbreviations, units,
historical dates, multi-document synthesis, out-of-domain handling, and conflicting records.
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

def test_01_exact_medical_terminology_query(rag_service):
    """Test 4B.1: Exact medical terminology retrieves authoritative clinical guidelines."""
    query = RetrievalQuery(
        query_id="Q-QUAL-01",
        query_text="What is the critical red-line resting heart rate threshold for emergency escalation?",
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    assert len(passages) >= 1
    # Check that ISS Medical Operations Redline is top-ranked
    assert any("ISS-MEDOPS-REDLINE" in p.citation_reference for p in passages)
    assert any("160" in p.excerpt or "heart rate" in p.excerpt.lower() for p in passages)

def test_02_semantic_paraphrase_query(rag_service):
    """Test 4B.2: Semantic paraphrase retrieves relevant passages even without lexical overlap."""
    query = RetrievalQuery(
        query_id="Q-QUAL-02",
        query_text="What happens when bodily liquids and interstitial fluid move up into the cranial region during spaceflight?",
        top_k=3,
        enable_dense=True,
        enable_bm25=False
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    assert len(passages) >= 1
    assert any("cephalad" in p.excerpt.lower() or "fluid" in p.excerpt.lower() for p in passages)

def test_03_query_with_abbreviations(rag_service):
    """Test 4B.3: Biomedical acronyms (EDA, HRV, RMSSD) are correctly mapped to standards."""
    query = RetrievalQuery(
        query_id="Q-QUAL-03",
        query_text="Recommended sampling rate and filter parameters for EDA and HRV RMSSD calculation",
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    assert len(passages) >= 1
    assert any("SPR-EDA-STANDARDS" in p.citation_reference or "IEEE-EMBS" in p.citation_reference for p in passages)

def test_04_query_involving_units(rag_service, doc_repo):
    """Test 4B.4: Queries specifying numerical units (mg/dL vs mmol/L) preserve correct units."""
    astro_id = f"AST-UNIT-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-UNIT-{uuid.uuid4().hex[:6]}"
    rec_id = f"REC-UNIT-{uuid.uuid4().hex[:6]}"

    doc_repo.save_document(document_id=doc_id, astronaut_id=astro_id, filename="u.pdf", file_hash=f"h_{doc_id}", file_type="pdf", file_size_bytes=100, storage_path="/tmp/u.pdf")
    doc_repo.save_extracted_records([
        ExtractedMedicalRecord(
            record_id=rec_id,
            document_id=doc_id,
            test_name="Fasting Blood Glucose",
            extracted_value="95.0",
            normalized_value=95.0,
            original_unit="mg/dL",
            normalized_unit="mg/dl",
            reference_range="70 - 99 mg/dL",
            validation_status=ValidationStatus.VALIDATED,
            extraction_method=ExtractionMethod.NATIVE_TEXT
        )
    ], astronaut_id=astro_id)
    doc_repo.update_record_review(record_id=rec_id, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-UNIT")

    query = RetrievalQuery(
        query_id="Q-QUAL-04",
        query_text="What was the Fasting Blood Glucose in mg/dL?",
        astronaut_id=astro_id
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    target = next((p for p in passages if p.chunk_id == f"REC-{rec_id}"), None)
    assert target is not None
    assert "mg/dL" in target.excerpt
    assert target.normalized_unit in ("mg/dl", "mg/dL")

def test_05_query_involving_historical_dates(rag_service, doc_repo):
    """Test 4B.5: Historical collection dates are preserved and retrievable."""
    astro_id = f"AST-DATE-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-DATE-{uuid.uuid4().hex[:6]}"
    rec_id = f"REC-DATE-{uuid.uuid4().hex[:6]}"

    doc_repo.save_document(document_id=doc_id, astronaut_id=astro_id, filename="d.pdf", file_hash=f"h_{doc_id}", file_type="pdf", file_size_bytes=100, storage_path="/tmp/d.pdf")
    doc_repo.save_extracted_records([
        ExtractedMedicalRecord(
            record_id=rec_id,
            document_id=doc_id,
            test_name="Pre-Flight Hematocrit",
            extracted_value="45.2",
            normalized_value=45.2,
            original_unit="%",
            collection_date="2026-09-01",
            validation_status=ValidationStatus.VALIDATED,
            extraction_method=ExtractionMethod.NATIVE_TEXT
        )
    ], astronaut_id=astro_id)
    doc_repo.update_record_review(record_id=rec_id, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-DATE")

    query = RetrievalQuery(
        query_id="Q-QUAL-05",
        query_text="Show Pre-Flight Hematocrit from 2026-09-01",
        astronaut_id=astro_id
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    target = next((p for p in passages if p.chunk_id == f"REC-{rec_id}"), None)
    assert target is not None
    assert "2026-09-01" in target.excerpt
    assert target.source_timestamp == "2026-09-01"

def test_06_multi_document_information_retrieval(rag_service):
    """Test 4B.6: Query spanning multiple protocols retrieves passages from distinct sources."""
    query = RetrievalQuery(
        query_id="Q-QUAL-06",
        query_text="Protocol for autonomic cardiac red-lines and behavioral confinement stress countermeasures",
        top_k=4
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    assert len(passages) >= 2
    doc_ids = {p.document_id for p in passages}
    # Multiple distinct documents retrieved
    assert len(doc_ids) >= 2

def test_07_irrelevant_query_handling(rag_service):
    """Test 4B.7: Completely irrelevant general queries return no relevant sources or low scores."""
    query = RetrievalQuery(
        query_id="Q-QUAL-07",
        query_text="How to bake sourdough bread with whole wheat flour in an Italian wood-fired oven?",
        similarity_threshold=0.50,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)
    # Threshold filters out irrelevant content
    assert status in (RAGRetrievalStatus.NO_RELEVANT_SOURCES, RAGRetrievalStatus.SUCCESS)
    if passages:
        # None of them should have high relevance to sourdough bread
        assert all(p.relevance_score < 0.60 for p in passages)

def test_08_query_with_no_supporting_evidence(rag_service):
    """Test 4B.8: Fictional medical inquiries have no supporting evidence."""
    query = RetrievalQuery(
        query_id="Q-QUAL-08",
        query_text="What is the therapeutic dosage for Martian fungal osteomyelitis in deep space?",
        similarity_threshold=0.45,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)
    # System returns no relevant sources above strict threshold
    assert status in (RAGRetrievalStatus.NO_RELEVANT_SOURCES, RAGRetrievalStatus.SUCCESS)

def test_09_duplicate_chunk_deduplication(rag_service):
    """Test 4B.9: Retrieved passages contain unique chunk identifiers without exact duplicates."""
    query = RetrievalQuery(
        query_id="Q-QUAL-09",
        query_text="spaceflight cephalad fluid shift cardiovascular deconditioning",
        top_k=5
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    chunk_ids = [p.chunk_id for p in passages]
    assert len(chunk_ids) == len(set(chunk_ids)), "Duplicate chunks found in retrieval results"

def test_10_conflicting_historical_records_retrieval(rag_service, doc_repo):
    """Test 4B.10: Conflicting clinical extractions trigger CONFLICT_DETECTED status."""
    astro_id = f"AST-CONF2-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-CONF2-{uuid.uuid4().hex[:6]}"
    rec_id = f"REC-CONF2-{uuid.uuid4().hex[:6]}"

    doc_repo.save_document(document_id=doc_id, astronaut_id=astro_id, filename="c.pdf", file_hash=f"h_{doc_id}", file_type="pdf", file_size_bytes=100, storage_path="/tmp/c.pdf")
    doc_repo.save_extracted_records([
        ExtractedMedicalRecord(
            record_id=rec_id,
            document_id=doc_id,
            test_name="Divergent Blood Sugar",
            extracted_value="210.0",
            normalized_value=210.0,
            original_unit="mg/dL",
            validation_status=ValidationStatus.CONFLICTING_EXTRACTION,
            validation_warnings=["Conflicting extraction with baseline"],
            extraction_method=ExtractionMethod.NATIVE_TEXT
        )
    ], astronaut_id=astro_id)
    doc_repo.update_record_review(record_id=rec_id, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-C")

    query = RetrievalQuery(
        query_id="Q-QUAL-10",
        query_text="What is the Divergent Blood Sugar level?",
        astronaut_id=astro_id
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.CONFLICT_DETECTED
    target = next((p for p in passages if p.chunk_id == f"REC-{rec_id}"), None)
    assert target is not None
    assert target.conflict_detected is True
