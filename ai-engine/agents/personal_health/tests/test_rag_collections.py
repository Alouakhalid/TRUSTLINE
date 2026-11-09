"""Unit tests for multi-collection aerospace medical RAG system."""
import pytest
from personal_health.rag.vector_store import MedicalVectorStore
from personal_health.services.rag_service import MedicalRAGService
from personal_health.schemas.rag_evidence import RAGCollection, EvidenceType

def test_five_collections_populated():
    """Verify that all 5 required medical collections are initialized with documents."""
    store = MedicalVectorStore()
    for col in RAGCollection:
        docs = store._collections[col]
        assert len(docs) > 0, f"Collection {col.value} has no ingested documents."

def test_mission_protocol_precedence():
    """Verify approved mission medical protocols receive precedence in operational queries."""
    svc = MedicalRAGService()
    results = svc.query_medical_evidence(query="chest pain emergency escalation protocol", top_k=3)
    assert len(results) > 0
    top = results[0]
    assert top.evidence_type == EvidenceType.APPROVED_MISSION_PROTOCOL
    assert "REDLINE" in top.citation_reference or "MEDOPS" in top.citation_reference

def test_hrv_collection_routing():
    """Verify HRV interpretation query routes to signal and biomedical collections."""
    store = MedicalVectorStore()
    matched = store.route_query_collections("ultra short term hrv rmssd signal noise")
    assert RAGCollection.PHYSIOLOGICAL_SIGNAL_RESEARCH in matched or RAGCollection.BIOMEDICAL_KNOWLEDGE in matched
