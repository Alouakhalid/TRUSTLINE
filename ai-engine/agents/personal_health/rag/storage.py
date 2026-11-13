"""Vector store wrapper managing ChromaDB index and metadata for medical knowledge chunks."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import chromadb
from chromadb.config import Settings

from .schemas import MedicalChunk, TrustStatus
from .embeddings import BaseEmbeddingProvider, get_embedding_provider

class MedicalKnowledgeVectorStore:
    """Manages dense vector storage and similarity search for medical knowledge."""

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        collection_name: str = "trustline_medical_knowledge"
    ):
        self.persist_dir = persist_dir
        self.embedding_provider = embedding_provider or get_embedding_provider("auto")
        self.collection_name = collection_name
        self._init_chroma()

    def _init_chroma(self):
        try:
            if self.persist_dir:
                p = Path(self.persist_dir)
                p.mkdir(parents=True, exist_ok=True)
                self.client = chromadb.PersistentClient(path=str(p))
            else:
                self.client = chromadb.Client()

            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize ChromaDB client: {str(exc)}") from exc

    def add_chunks(self, chunks: List[MedicalChunk]) -> int:
        """Embed and index medical chunks in ChromaDB idempotently."""
        if not chunks:
            return 0

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        texts_to_embed: List[str] = []

        for c in chunks:
            ids.append(c.chunk_id)
            documents.append(c.content)
            texts_to_embed.append(c.content)
            metadatas.append({
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "section_title": c.section_title or "General",
                "page_number": c.page_number if c.page_number is not None else -1,
                "chunk_index": c.chunk_index,
                "citation_reference": c.citation_reference,
                "trust_status": c.trust_status.value if hasattr(c.trust_status, "value") else str(c.trust_status),
                "medical_domain": c.medical_domain,
                "heading_hierarchy_json": json.dumps(c.heading_hierarchy)
            })

        # Generate dense embeddings
        embeddings = self.embedding_provider.embed_batch(texts_to_embed)

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        return len(chunks)

    def delete_document(self, document_id: str) -> int:
        """Remove all indexed chunks belonging to a specific document ID."""
        try:
            res = self.collection.get(where={"document_id": document_id})
            ids_to_del = res.get("ids", [])
            if ids_to_del:
                self.collection.delete(ids=ids_to_del)
            return len(ids_to_del)
        except Exception:
            return 0

    def query_dense(
        self,
        query_text: str,
        top_k: int = 5,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[MedicalChunk, float]]:
        """Execute dense vector similarity query and return ranked (chunk, score) pairs."""
        if self.collection.count() == 0:
            return []

        q_emb = self.embedding_provider.embed_text(query_text)
        kwargs: Dict[str, Any] = {
            "query_embeddings": [q_emb],
            "n_results": min(top_k, self.collection.count()),
            "include": ["documents", "metadatas", "distances"]
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = self.collection.query(**kwargs)
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        scored: List[Tuple[MedicalChunk, float]] = []
        for cid, doc_text, meta, dist in zip(ids, docs, metas, distances):
            # Cosine distance to similarity: dist is in [0, 2] where 0 is identical
            similarity = max(0.0, 1.0 - float(dist))
            
            page_val = meta.get("page_number", -1)
            page_num = page_val if page_val != -1 else None
            hierarchy_raw = meta.get("heading_hierarchy_json", "[]")
            try:
                hierarchy = json.loads(hierarchy_raw)
            except Exception:
                hierarchy = []

            chunk = MedicalChunk(
                chunk_id=cid,
                document_id=meta.get("document_id", "UNKNOWN"),
                section_title=meta.get("section_title", "General"),
                heading_hierarchy=hierarchy,
                page_number=page_num,
                chunk_index=meta.get("chunk_index", 0),
                content=doc_text,
                citation_reference=meta.get("citation_reference", ""),
                trust_status=TrustStatus(meta.get("trust_status", TrustStatus.OFFICIAL_GUIDELINE.value)),
                medical_domain=meta.get("medical_domain", "Aerospace Medicine")
            )
            scored.append((chunk, round(similarity, 4)))

        return scored

    def get_chunk_count(self) -> int:
        return self.collection.count()

    def clear(self):
        self.client.delete_collection(self.collection_name)
        self._init_chroma()
