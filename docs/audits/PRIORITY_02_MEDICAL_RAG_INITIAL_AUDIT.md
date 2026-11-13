# TRUSTLINE — PRIORITY 02: Medical RAG Initial Architectural & Evidence Audit

**Audit Date:** 2026-11-12T18:15:00 UTC  
**Auditor:** Autonomous Verification & QA Engineering Agent  
**Target Environment:** macOS Darwin 26.5.2 (arm64) / Python 3.10.0rc2 (pre-release candidate) / pytest 9.1.1  
**Audit Scope:** Complete repository audit of Medical Knowledge RAG, P01 Medical Document Integration, Evidence Registry, LangGraph Supervisor, and evaluation assets.

---

## 1. Actual Files and Classes Inspected

### Medical RAG Subsystem (`ai-engine/agents/personal_health/rag/`)
- `schemas.py`:
  - `DocumentType`, `TrustStatus`, `RAGRetrievalStatus`, `GroundingStatus`
  - `MedicalKnowledgeDocument`, `MedicalChunk`, `RetrievalQuery`, `RetrievedPassage`, `RAGGenerationResult`
- `parsers.py`:
  - `KnowledgeParserSecurityValidator`: Path traversal (`os.path.realpath`), file size limit ($50\,\text{MB}$), zip decompression bomb guard ($<100\,\text{MB}$, $<1000$ files).
  - `PDFKnowledgeParser`: Native PyMuPDF (`fitz`) text and heading extraction with Groq Vision fallback for scanned images.
  - `DOCXKnowledgeParser`: `python-docx` parser extracting heading levels (`Heading 1`..`Heading 4`) and markdown tables.
  - `TextKnowledgeParser`, `JSONKnowledgeParser`, `KnowledgeDocumentParserFactory`.
- `chunking.py`:
  - `StructureAwareChunker`: Preserves heading breadcrumb paths, markdown table structures, sentence integrity, and token boundaries (`min_chunk_tokens=50`, `max_chunk_tokens=512`, `overlap_tokens=64`).
- `embeddings.py`:
  - `BaseEmbeddingProvider`, `SentenceTransformerEmbeddingProvider` (`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions), `MockEmbeddingProvider`.
- `storage.py`:
  - `MedicalKnowledgeVectorStore`: SQLite metadata store and in-memory numpy cosine similarity index.
- `vector_store.py`:
  - Legacy `MedicalVectorStore` with mock/in-memory collections.
- `retrievers.py`:
  - `BM25LexicalRetriever`: Sparse lexical search using `rank_bm25.BM25Okapi`.
  - `HybridMedicalRetriever`: Combines dense cosine similarity ($\alpha=0.65$), BM25 lexical ranking ($1-\alpha=0.35$), and protocol precedence boost ($+0.20$ for `OFFICIAL_GUIDELINE`). Contains regex privacy guard.
- `generation.py`:
  - `GroundedMedicalGenerator`: Assembles 5-part structured responses (1. Facts, 2. Interpretation, 3. Uncertainty, 4. Citations, 5. Missing Info).
  - `ClaimGroundingValidator`: N-gram token overlap evaluation against source chunks; screening against unauthorized prescription/diagnosis.
- `service.py`:
  - `MedicalKnowledgeRAGService`: Unified facade connecting ingestion, storage, retrieval, generation, and validation.
- `evaluation/benchmark.py`:
  - 15-case benchmark evaluation suite measuring P@K, Recall@K, MRR, nDCG@K, citation correctness, and latencies.

### Personal Health Agent & P01 Integration
- `ai-engine/agents/personal_health/services/rag_service.py`:
  - `MedicalRAGService`: Bridge delegating to `MedicalKnowledgeRAGService` with backwards-compatible `query_medical_evidence` and `retrieve_approved_protocol`.
- `ai-engine/agents/personal_health/repositories/medical_document_repository.py`:
  - `MedicalDocumentModel`: SQLite tracking for uploaded medical documents (`document_id`, `astronaut_id`, `file_hash`, `processing_status`).
  - `PendingMedicalRecordModel`: Extracted lab/clinical values (`record_id`, `document_id`, `astronaut_id`, `test_name`, `extracted_value`, `normalized_value`, `original_unit`, `collection_date`, `validation_status`, `review_status`, `reviewed_by`).
  - `MedicalDocumentRepository`: Methods `save_document`, `save_extracted_records`, `get_pending_records`, `get_confirmed_records`, `update_record_review`, `get_document_by_hash`.
- `ai-engine/agents/personal_health/services/document_ingestion_service.py`:
  - Document upload, SHA-256 deduplication, PyMuPDF/docx extraction, normalization, and pending record creation.
- `ai-engine/agents/personal_health/services/medical_record_review_service.py`:
  - Clinical review transitions (`CONFIRM`, `EDIT`, `REJECT`).

### Supervisor Agent & Orchestration
- `ai-engine/agents/supervisor/schemas/state.py`:
  - `SupervisorWorkflowState`: Contains `incoming_request`, `astronaut_id`, `document_paths`, `medical_documents`, `pending_medical_records`, `confirmed_medical_records`, `medical_rag_result`.
- `ai-engine/agents/supervisor/schemas/assessment.py`:
  - `WorkflowTimingBreakdown`: Contains `medical_rag_execution_time_ms`.
  - `FinalSupervisorAssessment`: Contains `medical_rag_summary`, `provenance_chain`.
  - `EvidenceRegistryItem`: Unified evidence model (`evidence_id`, `source_agent`, `domain`, `metric_name`, `observed_value`, `validity_status`, `is_quarantined`, `quarantine_reason`, `provenance`).
- `ai-engine/agents/supervisor/services/evidence_registry_service.py`:
  - Compiles `EV-SQ-*`, `EV-PHY-*`, `EV-SYM-*`, `EV-MED-CONFIRMED-*`, `EV-DOC-PENDING-*`, and `EV-KNOW-*`. Quarantines conflicting knowledge and unverified astronaut records.
- `ai-engine/agents/supervisor/services/medical_rag_integration.py`:
  - `MedicalRAGIntegrationService`: Bridge executing RAG queries for Supervisor state.
- `ai-engine/agents/supervisor/workflow/nodes.py`:
  - `medical_rag_node`: Executes between `personal_health` and `risk_assessment`, timing telemetry instrumentation, failure containment.
- `ai-engine/agents/supervisor/workflow/graph.py`:
  - Linear 10-node StateGraph: `intake -> input_validation -> sensor_quality -> personal_health -> medical_rag -> risk_assessment -> evidence_validation -> final_synthesis -> persistence -> final_response`.
- `ai-engine/agents/supervisor/tests/test_medical_rag_supervisor_e2e.py`:
  - 7 E2E tests validating graph execution, registry compilation, assessment contracts, telemetry immutability, isolation rejection, error handling, and conflict quarantine.

---

## 2. Existing Architecture and Execution Flow

```
[ Astronaut / System Request ]
             |
             v
   [ 1. Supervisor Intake ] (SupervisorWorkflowRunner)
             |
             v
   [ 2. Input Validation ]
             |
             v
   [ 3. Sensor Quality Agent (SQA) ] -> EV-SQ-*
             |
             v
   [ 4. Personal Health Agent (PHA) ] -> EV-PHY-*, EV-SYM-*
      - Ingests uploaded document_paths
      - Creates PendingMedicalRecordModel (PENDING_REVIEW) -> EV-DOC-PENDING-*
      - Loads ConfirmedMedicalFinding (CONFIRMED) -> EV-MED-CONFIRMED-*
             |
             v
   [ 5. Medical Knowledge RAG Node ] (NEW P02)
      - Formulates query from input_data.text_query / symptoms
      - Queries MedicalKnowledgeRAGService
      - Returns medical_rag_result
             |
             v
   [ 6. Risk Assessment Agent (RAA) ]
             |
             v
   [ 7. Evidence Validation & Registry Compilation ]
      - Compiles EV-SQ-*, EV-PHY-*, EV-SYM-*, EV-MED-CONFIRMED-*, EV-DOC-PENDING-*, EV-KNOW-*
      - Scientific quarantine audit
             |
             v
   [ 8. Final Synthesis ]
      - Embeds medical_rag_summary & provenance_chain
             |
             v
   [ 9. Persistence & 10. Final Response ]
```

---

## 3. Current Providers, Vector Storage, and Configurations

1. **Embedding Provider:**
   - Active: `SentenceTransformerEmbeddingProvider` utilizing `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, normalized embeddings).
   - Fallback: `MockEmbeddingProvider` (deterministic pseudo-random unit vectors based on text SHA-256).
2. **Vector Storage:**
   - Active: `MedicalKnowledgeVectorStore` using SQLite for chunk and document metadata persistence, and in-memory numpy matrices for dense cosine similarity computations.
3. **Lexical Retrieval:**
   - `BM25Okapi` (`rank_bm25`) indexing tokenized chunk contents.
4. **OCR & External Provider:**
   - Groq Cloud API: `llama-3.3-70b-versatile` for grounded generation; `qwen/qwen3.8-27b` for vision OCR. Strictly zero local non-Groq OCR providers.

---

## 4. Current Retrieval, Generation, and P01 Integration Behavior

### What is currently working:
- Ingestion of general medical guidelines (PDF, DOCX, TXT, JSON) into `knowledge_base/` with SHA-256 deduplication and security checks.
- Structure-aware chunking preserving tables and section breadcrumbs.
- Hybrid dense-BM25 retrieval with protocol boost ($+0.20$ for official guidelines).
- Grounded 5-part answer formatting with claim-to-chunk token overlap validation.
- 10-node LangGraph orchestration and Evidence Registry indexing (`EV-KNOW-*`).
- Telemetry immutability ($\Delta \text{HR} = 0.0, \Delta \text{Resp} = 0.0$).

---

## 5. Confirmed Architectural and Evidence-Integrity Gaps

### GAP 1: Disconnect Between P01 Confirmed Medical Records and Medical RAG
- **Current State:** `MedicalKnowledgeRAGService` ONLY queries the static `knowledge_base/` general medical literature. It has **no mechanism to retrieve an astronaut's confirmed historical medical records** (lab reports, blood tests, clinical summaries) stored in `MedicalDocumentRepository`!
- **Severity:** `CRITICAL`.
- **Requirement:** Phase 1 and Phase 3 require: *"P01 confirmed medical records are retrievable by Medical RAG... Medical RAG must respect the P01 document-review lifecycle."*

### GAP 2: Naive Astronaut Isolation Pattern Rejection
- **Current State:** `retrievers.py` has a blanket regex `r"\bAST-\w+\b"` that immediately triggers `ISOLATION_VIOLATION` whenever any query mentions an astronaut ID (e.g. `AST-001`).
- **Severity:** `CRITICAL`.
- **Impact:** Legitimate authorized clinical inquiries for an astronaut's confirmed records (e.g., *"What is astronaut AST-001's latest hemoglobin level?"* or *"Does AST-001 have a history of tachycardia in confirmed records?"*) are unconditionally rejected!
- **Requirement:** Retrieval must be **strictly scoped to the session's authenticated astronaut ID**. If the session is for `AST-001`:
  - Inquiries for `AST-001`'s confirmed records are **permitted and retrieved with complete provenance**.
  - Cross-astronaut inquiries (e.g., asking for `AST-002` while session is `AST-001`) must be **strictly rejected as a cross-astronaut isolation violation**.
  - Missing/Unknown astronaut identity (`AST-UNKNOWN`) must produce an explicit safe abstention and never fall back to `AST-001` or another astronaut.

### GAP 3: Document Status Eligibility Lifecycle Enforcement
- **Current State:** There is no explicit lifecycle gate checking document status during RAG retrieval of clinical records.
- **Severity:** `HIGH`.
- **Requirement:**
  - `CONFIRMED`: Eligible for medical answers (subject to astronaut identity and provenance).
  - `PENDING_REVIEW`: Ineligible for medical answers (quarantined).
  - `REJECTED`: Completely excluded.
  - `QUARANTINED` / `CONFLICTING_EXTRACTION`: Completely excluded from trusted medical answers.
  - Unknown identity: Must never be retrieved under AST-001 or any other astronaut.

### GAP 4: Missing Provenance Fields in Retrieved Passages
- **Current State:** `RetrievedPassage` schema does not store `astronaut_id`, `document_hash`, `evidence_id`, `review_status`, `source_timestamp`, or `ingestion_timestamp`.
- **Severity:** `MEDIUM`.
- **Requirement:** Full provenance chain must be preserved so that answers and Evidence Registry items link back to the exact physical source.

### GAP 5: Grounded Answer Separation Between Historical Records and Live Telemetry
- **Current State:** The response generator does not explicitly distinguish whether a fact originated from a historical lab document vs general clinical guidelines vs live biosensor telemetry.
- **Severity:** `MEDIUM`.
- **Requirement:** Generated answers must explicitly distinguish historical laboratory records from current telemetry, identify conflicting records, and state when evidence is insufficient without interpreting absence as normal.

---

## 6. Components That Should Remain Unchanged

1. **LangGraph Supervisor Graph Topology:** The 10-node linear StateGraph is correct, stable, and satisfies the single orchestrator constraint.
2. **Comment Hygiene Invariant:** Strictly 0 `#` comments in `ai-engine/agents/supervisor/` and `ai-engine/agents/risk_assessment/`.
3. **P01 Core Ingestion & Review Pipeline:** `DocumentIngestionService`, `MedicalDocumentRepository`, `MedicalRecordReviewService`, and SQLite database tables remain the single source of truth for P01 documents. No secondary database will be created.
4. **General Knowledge Corpus & Chunker:** `StructureAwareChunker`, `KnowledgeParserSecurityValidator`, and multi-format parsers (PDF, DOCX, TXT, JSON) are working well and should be preserved.
5. **Existing Regression Tests:** All 360 baseline + 46 stress = 406 existing tests must be preserved and pass without regression.

---

## 7. Audit Conclusion & Remediation Roadmap

The Medical RAG subsystem has strong foundational components for general literature retrieval, but requires critical hardening to:
1. Integrate P01 confirmed clinical documents into the RAG retrieval scope.
2. Replace the naive regex isolation guard with robust server-side astronaut identity scoping and cross-astronaut isolation defense.
3. Enforce the P01 review lifecycle (CONFIRMED eligible, PENDING/REJECTED/QUARANTINED excluded).
4. Preserve full evidence provenance and historical telemetry separation in generated answers.
5. Provide comprehensive test coverage across all scenarios specified in Phase 4 (Eligibility, Retrieval Quality, Grounding, and Failure Recovery).
