"""Supervisor integration adapter orchestrating Medical Knowledge RAG queries and state contracts."""
from typing import Dict, List, Optional, Any
from personal_health.rag.service import MedicalKnowledgeRAGService
from personal_health.rag.schemas import RAGRetrievalStatus, GroundingStatus

class MedicalRAGIntegrationService:
    """Bridge executing medical knowledge retrieval and grounded synthesis for the Supervisor."""

    def __init__(self, rag_service: Optional[MedicalKnowledgeRAGService] = None):
        self._rag_service = rag_service or MedicalKnowledgeRAGService()

    def execute_rag_for_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract query intent from supervisor state, execute hybrid RAG, and return structured result."""
        query_text = state.get("reported_symptoms_text") or ""
        symptoms = state.get("reported_symptoms") or []
        
        if not query_text and symptoms:
            first_sym = symptoms[0]
            s_type = first_sym.get("symptom_type", "symptom") if isinstance(first_sym, dict) else getattr(first_sym, "symptom_type", "symptom")
            query_text = f"protocol emergency {s_type}"

        if not query_text.strip():
            return {
                "query_id": "QRY-EMPTY",
                "query": "",
                "retrieved_passages": [],
                "source_metadata": [],
                "relevance_scores": {},
                "generated_answer": "No medical query or symptom text was provided for knowledge retrieval.",
                "retrieved_facts": [],
                "synthesis_interpretation": "No query submitted.",
                "uncertainty_and_limitations": ["Absence of query."],
                "source_citations": [],
                "missing_information": ["Medical query string."],
                "claim_evidence_mapping": [],
                "retrieval_status": RAGRetrievalStatus.NO_RELEVANT_SOURCES.value,
                "grounding_status": GroundingStatus.FULLY_GROUNDED.value,
                "execution_metadata": {"reason": "EMPTY_QUERY"}
            }

        try:
            res = self._rag_service.query(query_text, astronaut_id=state.get("astronaut_id"))
            return res.model_dump()
        except Exception as exc:
            return {
                "query_id": f"QRY-ERR-{abs(hash(query_text)) % 1000000:06d}",
                "query": query_text,
                "retrieved_passages": [],
                "source_metadata": [],
                "relevance_scores": {},
                "generated_answer": "Medical knowledge retrieval failed due to an internal service exception.",
                "retrieved_facts": [],
                "synthesis_interpretation": "Retrieval exception.",
                "uncertainty_and_limitations": [str(exc)],
                "source_citations": [],
                "missing_information": ["Knowledge corpus unavailable."],
                "claim_evidence_mapping": [],
                "retrieval_status": RAGRetrievalStatus.RETRIEVAL_FAILURE.value,
                "grounding_status": GroundingStatus.UNGROUNDED.value,
                "execution_metadata": {"error": str(exc)}
            }
