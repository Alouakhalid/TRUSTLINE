"""Medical RAG retrieval service orchestrating multi-collection searches."""
from typing import Dict, List, Optional
from ..rag.vector_store import MedicalVectorStore
from ..schemas.rag_evidence import RAGCollection, EvidenceType, RAGEvidenceItem

class MedicalRAGService:
    """Service providing citation-preserving medical knowledge retrieval."""

    def __init__(self, vector_store: Optional[MedicalVectorStore] = None):
        self.vector_store = vector_store or MedicalVectorStore()

    def query_medical_evidence(
        self,
        query: str,
        collection: Optional[RAGCollection] = None,
        top_k: int = 3
    ) -> List[RAGEvidenceItem]:
        """Search medical knowledge base and return ranked evidence items."""
        if not query.strip():
            return []
        return self.vector_store.search(query=query, collection=collection, top_k=top_k)

    def retrieve_approved_protocol(self, symptom_or_trigger: str) -> Optional[RAGEvidenceItem]:
        """Retrieve authoritative mission medical protocol for an operational trigger."""
        results = self.vector_store.search(
            query=f"protocol emergency {symptom_or_trigger}",
            collection=RAGCollection.MISSION_MEDICAL_PROTOCOLS,
            top_k=1
        )
        if results and results[0].evidence_type == EvidenceType.APPROVED_MISSION_PROTOCOL:
            return results[0]
        return None
