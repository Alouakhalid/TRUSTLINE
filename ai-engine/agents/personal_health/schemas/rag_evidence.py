"""Schemas for medical and aerospace research evidence retrieved via RAG."""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class EvidenceType(str, Enum):
    """Clinical authority level of retrieved document."""
    APPROVED_MISSION_PROTOCOL = "APPROVED_MISSION_PROTOCOL"
    FLIGHT_SURGEON_GUIDELINE = "FLIGHT_SURGEON_GUIDELINE"
    CLINICAL_GUIDELINE = "CLINICAL_GUIDELINE"
    PEER_REVIEWED_RESEARCH = "PEER_REVIEWED_RESEARCH"
    TECHNICAL_SPECIFICATION = "TECHNICAL_SPECIFICATION"

class RAGCollection(str, Enum):
    """The 5 required aerospace medical knowledge collections."""
    BIOMEDICAL_KNOWLEDGE = "biomedical_knowledge"
    SPACE_HEALTH_RESEARCH = "space_health_research"
    MISSION_MEDICAL_PROTOCOLS = "mission_medical_protocols"
    PSYCHOLOGICAL_COGNITIVE_RESEARCH = "psychological_cognitive_research"
    PHYSIOLOGICAL_SIGNAL_RESEARCH = "physiological_signal_research"

class RAGEvidenceItem(BaseModel):
    """Single evidence chunk retrieved from the aerospace medical knowledge base."""
    doc_id: str
    collection: RAGCollection
    title: str
    source_organization: str
    author: Optional[str] = None
    publication_date: Optional[str] = None
    version: Optional[str] = None
    medical_domain: str
    evidence_type: EvidenceType
    population_studied: Optional[str] = None
    spaceflight_relevance: str = Field(default="high")
    approval_status: str = Field(default="approved_flight_medicine")
    excerpt: str
    relevance_score: Optional[float] = None
    citation_reference: str
    retrieval_timestamp: datetime = Field(default_factory=datetime.utcnow)
