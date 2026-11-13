"""Schemas and domain contracts for TRUSTLINE Medical Knowledge RAG subsystem."""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

# Re-export legacy enums and models for backwards compatibility
from ..schemas.rag_evidence import (
    RAGCollection,
    EvidenceType,
    RAGEvidenceItem
)

class DocumentType(str, Enum):
    """Supported knowledge document file formats and structural types."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    JSON = "json"
    GUIDELINE = "guideline"

class TrustStatus(str, Enum):
    """Evidence authority level for medical knowledge documents and chunks."""
    OFFICIAL_GUIDELINE = "OFFICIAL_GUIDELINE"
    PEER_REVIEWED = "PEER_REVIEWED"
    INSTITUTIONAL_REFERENCE = "INSTITUTIONAL_REFERENCE"
    GENERAL_EDUCATIONAL = "GENERAL_EDUCATIONAL"
    UNVERIFIED = "UNVERIFIED"

    # Compatibility aliases
    MISSION_PROTOCOL = "OFFICIAL_GUIDELINE"
    CLINICAL_GUIDELINE = "OFFICIAL_GUIDELINE"

class RAGRetrievalStatus(str, Enum):
    """Granular outcome status of a retrieval operation."""
    SUCCESS = "SUCCESS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_RELEVANT_SOURCES = "NO_RELEVANT_SOURCES"
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    ISOLATION_VIOLATION = "ISOLATION_VIOLATION"
    CROSS_ASTRONAUT_VIOLATION = "CROSS_ASTRONAUT_VIOLATION"
    UNVERIFIED_ASTRONAUT_IDENTITY = "UNVERIFIED_ASTRONAUT_IDENTITY"
    EMPTY_CORPUS = "EMPTY_CORPUS"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
    GENERATION_FAILURE = "GENERATION_FAILURE"

class GroundingStatus(str, Enum):
    """Clinical evidence grounding classification for generated answers."""
    FULLY_GROUNDED = "FULLY_GROUNDED"
    PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
    UNGROUNDED = "UNGROUNDED"
    CONFLICTING = "CONFLICTING"

class MedicalKnowledgeDocument(BaseModel):
    """Top-level medical knowledge document in the TRUSTLINE knowledge corpus."""
    document_id: str = Field(..., description="Unique document identifier e.g. DOC-NASA-STD-3001")
    source_id: str = Field(default="", description="Original reference or publication identifier")
    title: str = Field(..., description="Document or guideline title")
    author: Optional[str] = Field(default=None, description="Author or investigator")
    source_organization: str = Field(..., description="Issuing organization e.g. NASA, ESA, JAXA, WHO")
    publication_date: Optional[str] = Field(default=None, description="ISO publication date YYYY-MM-DD")
    document_version: str = Field(default="1.0", description="Document or standard revision")
    document_type: DocumentType = Field(default=DocumentType.PDF, description="Original file type")
    medical_domain: str = Field(default="Aerospace Medicine", description="Clinical or physiological topic")
    source_url: Optional[str] = Field(default=None, description="URL or authoritative registry link")
    ingestion_timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC ingestion timestamp")
    content_hash: str = Field(..., description="SHA-256 cryptographic hash of document content")
    trust_status: TrustStatus = Field(default=TrustStatus.OFFICIAL_GUIDELINE, description="Authority classification")
    verification_notes: Optional[str] = Field(default=None, description="Verification or validation audit note")
    file_path: Optional[str] = Field(default=None, description="Storage location on disk")
    file_size_bytes: int = Field(default=0, description="Size in bytes")
    total_chunks: int = Field(default=0, description="Count of parsed chunks indexed")

class MedicalChunk(BaseModel):
    """Clinically coherent structure-aware chunk extracted from a knowledge document."""
    chunk_id: str = Field(..., description="Unique chunk identifier e.g. DOC-NASA-STD-3001_c001")
    document_id: str = Field(..., description="Parent document identifier")
    document_title: Optional[str] = Field(default=None, description="Parent document title")
    section_title: str = Field(default="General", description="Immediate section or header title")
    heading_hierarchy: List[str] = Field(default_factory=list, description="Path of parent headers")
    page_number: Optional[int] = Field(default=None, description="1-indexed source page number")
    chunk_index: int = Field(default=0, description="Sequential index within document")
    content: str = Field(..., description="Text content of the chunk")
    token_count: int = Field(default=0, description="Estimated token count")
    table_data: Optional[List[List[str]]] = Field(default=None, description="Preserved tabular data")
    citation_reference: str = Field(..., description="Standard citation tag e.g. NASA-STD-3001-Sec4.2-P12")
    trust_status: TrustStatus = Field(default=TrustStatus.OFFICIAL_GUIDELINE)
    medical_domain: str = Field(default="Aerospace Medicine")
    embedding: Optional[List[float]] = Field(default=None, description="Dense vector embedding")

class RetrievalQuery(BaseModel):
    """Structured search request targeting the medical knowledge corpus."""
    query_id: str = Field(..., description="Unique query tracking identifier")
    query_text: str = Field(..., min_length=1, description="Medical question or operational query")
    astronaut_id: Optional[str] = Field(default=None, description="Authenticated astronaut ID for the session")
    include_confirmed_records: bool = Field(default=True, description="Whether to include confirmed clinical records for astronaut")
    include_general_knowledge: bool = Field(default=True, description="Whether to include general medical guidelines")
    target_domains: List[str] = Field(default_factory=list, description="Optional domain filters")
    target_collections: List[RAGCollection] = Field(default_factory=list, description="Collections to search")
    min_authority: TrustStatus = Field(default=TrustStatus.GENERAL_EDUCATIONAL, description="Minimum acceptable trust status")
    top_k: int = Field(default=3, ge=1, le=20, description="Maximum passages to retrieve")
    similarity_threshold: float = Field(default=0.25, ge=0.0, le=1.0, description="Minimum fused relevance score")
    enable_bm25: bool = Field(default=True, description="Enable BM25 sparse lexical retrieval")
    enable_dense: bool = Field(default=True, description="Enable dense semantic vector retrieval")
    filter_metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata filters")

class RetrievedPassage(BaseModel):
    """Individual passage returned by the hybrid retrieval engine with provenance."""
    chunk_id: str
    document_id: str
    title: str
    source_organization: str
    excerpt: str
    page_number: Optional[int] = None
    section_title: str = "General"
    relevance_score: float = Field(..., description="Fused relevance score [0.0 - 1.0+]")
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    evidence_type: EvidenceType = Field(default=EvidenceType.CLINICAL_GUIDELINE)
    trust_status: TrustStatus = Field(default=TrustStatus.OFFICIAL_GUIDELINE)
    citation_reference: str
    retrieval_timestamp: datetime = Field(default_factory=datetime.utcnow)
    astronaut_id: Optional[str] = None
    document_hash: Optional[str] = None
    evidence_id: Optional[str] = None
    source_filename: Optional[str] = None
    review_status: Optional[str] = None
    source_timestamp: Optional[str] = None
    ingestion_timestamp: Optional[datetime] = None
    is_historical: bool = True
    conflict_detected: bool = False
    test_name: Optional[str] = None
    extracted_value: Optional[str] = None
    normalized_unit: Optional[str] = None
    reference_range: Optional[str] = None

    @property
    def passage_text(self) -> str:
        """Backwards compatibility alias for excerpt."""
        return self.excerpt

    def to_rag_evidence_item(self) -> RAGEvidenceItem:
        """Convert to legacy RAGEvidenceItem for backwards compatibility."""
        col_map = {
            "cardiovascular": RAGCollection.BIOMEDICAL_KNOWLEDGE,
            "spaceflight": RAGCollection.SPACE_HEALTH_RESEARCH,
            "emergency": RAGCollection.MISSION_MEDICAL_PROTOCOLS,
            "psychological": RAGCollection.PSYCHOLOGICAL_COGNITIVE_RESEARCH,
            "signal": RAGCollection.PHYSIOLOGICAL_SIGNAL_RESEARCH
        }
        matched_col = RAGCollection.BIOMEDICAL_KNOWLEDGE
        for k, col in col_map.items():
            if k in self.title.lower() or k in self.section_title.lower() or k in self.excerpt.lower():
                matched_col = col
                break
        return RAGEvidenceItem(
            doc_id=self.document_id,
            collection=matched_col,
            title=self.title,
            source_organization=self.source_organization,
            medical_domain=self.section_title,
            evidence_type=self.evidence_type,
            excerpt=self.excerpt,
            relevance_score=self.relevance_score,
            citation_reference=self.citation_reference,
            retrieval_timestamp=self.retrieval_timestamp
        )

class RAGGenerationResult(BaseModel):
    """Comprehensive output contract for grounded medical knowledge RAG."""
    query_id: str
    query: str
    retrieved_passages: List[RetrievedPassage] = Field(default_factory=list)
    source_metadata: List[Dict[str, Any]] = Field(default_factory=list)
    relevance_scores: Dict[str, float] = Field(default_factory=dict)
    generated_answer: str = Field(default="", description="Full grounded synthesis")
    retrieved_facts: List[str] = Field(default_factory=list, description="Direct empirical medical facts")
    synthesis_interpretation: str = Field(default="", description="Clinical interpretation")
    uncertainty_and_limitations: List[str] = Field(default_factory=list, description="Expressed caveats and limits")
    source_citations: List[str] = Field(default_factory=list, description="Verified citations")
    missing_information: List[str] = Field(default_factory=list, description="Identified informational gaps")
    claim_evidence_mapping: List[Dict[str, Any]] = Field(default_factory=list, description="Sentence-level audit trace")
    retrieval_status: RAGRetrievalStatus = Field(default=RAGRetrievalStatus.SUCCESS)
    grounding_status: GroundingStatus = Field(default=GroundingStatus.FULLY_GROUNDED)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
