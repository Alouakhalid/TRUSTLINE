"""In-memory and persistent vector index managing aerospace medical collections."""
import json
import math
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .collections import COLLECTION_DOMAINS, ROUTING_KEYWORDS
from ..schemas.rag_evidence import RAGCollection, EvidenceType, RAGEvidenceItem

class MedicalVectorStore:
    """Multi-collection aerospace medical retrieval engine with protocol precedence."""

    def __init__(self, knowledge_base_dir: Optional[Path] = None):
        self.kb_dir = knowledge_base_dir or Path(__file__).resolve().parent / "knowledge_base"
        self._collections: Dict[RAGCollection, List[RAGEvidenceItem]] = {c: [] for c in RAGCollection}
        self.load_all_collections()

    def load_all_collections(self):
        """Ingest all curated JSON knowledge documents into memory."""
        file_mapping = {
            RAGCollection.BIOMEDICAL_KNOWLEDGE: "biomedical_knowledge.json",
            RAGCollection.SPACE_HEALTH_RESEARCH: "space_health_research.json",
            RAGCollection.MISSION_MEDICAL_PROTOCOLS: "mission_medical_protocols.json",
            RAGCollection.PSYCHOLOGICAL_COGNITIVE_RESEARCH: "psychological_cognitive.json",
            RAGCollection.PHYSIOLOGICAL_SIGNAL_RESEARCH: "physiological_signals.json"
        }
        for col, fname in file_mapping.items():
            p = self.kb_dir / fname
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    docs = json.load(f)
                    for d in docs:
                        item = RAGEvidenceItem(
                            doc_id=d["doc_id"],
                            collection=col,
                            title=d["title"],
                            source_organization=d["source_organization"],
                            author=d.get("author"),
                            publication_date=d.get("publication_date"),
                            version=d.get("version"),
                            medical_domain=d["medical_domain"],
                            evidence_type=EvidenceType(d["evidence_type"]),
                            population_studied=d.get("population_studied"),
                            spaceflight_relevance=d.get("spaceflight_relevance", "high"),
                            approval_status=d.get("approval_status", "approved"),
                            excerpt=d["excerpt"],
                            relevance_score=1.0,
                            citation_reference=d["citation_reference"]
                        )
                        self._collections[col].append(item)

    def route_query_collections(self, query: str) -> List[RAGCollection]:
        """Determine target collections based on domain intent and keywords."""
        q_lower = query.lower()
        matched: List[RAGCollection] = []

        if any(kw in q_lower for kw in ROUTING_KEYWORDS[RAGCollection.MISSION_MEDICAL_PROTOCOLS]):
            matched.append(RAGCollection.MISSION_MEDICAL_PROTOCOLS)

        for col, keywords in ROUTING_KEYWORDS.items():
            if col == RAGCollection.MISSION_MEDICAL_PROTOCOLS:
                continue
            if any(kw in q_lower for kw in keywords):
                if col not in matched:
                    matched.append(col)

        if not matched:
            matched = [RAGCollection.BIOMEDICAL_KNOWLEDGE, RAGCollection.SPACE_HEALTH_RESEARCH]

        return matched

    def search(
        self,
        query: str,
        collection: Optional[RAGCollection] = None,
        top_k: int = 3
    ) -> List[RAGEvidenceItem]:
        """Execute hybrid keyword and semantic scoring with protocol precedence."""
        target_cols = [collection] if collection else self.route_query_collections(query)
        candidates: List[RAGEvidenceItem] = []

        for c in target_cols:
            candidates.extend(self._collections.get(c, []))

        if not candidates:
            return []

        q_terms = set(re.findall(r"\w+", query.lower()))
        scored: List[Tuple[float, RAGEvidenceItem]] = []

        for item in candidates:
            doc_text = f"{item.title} {item.excerpt} {item.medical_domain}".lower()
            doc_terms = set(re.findall(r"\w+", doc_text))
            overlap = len(q_terms.intersection(doc_terms))

            score = float(overlap) / max(1.0, math.sqrt(len(q_terms) * len(doc_terms)))

            if item.evidence_type == EvidenceType.APPROVED_MISSION_PROTOCOL:
                score += 0.25

            item_copy = item.model_copy(update={"relevance_score": round(score, 4)})
            scored.append((score, item_copy))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]
