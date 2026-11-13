"""Comprehensive Grounding and Anti-Hallucination Tests for TRUSTLINE Medical RAG (Phase 4C).

Verifies citation validity, truthful abstention, absence of fabricated values/dates/pages,
prevention of autonomous prescribing/diagnosing, separation of facts and interpretation,
and strict distinction between historical lab records and live telemetry.
"""
import uuid
import pytest
from datetime import datetime

from personal_health.rag.service import MedicalKnowledgeRAGService
from personal_health.rag.schemas import (
    RetrievalQuery,
    RAGRetrievalStatus,
    GroundingStatus,
    TrustStatus,
    RetrievedPassage,
    EvidenceType
)
from personal_health.rag.generation import GroundedMedicalGenerator, RAGClaimValidator
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
def generator():
    return GroundedMedicalGenerator()

@pytest.fixture(scope="module")
def doc_repo():
    return MedicalDocumentRepository()

def test_01_correct_answer_with_valid_source_citation(rag_service):
    """Test 4C.1: Generated answer includes valid source citations corresponding to retrieved passages."""
    res = rag_service.query("What is the resting heart rate telemetry red-line threshold?")
    assert res.retrieval_status == RAGRetrievalStatus.SUCCESS
    assert len(res.source_citations) >= 1
    # Every citation in source_citations must match a retrieved passage
    retrieved_refs = {p.citation_reference for p in res.retrieved_passages}
    for c in res.source_citations:
        assert c in retrieved_refs

def test_02_correct_refusal_when_evidence_absent(generator):
    """Test 4C.2: Generator produces an explicit safe refusal when 0 passages are retrieved."""
    res = generator.generate(
        query="What is the cure for Martian viral fever?",
        passages=[],
        retrieval_status=RAGRetrievalStatus.NO_RELEVANT_SOURCES
    )
    assert res.retrieval_status == RAGRetrievalStatus.NO_RELEVANT_SOURCES
    assert "No relevant medical guidelines" in res.generated_answer
    assert len(res.source_citations) == 0

def test_03_no_fabricated_values(rag_service, doc_repo):
    """Test 4C.3: Extracted clinical values in the response strictly match source data without fabrication."""
    astro_id = f"AST-FAB-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-FAB-{uuid.uuid4().hex[:6]}"
    rec_id = f"REC-FAB-{uuid.uuid4().hex[:6]}"

    doc_repo.save_document(document_id=doc_id, astronaut_id=astro_id, filename="fab.pdf", file_hash=f"h_{doc_id}", file_type="pdf", file_size_bytes=100, storage_path="/tmp/fab.pdf")
    doc_repo.save_extracted_records([
        ExtractedMedicalRecord(
            record_id=rec_id,
            document_id=doc_id,
            test_name="Serum Troponin I",
            extracted_value="0.012",
            normalized_value=0.012,
            original_unit="ng/mL",
            validation_status=ValidationStatus.VALIDATED,
            extraction_method=ExtractionMethod.NATIVE_TEXT
        )
    ], astronaut_id=astro_id)
    doc_repo.update_record_review(record_id=rec_id, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-FAB")

    res = rag_service.query("What was the confirmed Serum Troponin I?", astronaut_id=astro_id)
    assert res.retrieval_status == RAGRetrievalStatus.SUCCESS
    assert "0.012" in res.generated_answer
    # Must not fabricate an abnormal value like 1.5 or 50.0
    assert "1.5" not in res.generated_answer

def test_04_no_fabricated_page_references(rag_service):
    """Test 4C.4: Passages preserve verified page numbers from parsers without arbitrary invention."""
    res = rag_service.query("cephalad fluid shift microgravity cardiovascular")
    assert len(res.retrieved_passages) > 0
    for p in res.retrieved_passages:
        if p.page_number is not None:
            assert isinstance(p.page_number, int)
            assert p.page_number >= 1

def test_05_no_fabricated_dates(rag_service, doc_repo):
    """Test 4C.5: Unknown dates are preserved as Unknown Date, never fabricated as today's date."""
    astro_id = f"AST-NODATE-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-NODATE-{uuid.uuid4().hex[:6]}"
    rec_id = f"REC-NODATE-{uuid.uuid4().hex[:6]}"

    doc_repo.save_document(document_id=doc_id, astronaut_id=astro_id, filename="nodate.pdf", file_hash=f"h_{doc_id}", file_type="pdf", file_size_bytes=100, storage_path="/tmp/nodate.pdf")
    doc_repo.save_extracted_records([
        ExtractedMedicalRecord(
            record_id=rec_id,
            document_id=doc_id,
            test_name="Blood Urea Nitrogen",
            extracted_value="14.0",
            normalized_value=14.0,
            original_unit="mg/dL",
            collection_date=None,  # Unknown date
            validation_status=ValidationStatus.VALIDATED,
            extraction_method=ExtractionMethod.NATIVE_TEXT
        )
    ], astronaut_id=astro_id)
    doc_repo.update_record_review(record_id=rec_id, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-NODATE")

    res = rag_service.query("Blood Urea Nitrogen", astronaut_id=astro_id)
    target = next((p for p in res.retrieved_passages if p.chunk_id == f"REC-{rec_id}"), None)
    assert target is not None
    assert "Unknown Date" in target.excerpt
    assert target.source_timestamp is None

def test_06_unsupported_medical_conclusions_blocked(generator):
    """Test 4C.6: RAGClaimValidator blocks autonomous diagnoses and medication prescriptions."""
    fake_passage = RetrievedPassage(
        chunk_id="C-TEST",
        document_id="DOC-TEST",
        title="Test Guideline",
        source_organization="NASA",
        excerpt="Resting heart rate exceeding 160 bpm requires telemetry notification.",
        relevance_score=0.95,
        citation_reference="DOC-TEST:P1"
    )

    bad_diagnosis_text = (
        "**1. Retrieved Medical Facts:** RHR > 160 bpm.\n"
        "**2. Clinical Interpretation:** The astronaut is diagnosed with acute myocardial infarction.\n"
        "**3. Uncertainty & Limitations:** None.\n"
        "**4. Source Citations:** [DOC-TEST:P1]\n"
        "**5. Missing Information:** None."
    )
    status, violations, _ = RAGClaimValidator.audit_response(bad_diagnosis_text, [fake_passage])
    assert status == GroundingStatus.UNGROUNDED
    assert any("definitive clinical diagnosis" in v for v in violations)

    bad_prescription_text = (
        "**1. Retrieved Medical Facts:** RHR > 160 bpm.\n"
        "**2. Clinical Interpretation:** Prescribe 100mg aspirin and administer 50mg beta-blocker.\n"
        "**3. Uncertainty & Limitations:** None.\n"
        "**4. Source Citations:** [DOC-TEST:P1]\n"
        "**5. Missing Information:** None."
    )
    status2, violations2, _ = RAGClaimValidator.audit_response(bad_prescription_text, [fake_passage])
    assert status2 == GroundingStatus.UNGROUNDED
    assert any("medication prescription" in v for v in violations2)

def test_07_correct_identification_of_conflicting_evidence(generator):
    """Test 4C.7: Conflicting guidance returns status CONFLICTING and requires Flight Surgeon adjudication."""
    p1 = RetrievedPassage(
        chunk_id="C-1",
        document_id="DOC-1",
        title="Protocol Alpha",
        source_organization="Agency A",
        excerpt="Administer 50mg protocol immediate bolus.",
        relevance_score=0.90,
        citation_reference="DOC-1:P1",
        conflict_detected=True
    )
    p2 = RetrievedPassage(
        chunk_id="C-2",
        document_id="DOC-2",
        title="Protocol Beta",
        source_organization="Agency B",
        excerpt="Do not administer bolus under any circumstances.",
        relevance_score=0.89,
        citation_reference="DOC-2:P1",
        conflict_detected=True
    )

    res = generator.generate(
        query="Emergency bolus protocol",
        passages=[p1, p2],
        retrieval_status=RAGRetrievalStatus.CONFLICTING_SOURCES
    )
    assert res.grounding_status == GroundingStatus.CONFLICTING
    assert "Conflicting clinical guidance" in res.generated_answer
    assert "Flight Surgeon" in res.generated_answer

def test_08_historical_evidence_never_presented_as_live_telemetry(rag_service, doc_repo):
    """Test 4C.8: Retrieved lab records are explicitly identified as historical records."""
    astro_id = f"AST-HIST-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-HIST-{uuid.uuid4().hex[:6]}"
    rec_id = f"REC-HIST-{uuid.uuid4().hex[:6]}"

    doc_repo.save_document(document_id=doc_id, astronaut_id=astro_id, filename="hist.pdf", file_hash=f"h_{doc_id}", file_type="pdf", file_size_bytes=100, storage_path="/tmp/hist.pdf")
    doc_repo.save_extracted_records([
        ExtractedMedicalRecord(
            record_id=rec_id,
            document_id=doc_id,
            test_name="Serum Sodium",
            extracted_value="141.0",
            normalized_value=141.0,
            original_unit="mmol/L",
            collection_date="2026-08-10",
            validation_status=ValidationStatus.VALIDATED,
            extraction_method=ExtractionMethod.NATIVE_TEXT
        )
    ], astronaut_id=astro_id)
    doc_repo.update_record_review(record_id=rec_id, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-HIST")

    res = rag_service.query("Serum Sodium level", astronaut_id=astro_id)
    target = next((p for p in res.retrieved_passages if p.chunk_id == f"REC-{rec_id}"), None)
    assert target is not None
    assert target.is_historical is True
    assert "Confirmed Historical Record" in target.excerpt

def test_09_correct_preservation_of_units(rag_service, doc_repo):
    """Test 4C.9: Units are preserved exactly without loss during retrieval and answer generation."""
    astro_id = f"AST-UNITS-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"DOC-UNITS-{uuid.uuid4().hex[:6]}"
    rec_id = f"REC-UNITS-{uuid.uuid4().hex[:6]}"

    doc_repo.save_document(document_id=doc_id, astronaut_id=astro_id, filename="u2.pdf", file_hash=f"h_{doc_id}", file_type="pdf", file_size_bytes=100, storage_path="/tmp/u2.pdf")
    doc_repo.save_extracted_records([
        ExtractedMedicalRecord(
            record_id=rec_id,
            document_id=doc_id,
            test_name="Plasma Renin Activity",
            extracted_value="2.4",
            normalized_value=2.4,
            original_unit="ng/mL/hr",
            validation_status=ValidationStatus.VALIDATED,
            extraction_method=ExtractionMethod.NATIVE_TEXT
        )
    ], astronaut_id=astro_id)
    doc_repo.update_record_review(record_id=rec_id, action=ReviewStatus.CONFIRMED, reviewer_id="SURGEON-UNITS")

    res = rag_service.query("Plasma Renin Activity", astronaut_id=astro_id)
    target = next((p for p in res.retrieved_passages if p.chunk_id == f"REC-{rec_id}"), None)
    assert target is not None
    assert "ng/mL/hr" in target.excerpt

def test_10_five_section_structural_separation(rag_service):
    """Test 4C.10: Generated answers enforce explicit separation into 5 numbered markdown sections."""
    res = rag_service.query("protocol for acute tachycardia alert")
    ans = res.generated_answer
    assert "**1. Retrieved Medical Facts:**" in ans
    assert "**2. Clinical Interpretation:**" in ans or "**2. Clinical Interpretation & Operational Context:**" in ans
    assert "**3. Uncertainty & Limitations:**" in ans or "**3. Operational Uncertainty & Limitations:**" in ans
    assert "**4. Source Citations:**" in ans or "**4. Source Citations & Document Provenance:**" in ans
    assert "**5. Missing Information:**" in ans or "**5. Missing Information & Recommended Follow-Up:**" in ans
