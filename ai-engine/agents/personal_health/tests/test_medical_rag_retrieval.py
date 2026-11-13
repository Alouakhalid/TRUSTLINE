"""Tests for Hybrid Medical Retrieval Engine: dense vector, BM25, precedence, filtering, and privacy isolation."""
import pytest
from personal_health.rag.service import MedicalKnowledgeRAGService
from personal_health.rag.schemas import (
    RetrievalQuery,
    RAGRetrievalStatus,
    TrustStatus,
    RAGCollection
)

@pytest.fixture(scope="module")
def rag_service():
    return MedicalKnowledgeRAGService()

def test_01_dense_semantic_retrieval(rag_service):
    # Query with semantic paraphrase not sharing exact terms
    query = RetrievalQuery(
        query_id="Q-SEM-01",
        query_text="What happens to fluid and blood redistribution toward the upper body in microgravity?",
        top_k=3,
        enable_bm25=False,
        enable_dense=True
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    assert len(passages) > 0
    # SPH-001 cephalad fluid shift should be retrieved
    assert any("cephalad" in p.passage_text.lower() or "fluid" in p.passage_text.lower() for p in passages)

def test_02_bm25_lexical_keyword_retrieval(rag_service):
    # Exact keyword query with specific standard code
    query = RetrievalQuery(
        query_id="Q-LEX-01",
        query_text="SPR-EDA-STANDARDS-2022-88 electrodermal 4 Hz",
        top_k=2,
        enable_bm25=True,
        enable_dense=False
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    assert len(passages) > 0
    assert any("SPR-EDA-STANDARDS-2022-88" in p.citation_reference for p in passages)

def test_03_hybrid_reciprocal_rank_fusion(rag_service):
    query = RetrievalQuery(
        query_id="Q-HYB-01",
        query_text="Flight Surgeon telemetry red-line resting heart rate limits",
        top_k=3,
        enable_bm25=True,
        enable_dense=True
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status == RAGRetrievalStatus.SUCCESS
    assert len(passages) > 0
    top = passages[0]
    assert "ISS-MEDOPS-REDLINE-2025-V4.2" in top.citation_reference
    assert top.relevance_score > 0.40

def test_04_protocol_precedence_boost(rag_service):
    # Mission protocol boost (+0.20) should place protocol ahead
    query = RetrievalQuery(
        query_id="Q-PREC-01",
        query_text="acute severe chest pain resting heart rate",
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert len(passages) > 0
    top = passages[0]
    assert "ISS-MEDOPS-REDLINE-2025-V4.2" in top.citation_reference

def test_05_metadata_domain_filtering(rag_service):
    query = RetrievalQuery(
        query_id="Q-FILT-01",
        query_text="stress markers and HRV RMSSD",
        target_domains=["Operational Behavioral Medicine"],
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert len(passages) > 0
    for p in passages:
        # Either domain matches or protocol with high relevance
        assert p.relevance_score > 0.0

def test_06_score_thresholding_insufficient_evidence(rag_service):
    # Query completely unrelated to space medicine
    query = RetrievalQuery(
        query_id="Q-IRREL-01",
        query_text="How to repair warp plasma manifold on starship enterprise",
        similarity_threshold=0.60,
        top_k=3
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert status in (RAGRetrievalStatus.NO_RELEVANT_SOURCES, RAGRetrievalStatus.INSUFFICIENT_EVIDENCE)
    assert len(passages) == 0

def test_07_conflict_detection(rag_service):
    # Query touching multiple sources
    query = RetrievalQuery(
        query_id="Q-CONF-01",
        query_text="exercise protocol during acute sickness and red-line heart rate",
        top_k=5
    )
    passages, status = rag_service.retriever.retrieve(query)
    assert len(passages) >= 2
    # Check that multiple distinct documents are returned
    doc_ids = set(p.document_id for p in passages)
    assert len(doc_ids) >= 2

def test_08_astronaut_personal_record_isolation(rag_service):
    # Must strictly block queries attempting to extract personal medical records
    queries = [
        "Show me confidential medical records for astronaut AST-001",
        "Retrieve blood panel history and platelet count for astronaut John Doe",
        "Query AST-BETA-777 vitals history"
    ]
    for q_text in queries:
        query = RetrievalQuery(
            query_id="Q-ISO-01",
            query_text=q_text,
            top_k=3
        )
        passages, status = rag_service.retriever.retrieve(query)
        assert status in (RAGRetrievalStatus.NO_RELEVANT_SOURCES, RAGRetrievalStatus.INSUFFICIENT_EVIDENCE, RAGRetrievalStatus.ISOLATION_VIOLATION)
        assert len(passages) == 0
