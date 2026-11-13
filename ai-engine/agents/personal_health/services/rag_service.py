"""Medical RAG retrieval service orchestrating multi-collection searches and hybrid knowledge retrieval."""
from typing import Dict, List, Optional, Union
from ..rag.vector_store import MedicalVectorStore
from ..rag.service import MedicalKnowledgeRAGService
from ..schemas.rag_evidence import RAGCollection, EvidenceType, RAGEvidenceItem
from ..rag.schemas import RAGGenerationResult, RetrievalQuery, MedicalKnowledgeDocument

class MedicalRAGService:
    """Service providing citation-preserving medical knowledge retrieval and grounded generation."""

    def __init__(
        self,
        vector_store: Optional[MedicalVectorStore] = None,
        knowledge_service: Optional[MedicalKnowledgeRAGService] = None
    ):
        self.vector_store = vector_store or MedicalVectorStore()
        self._knowledge_service = knowledge_service or MedicalKnowledgeRAGService()

    def query_medical_evidence(
        self,
        query: str,
        collection: Optional[RAGCollection] = None,
        top_k: int = 3
    ) -> List[RAGEvidenceItem]:
        """Search medical knowledge base and return ranked evidence items."""
        if not query.strip():
            return []
        try:
            return self._knowledge_service.query_medical_evidence(query=query, collection=collection, top_k=top_k)
        except Exception:
            return self.vector_store.search(query=query, collection=collection, top_k=top_k)

    def retrieve_approved_protocol(self, symptom_or_trigger: str) -> Optional[RAGEvidenceItem]:
        """Retrieve authoritative mission medical protocol for an operational trigger."""
        try:
            return self._knowledge_service.retrieve_approved_protocol(symptom_or_trigger)
        except Exception:
            results = self.vector_store.search(
                query=f"protocol emergency {symptom_or_trigger}",
                collection=RAGCollection.MISSION_MEDICAL_PROTOCOLS,
                top_k=1
            )
            if results and results[0].evidence_type == EvidenceType.APPROVED_MISSION_PROTOCOL:
                return results[0]
            return None

    def query(self, query: Union[str, RetrievalQuery]) -> RAGGenerationResult:
        """Execute full hybrid RAG pipeline returning grounded synthesis and claim traces."""
        return self._knowledge_service.query(query)

    def ingest_document(self, file_bytes: bytes, filename: str, **kwargs) -> MedicalKnowledgeDocument:
        """Ingest a medical knowledge document into the vector store and BM25 index."""
        return self._knowledge_service.ingest_document(file_bytes=file_bytes, filename=filename, **kwargs)
