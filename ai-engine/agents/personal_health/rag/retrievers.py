"""Hybrid retrieval engine combining dense vector search, BM25 lexical ranking, and protocol precedence."""
import math
import re
from typing import Dict, List, Optional, Tuple, Any

from rank_bm25 import BM25Okapi

from .schemas import (
    MedicalChunk,
    RetrievalQuery,
    RetrievedPassage,
    RAGRetrievalStatus,
    TrustStatus,
    EvidenceType
)
from .storage import MedicalKnowledgeVectorStore

class BM25LexicalRetriever:
    """Sparse lexical retriever using BM25Okapi over medical knowledge chunks."""

    def __init__(self):
        self._chunks: List[MedicalChunk] = []
        self._bm25: Optional[BM25Okapi] = None

    def index_chunks(self, chunks: List[MedicalChunk]):
        self._chunks = list(chunks)
        if not self._chunks:
            self._bm25 = None
            return

        corpus = [self._tokenize(c.content) for c in self._chunks]
        self._bm25 = BM25Okapi(corpus)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def query_bm25(self, query_text: str, top_k: int = 10) -> List[Tuple[MedicalChunk, float]]:
        if not self._bm25 or not self._chunks:
            return []

        tokens = self._tokenize(query_text)
        if not tokens:
            return []

        raw_scores = self._bm25.get_scores(tokens)
        max_score = max(raw_scores) if len(raw_scores) > 0 else 1.0
        if max_score <= 0.0:
            return []

        scored: List[Tuple[MedicalChunk, float]] = []
        for c, s in zip(self._chunks, raw_scores):
            if s > 0.0:
                norm_s = min(1.0, float(s) / max(1.0, max_score))
                scored.append((c, round(norm_s, 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

class HybridMedicalRetriever:
    """Fused retrieval engine integrating dense semantics, BM25 lexical precision, and clinical authority boosting."""

    def __init__(
        self,
        vector_store: MedicalKnowledgeVectorStore,
        dense_weight: float = 0.65,
        sparse_weight: float = 0.35,
        protocol_boost: float = 0.20,
        similarity_threshold: float = 0.25,
        repository: Optional[Any] = None
    ):
        self.vector_store = vector_store
        self.repository = repository
        self.bm25_retriever = BM25LexicalRetriever()
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.protocol_boost = protocol_boost
        self.similarity_threshold = similarity_threshold
        self._indexed_chunks: Dict[str, MedicalChunk] = {}

    def sync_lexical_index(self, chunks: List[MedicalChunk]):
        """Update BM25 corpus with indexed chunks."""
        for c in chunks:
            self._indexed_chunks[c.chunk_id] = c
        self.bm25_retriever.index_chunks(list(self._indexed_chunks.values()))

    def remove_document_chunks(self, document_id: str):
        """Remove document chunks from lexical index."""
        self._indexed_chunks = {
            cid: c for cid, c in self._indexed_chunks.items()
            if c.document_id != document_id
        }
        self.bm25_retriever.index_chunks(list(self._indexed_chunks.values()))

    def retrieve(self, query: RetrievalQuery) -> Tuple[List[RetrievedPassage], RAGRetrievalStatus]:
        """Execute hybrid retrieval with metadata filtering, protocol precedence, and conflict detection."""
        q_text = query.query_text.strip()
        if not q_text:
            return [], RAGRetrievalStatus.INSUFFICIENT_EVIDENCE

        # Guard against unauthorized confidential record dumping
        confidential_patterns = (
            r"confidential\s+(?:medical\s+)?records?",
            r"(?:history|records?|vitals?|blood\s+panel|platelet|troponin|lab\s+result|biomarker)\b.*for\s+astronaut",
            r"records?\s+for\s+astronaut"
        )
        if any(re.search(pat, q_text, re.IGNORECASE) for pat in confidential_patterns):
            return [], RAGRetrievalStatus.ISOLATION_VIOLATION

        # Detect any explicit astronaut IDs mentioned in the query text
        astro_matches = re.findall(r"\bAST-([A-Za-z0-9_-]+)\b", q_text, re.IGNORECASE)
        queried_astros = [f"AST-{m.upper()}" for m in astro_matches]
        session_astro = (query.astronaut_id or "").upper().strip()

        # Cross-astronaut isolation check
        if queried_astros:
            if not session_astro or session_astro in ("UNKNOWN", "AST-UNKNOWN"):
                return [], RAGRetrievalStatus.ISOLATION_VIOLATION
            if any(qa != session_astro for qa in queried_astros):
                return [], RAGRetrievalStatus.ISOLATION_VIOLATION

        # Unauthenticated personal inquiry check
        if not session_astro or session_astro in ("UNKNOWN", "AST-UNKNOWN"):
            personal_leak_patterns = (
                r"(?:personal|patient)\s+(?:medical\s+)?records?",
                r"\b(platelet\s+counts?|blood\s+glucose|troponin|lipid\s+panel)\s+from\s+last\b",
                r"\b(my|his|her)\s+medical\s+(records?|history)\b"
            )
            if any(re.search(pat, q_text, re.IGNORECASE) for pat in personal_leak_patterns):
                return [], RAGRetrievalStatus.ISOLATION_VIOLATION

        clinical_passages: List[RetrievedPassage] = []

        # 1. P01 Confirmed Medical Records Retrieval (Lifecycle-enforced)
        if query.include_confirmed_records and session_astro and session_astro not in ("UNKNOWN", "AST-UNKNOWN"):
            repo = self.repository
            if repo is None:
                try:
                    from personal_health.repositories.medical_document_repository import MedicalDocumentRepository
                    repo = MedicalDocumentRepository()
                except Exception:
                    repo = None

            if repo is not None:
                try:
                    confirmed_records = repo.get_confirmed_records(session_astro)
                    for rec in confirmed_records:
                        test_str = (rec.test_name or "").lower()
                        q_lower = q_text.lower()
                        is_match = (
                            (test_str and test_str in q_lower)
                            or any(t in q_lower for t in test_str.split() if len(t) > 3)
                            or any(term in q_lower for term in ("lab record", "lab result", "confirmed record", "blood test", "medical test", "historical record", "blood panel"))
                        )
                        if is_match:
                            coll_str = rec.collection_date or "Unknown Date"
                            conf_time = rec.confirmation_timestamp.strftime("%Y-%m-%d %H:%M:%S") if rec.confirmation_timestamp else "N/A"
                            excerpt_text = (
                                f"Confirmed Historical Record: {rec.test_name} = {rec.value_string} {rec.unit or ''} "
                                f"(Reference Range: {rec.reference_range or 'N/A'}, Collection Date: {coll_str}). "
                                f"Confirmed by Flight Surgeon: {rec.confirmed_by} on {conf_time}."
                            )
                            is_conf = bool(rec.conflict_detected)
                            rel_s = 0.98 if (test_str and test_str in q_lower) else 0.88

                            passage = RetrievedPassage(
                                chunk_id=f"REC-{rec.record_id}",
                                document_id=rec.document_id,
                                title=f"Confirmed Record: {rec.test_name}",
                                source_organization=rec.laboratory_name or "Flight Medicine Clinic",
                                excerpt=excerpt_text,
                                page_number=1,
                                section_title="Confirmed Clinical Findings",
                                relevance_score=rel_s,
                                dense_score=rel_s,
                                sparse_score=rel_s,
                                evidence_type=EvidenceType.CONFIRMED_CLINICAL_FINDING,
                                trust_status=TrustStatus.OFFICIAL_GUIDELINE,
                                citation_reference=f"{rec.document_id}:{rec.test_name.upper().replace(' ', '_')}",
                                astronaut_id=rec.astronaut_id,
                                source_filename=rec.source_location or rec.document_id,
                                review_status="CONFIRMED",
                                source_timestamp=rec.collection_date,
                                ingestion_timestamp=rec.confirmation_timestamp,
                                is_historical=True,
                                conflict_detected=is_conf,
                                test_name=rec.test_name,
                                extracted_value=rec.value_string,
                                normalized_unit=rec.unit,
                                reference_range=rec.reference_range
                            )
                            clinical_passages.append(passage)
                except Exception:
                    pass

        # 1. Dense retrieval
        dense_results: List[Tuple[MedicalChunk, float]] = []
        if query.enable_dense:
            try:
                where_filter = {}
                if query.target_domains:
                    where_filter["medical_domain"] = {"$in": query.target_domains}
                dense_results = self.vector_store.query_dense(
                    query_text=q_text,
                    top_k=query.top_k * 3,
                    where_filter=where_filter if where_filter else None
                )
            except Exception:
                dense_results = []

        # 2. Sparse BM25 retrieval
        sparse_results: List[Tuple[MedicalChunk, float]] = []
        if query.enable_bm25:
            sparse_results = self.bm25_retriever.query_bm25(query_text=q_text, top_k=query.top_k * 3)

        # 3. Fusion scoring & Deduplication
        fused_scores: Dict[str, Dict[str, Any]] = {}

        for chunk, d_score in dense_results:
            fused_scores[chunk.chunk_id] = {
                "chunk": chunk,
                "dense_score": d_score,
                "sparse_score": 0.0
            }

        for chunk, s_score in sparse_results:
            if chunk.chunk_id in fused_scores:
                fused_scores[chunk.chunk_id]["sparse_score"] = s_score
            else:
                fused_scores[chunk.chunk_id] = {
                    "chunk": chunk,
                    "dense_score": 0.0,
                    "sparse_score": s_score
                }

        if not fused_scores and not clinical_passages:
            return [], RAGRetrievalStatus.NO_RELEVANT_SOURCES

        ranked: List[RetrievedPassage] = []

        for cid, info in fused_scores.items():
            chunk: MedicalChunk = info["chunk"]
            d_s = info["dense_score"]
            s_s = info["sparse_score"]

            # Weighted fusion
            combined = (self.dense_weight * d_s) + (self.sparse_weight * s_s)

            # Protocol precedence boost for official guidelines
            if chunk.trust_status == TrustStatus.OFFICIAL_GUIDELINE:
                combined += self.protocol_boost
            
            # Map evidence type
            ev_type = EvidenceType.CLINICAL_GUIDELINE
            if chunk.trust_status == TrustStatus.OFFICIAL_GUIDELINE:
                ev_type = EvidenceType.APPROVED_MISSION_PROTOCOL
            elif chunk.trust_status == TrustStatus.PEER_REVIEWED:
                ev_type = EvidenceType.PEER_REVIEWED_RESEARCH
            elif chunk.trust_status == TrustStatus.INSTITUTIONAL_REFERENCE:
                ev_type = EvidenceType.FLIGHT_SURGEON_GUIDELINE

            passage = RetrievedPassage(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                title=chunk.section_title,
                source_organization=chunk.medical_domain,
                excerpt=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                relevance_score=round(combined, 4),
                dense_score=round(d_s, 4),
                sparse_score=round(s_s, 4),
                evidence_type=ev_type,
                trust_status=chunk.trust_status,
                citation_reference=chunk.citation_reference
            )
            ranked.append(passage)

        all_candidates = clinical_passages + ranked
        if not all_candidates:
            return [], RAGRetrievalStatus.NO_RELEVANT_SOURCES

        all_candidates.sort(key=lambda x: x.relevance_score, reverse=True)

        # Apply thresholding
        filtered = [p for p in all_candidates if p.relevance_score >= query.similarity_threshold]
        if not filtered:
            return [], RAGRetrievalStatus.NO_RELEVANT_SOURCES

        top_passages = filtered[:query.top_k]

        # Check for conflicting guidance in retrieved passages
        if any(p.conflict_detected for p in top_passages) or self._detect_conflicts(top_passages):
            return top_passages, RAGRetrievalStatus.CONFLICT_DETECTED

        return top_passages, RAGRetrievalStatus.SUCCESS

    @staticmethod
    def _detect_conflicts(passages: List[RetrievedPassage]) -> bool:
        """Identify contradictory clinical thresholds or opposing recommendations."""
        if len(passages) < 2:
            return False

        has_mandatory_rest = False
        has_exercise_recommended = False

        for p in passages:
            lower = p.excerpt.lower()
            if "strict bed rest" in lower or "exercise contraindicated" in lower or "terminate eva immediately" in lower:
                has_mandatory_rest = True
            if "countermeasure exercise protocol" in lower or "mandatory aerobic exercise" in lower or "continue mission tasks" in lower:
                has_exercise_recommended = True

        return has_mandatory_rest and has_exercise_recommended
