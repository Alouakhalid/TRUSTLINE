"""Unified Medical Knowledge RAG Service orchestrating ingestion, hybrid retrieval, and grounded generation."""
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from .schemas import (
    MedicalKnowledgeDocument,
    MedicalChunk,
    RetrievalQuery,
    RetrievedPassage,
    RAGGenerationResult,
    RAGRetrievalStatus,
    DocumentType,
    TrustStatus,
    RAGEvidenceItem,
    RAGCollection,
    EvidenceType
)
from .parsers import (
    KnowledgeParserSecurityValidator,
    PDFKnowledgeParser,
    DOCXKnowledgeParser,
    TextKnowledgeParser,
    JSONKnowledgeParser,
    ParsedSection
)
from .chunking import StructureAwareChunker
from .storage import MedicalKnowledgeVectorStore
from .retrievers import HybridMedicalRetriever
from .generation import GroundedMedicalGenerator
from .embeddings import get_embedding_provider, BaseEmbeddingProvider

class MedicalKnowledgeRAGService:
    """Unified medical knowledge ingestion, hybrid search, and citation-grounded generation service."""

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        vector_store: Optional[MedicalKnowledgeVectorStore] = None,
        repository: Optional[Any] = None
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider("auto")
        self.vector_store = vector_store or MedicalKnowledgeVectorStore(
            persist_dir=persist_dir,
            embedding_provider=self.embedding_provider
        )
        self.repository = repository
        self.retriever = HybridMedicalRetriever(vector_store=self.vector_store, repository=self.repository)
        self.generator = GroundedMedicalGenerator()
        self.chunker = StructureAwareChunker()
        self._documents: Dict[str, MedicalKnowledgeDocument] = {}
        self._hash_to_doc_id: Dict[str, str] = {}
        self._auto_load_default_kb()

    def _auto_load_default_kb(self):
        """Auto-index default curated aerospace medical knowledge files from knowledge_base directory."""
        default_kb_dir = Path(__file__).resolve().parent / "knowledge_base"
        if default_kb_dir.exists():
            self.ingest_corpus_directory(default_kb_dir)

    def ingest_file(
        self,
        file_bytes: bytes,
        filename: str,
        title: Optional[str] = None,
        doc_type: Optional[DocumentType] = None,
        source_organization: str = "NASA / ISS Medical Operations",
        medical_domain: str = "Aerospace Medicine",
        trust_status: TrustStatus = TrustStatus.OFFICIAL_GUIDELINE,
        source_url: Optional[str] = None,
        publication_date: Optional[str] = None,
        version: str = "1.0",
        citation_base: Optional[str] = None,
        **kwargs
    ) -> MedicalKnowledgeDocument:
        """Backwards-compatibility alias for ingest_document."""
        return self.ingest_document(
            file_bytes=file_bytes,
            filename=filename,
            title=title,
            source_organization=source_organization,
            medical_domain=medical_domain,
            trust_status=trust_status,
            source_url=source_url,
            publication_date=publication_date,
            version=version,
            citation_base=citation_base
        )

    def ingest_document(
        self,
        file_bytes: bytes,
        filename: str,
        title: Optional[str] = None,
        source_organization: str = "NASA / ISS Medical Operations",
        medical_domain: str = "Aerospace Medicine",
        trust_status: TrustStatus = TrustStatus.OFFICIAL_GUIDELINE,
        source_url: Optional[str] = None,
        publication_date: Optional[str] = None,
        version: str = "1.0",
        citation_base: Optional[str] = None
    ) -> MedicalKnowledgeDocument:
        """Ingest a medical document (PDF, DOCX, TXT, JSON) with content hash deduplication."""
        doc_type = KnowledgeParserSecurityValidator.validate(file_bytes, filename)
        content_hash = hashlib.sha256(file_bytes).hexdigest()

        # Idempotency check: if document with identical hash already indexed, return existing metadata
        if content_hash in self._hash_to_doc_id:
            existing_id = self._hash_to_doc_id[content_hash]
            return self._documents[existing_id]

        doc_stem = Path(filename).stem.upper().replace(" ", "-")
        doc_id = f"KNOW-{doc_stem}-{content_hash[:8].upper()}"
        doc_title = title or Path(filename).stem.replace("_", " ").title()
        ref_base = citation_base or f"{doc_stem}-V{version}"

        # 1. Parse into sections
        sections: List[ParsedSection] = []
        if doc_type == DocumentType.PDF:
            sections = PDFKnowledgeParser.parse(file_bytes, filename)
        elif doc_type == DocumentType.DOCX:
            sections = DOCXKnowledgeParser.parse(file_bytes, filename)
        elif doc_type in (DocumentType.TXT, DocumentType.MARKDOWN):
            sections = TextKnowledgeParser.parse(file_bytes, filename)
        elif doc_type == DocumentType.JSON:
            sections = JSONKnowledgeParser.parse(file_bytes, filename)

        # 2. Chunk sections
        chunks = self.chunker.chunk_sections(
            sections=sections,
            document_id=doc_id,
            document_title=doc_title,
            citation_base=ref_base,
            trust_status=trust_status,
            medical_domain=medical_domain
        )

        # 3. Index chunks in Vector Store and BM25 Lexical index
        self.vector_store.add_chunks(chunks)
        self.retriever.sync_lexical_index(chunks)

        # 4. Save document record
        doc_record = MedicalKnowledgeDocument(
            document_id=doc_id,
            source_id=doc_stem,
            title=doc_title,
            source_organization=source_organization,
            publication_date=publication_date,
            document_version=version,
            document_type=doc_type,
            medical_domain=medical_domain,
            source_url=source_url,
            content_hash=content_hash,
            trust_status=trust_status,
            file_size_bytes=len(file_bytes),
            total_chunks=len(chunks)
        )
        self._documents[doc_id] = doc_record
        self._hash_to_doc_id[content_hash] = doc_id
        return doc_record

    def ingest_corpus_directory(self, dir_path: Path) -> int:
        """Scan and ingest all supported medical knowledge files in a directory."""
        count = 0
        p = Path(dir_path)
        if not p.exists() or not p.is_dir():
            return 0

        for file_path in p.glob("**/*"):
            if file_path.is_file() and file_path.suffix.lower() in (".pdf", ".docx", ".txt", ".md", ".json"):
                try:
                    file_bytes = file_path.read_bytes()
                    domain = "Aerospace Medicine"
                    if "cardiovascular" in file_path.name.lower() or "biomedical" in file_path.name.lower():
                        domain = "Cardiovascular Dynamics"
                    elif "protocol" in file_path.name.lower():
                        domain = "Mission Medical Protocols"
                    elif "psychological" in file_path.name.lower():
                        domain = "Operational Psychology"
                    elif "signal" in file_path.name.lower():
                        domain = "Physiological Signal Processing"

                    self.ingest_document(
                        file_bytes=file_bytes,
                        filename=file_path.name,
                        medical_domain=domain,
                        trust_status=TrustStatus.OFFICIAL_GUIDELINE
                    )
                    count += 1
                except Exception:
                    pass
        return count

    def delete_document(self, document_id: str) -> bool:
        """Remove document and its indexed chunks from ChromaDB and BM25 indexes."""
        if document_id in self._documents:
            doc = self._documents.pop(document_id)
            if doc.content_hash in self._hash_to_doc_id:
                del self._hash_to_doc_id[doc.content_hash]
            self.vector_store.delete_document(document_id)
            self.retriever.remove_document_chunks(document_id)
            return True
        return False

    def query(self, query: Union[str, RetrievalQuery], astronaut_id: Optional[str] = None) -> RAGGenerationResult:
        """Execute full RAG pipeline: retrieval -> grounded generation -> claim validation."""
        if isinstance(query, str):
            q_obj = RetrievalQuery(
                query_id=f"QRY-{abs(hash(query)) % 1000000:06d}",
                query_text=query,
                astronaut_id=astronaut_id
            )
        else:
            q_obj = query
            if astronaut_id and not q_obj.astronaut_id:
                q_obj.astronaut_id = astronaut_id

        passages, status = self.retriever.retrieve(q_obj)
        result = self.generator.generate(
            query=q_obj.query_text,
            passages=passages,
            retrieval_status=status
        )
        return result

    # -------------------------------------------------------------------------
    # Backwards-Compatibility API for PersonalHealthAgent & Legacy Tests
    # -------------------------------------------------------------------------
    def query_medical_evidence(
        self,
        query: str,
        collection: Optional[RAGCollection] = None,
        top_k: int = 3
    ) -> List[RAGEvidenceItem]:
        """Backward-compatible search method returning legacy RAGEvidenceItem objects."""
        q_obj = RetrievalQuery(
            query_id=f"LEGACY-{abs(hash(query)) % 1000000:06d}",
            query_text=query,
            top_k=top_k
        )
        passages, status = self.retriever.retrieve(q_obj)
        return [p.to_rag_evidence_item() for p in passages]

    def retrieve_approved_protocol(self, symptom_or_trigger: str) -> Optional[RAGEvidenceItem]:
        """Backward-compatible protocol retrieval returning authoritative protocol if matched."""
        results = self.query_medical_evidence(
            query=f"protocol emergency {symptom_or_trigger}",
            collection=RAGCollection.MISSION_MEDICAL_PROTOCOLS,
            top_k=1
        )
        if results and results[0].evidence_type == EvidenceType.APPROVED_MISSION_PROTOCOL:
            return results[0]
        return None
