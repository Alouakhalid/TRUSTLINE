# TRUSTLINE — PRIORITY 02: Medical Knowledge Retrieval-Augmented Generation (Medical RAG)
## System Architecture, Design Invariants, and Orchestration Specification

**Subsystem Status:** `IMPLEMENTED & END-TO-END VERIFIED`  
**Execution Timestamp:** 2026-11-12T15:30:00 UTC  
**Target Environment:** TRUSTLINE Edge Computing Node (macOS / Python 3.10 / SQLite Edge DB)  
**LangGraph Orchestration Topology:** 10-Node Linear Directed Acyclic Graph (DAG)  
**Primary Embeddings Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors)  
**Primary Retrieval Strategy:** Hybrid Vector Dense + BM25 Lexical + Protocol Precedence Boost  

---

## 1. Executive Overview & System Purpose

The **TRUSTLINE Medical Knowledge Retrieval-Augmented Generation (Medical RAG)** subsystem provides deterministic, evidence-grounded aerospace medical guidelines to the TRUSTLINE decision-support hierarchy. Operating inside an isolated deep-space edge deployment (such as an exploration vehicle or lunar habitat), TRUSTLINE cannot rely on uninterrupted high-bandwidth connectivity to Earth-based mission control or external medical databases.

Medical RAG serves as an authoritative clinical knowledge base that:
1. Ingests and structures mission medical protocols, emergency redlines, clinical clinical guidelines, and biomedical standards across heterogeneous formats (PDF, DOCX, TXT, JSON).
2. Performs hybrid dense-lexical retrieval with strict protocol precedence ranking, ensuring official flight surgeon directives take precedence over general clinical literature.
3. Enforces an impenetrable isolation barrier between general clinical guidelines and confidential astronaut medical records (`AST-...`), preventing medical identity confusion and privacy violations.
4. Generates structured, 5-part clinical responses governed by automated anti-hallucination claim validation and aerospace safety policies.
5. Integrates directly into the central LangGraph Supervisor orchestrator as a dedicated first-class workflow node (`medical_rag_node`), exposing verifiable evidence items (`EV-KNOW-*`) to the Supervisor Evidence Registry while guaranteeing zero mutation of live biosensor telemetry.

```
+--------------------------------------------------------------------------------------------------+
|                                    TRUSTLINE EDGE RUNTIME                                        |
|                                                                                                  |
|  +--------------------+        +---------------------+        +-------------------------------+  |
|  | Knowledge Sources  |  --->  | Multi-Format Parser |  --->  | Structure-Aware Chunker       |  |
|  | (PDF, DOCX, TXT)   |        | & Security Guard    |        | (Headings, Tables, Metadata)  |  |
|  +--------------------+        +---------------------+        +-------------------------------+  |
|                                                                               |                  |
|                                                                               v                  |
|  +--------------------------------------------------------------------------------------------+  |
|  |                                  HYBRID RETRIEVAL ENGINE                                   |  |
|  |  +-----------------------+   +----------------------+   +-------------------------------+  |  |
|  |  | Dense Vector Index    |   | BM25 Lexical Index   |   | Protocol Precedence Booster   |  |  |
|  |  | (all-MiniLM-L6-v2)    |   | (rank_bm25 Okapi)    |   | (+0.20 Official Guidelines)   |  |  |
|  |  +-----------------------+   +----------------------+   +-------------------------------+  |  |
|  |                              \          |           /                                      |  |
|  |                               v         v          v                                       |  |
|  |                        [ Reciprocal Fusion & Reranking ]                                   |  |
|  |                                         |                                                  |  |
|  |                                         v                                                  |  |
|  |                   [ Isolation Guard & Conflict Detector ]                                  |  |
|  +-----------------------------------------+--------------------------------------------------+  |
|                                            |                                                     |
|                                            v                                                     |
|  +--------------------------------------------------------------------------------------------+  |
|  |                              GROUNDED GENERATION & VALIDATION                              |  |
|  |  +-----------------------------------+   +-----------------------------------------------+ |  |
|  |  | 5-Part Structured Synthesizer     |   | Claim Grounding & Policy Validator            | |  |
|  |  | (Facts, Context, Uncertainty,    |   | (N-gram Claim Overlap, Prescription Filter,   | |  |
|  |  |  Citations, Missing Info)         |   |  Anti-Hallucination Guard)                    | |  |
|  |  +-----------------------------------+   +-----------------------------------------------+ |  |
|  +-----------------------------------------+--------------------------------------------------+  |
|                                            |                                                     |
|                                            v                                                     |
|  +--------------------------------------------------------------------------------------------+  |
|  |                        LANGGRAPH SUPERVISOR WORKFLOW (10 NODES)                            |  |
|  |  [intake] -> [input_val] -> [sensor_qual] -> [personal_health] -> [medical_rag]             |  |
|  |     -> [risk_assess] -> [evidence_val] -> [synthesis] -> [persistence] -> [response]       |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                            |                                                     |
|                                            v                                                     |
|  +--------------------------------------------------------------------------------------------+  |
|  |                   EVIDENCE REGISTRY: EV-KNOW-* & TELEMETRY IMMUTABILITY                    |  |
|  |                   (delta_HR = 0.0, delta_Resp = 0.0, Provenance Audited)                   |  |
|  +--------------------------------------------------------------------------------------------+  |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Non-Negotiable Architectural Constraints

The subsystem strictly adheres to the core system invariants:
1. **LangGraph Sole Orchestrator:** LangGraph is the single workflow orchestrator for the entire TRUSTLINE system. No secondary orchestrators, external agent loops, or conflicting graph dispatchers exist.
2. **Subsystem Preservation:** All Priority 01 components (Medical Document Integration, Ingestion Service, OCR pipeline, Evidence Registry, Human-in-the-Loop review) remain fully functional and intact.
3. **Comment Hygiene:** All Python files within `ai-engine/agents/supervisor/` and `ai-engine/agents/risk_assessment/` maintain strictly **zero `#` comments**. Documentation is expressed exclusively through clean code structure, type annotations, and docstrings.
4. **Data Privacy & Personal Isolation:** General medical knowledge queries never retrieve, expose, or correlate personal astronaut medical records (`AST-...`). Personal health records remain exclusively within the Patient Health Agent (PHA) and confirmed clinical document stores.
5. **Deterministic Telemetry Immutability:** Medical RAG operations are strictly side-effect-free regarding live biosensor telemetry. Retrieving clinical literature cannot mutate real-time heart rate, respiration rate, SpO2, or skin conductance measurements.

---

## 3. Subsystem Architecture & Component Breakdown

### 3.1 Multi-Format Ingestion Pipeline (`parsers.py`)
The ingestion pipeline processes raw knowledge documents from filesystem directories or mission payloads:
- **Supported Formats:**
  - `PDF`: Parsed via native PyMuPDF (`fitz`), capturing text blocks, bounding geometries, page numbers, and embedded heading styles. Scanned documents route to Groq Vision OCR if native text is absent.
  - `DOCX`: Parsed via `python-docx`, preserving hierarchical heading levels (`Heading 1` through `Heading 4`), bulleted lists, and structured tabular data cell-by-cell.
  - `TXT`: Ingested with encoding normalization (UTF-8 strict fallback to Latin-1) and paragraph boundary recognition.
  - `JSON`: Structured protocol specifications parsed into domain entities, preserving author, revision, jurisdiction, and trust flags.
- **Security Validation (`KnowledgeParserSecurityValidator`):**
  - **Path Traversal Defense:** Verifies that canonical paths (`os.path.realpath`) remain within permitted knowledge storage boundaries, rejecting attempts to access parent directories via `..` or symbolic links.
  - **Decompression Bomb Guard:** Enforces strict archive safety limits: uncompressed file size $\le 100\,\text{MB}$, compressed ratio $\le 10:1$, and total file count $\le 1,000$.
  - **File Size Verification:** Hard threshold of $50\,\text{MB}$ per raw document.

### 3.2 Structure-Aware Chunking Engine (`chunking.py`)
Standard naive fixed-length chunking destroys clinical context by slicing across therapeutic dosage tables, diagnostic criteria, and warning bullet points. The TRUSTLINE Structure-Aware Chunker implements:
- **Hierarchical Heading Tracking:** Traverses document sections, maintaining an active breadcrumb trail (e.g., `["EVA Guidelines", "Cardiovascular Red-Lines", "Tachycardia Intervention"]`).
- **Semantic Section Boundaries:** Splits text at natural semantic breaks (headings, horizontal rules, markdown tables, double newlines) rather than arbitrary byte offsets.
- **Configurable Token Windowing:** Enforces token constraints (`min_chunk_tokens=50`, `max_chunk_tokens=512`, `overlap_tokens=64`), preserving sentence integrity at chunk margins.
- **Table Preservation:** Markdown-formatted tables are kept intact within single chunks whenever possible; large tables are split along row boundaries with preserved header rows.
- **Chunk Metadata Enrichment:** Every chunk retains `chunk_id`, `document_id`, `document_title`, `section_hierarchy`, `page_number`, `token_count`, and `trust_status`.

### 3.3 Hybrid Retrieval Engine (`retrievers.py`)
The retrieval engine combines dense semantic search with sparse lexical matching and domain-specific trust weighting:
1. **Dense Vector Search:**
   - Embeds query and passages using `SentenceTransformerEmbeddingProvider` (`all-MiniLM-L6-v2`, 384 dimensions).
   - Computes cosine similarity between normalized query vector $\mathbf{q}$ and passage vectors $\mathbf{d}_i$:
     $$S_{\text{dense}}(\mathbf{q}, \mathbf{d}_i) = \frac{\mathbf{q} \cdot \mathbf{d}_i}{\|\mathbf{q}\| \|\mathbf{d}_i\|}$$
   - Filters candidates against a baseline similarity threshold ($S_{\text{dense}} \ge 0.25$).
2. **Sparse Lexical Search (BM25Okapi):**
   - Tokenizes and normalizes terms, computing term frequency-inverse document frequency scores via `rank_bm25.BM25Okapi`:
     $$\text{BM25}(\mathbf{q}, \mathbf{d}_i) = \sum_{t \in \mathbf{q}} \text{IDF}(t) \cdot \frac{f(t, \mathbf{d}_i) \cdot (k_1 + 1)}{f(t, \mathbf{d}_i) + k_1 \cdot \left(1 - b + b \cdot \frac{|\mathbf{d}_i|}{\text{avgdl}}\right)}$$
     with standard parameters $k_1 = 1.5, b = 0.75$. BM25 scores are min-max normalized to $[0, 1]$.
3. **Protocol Precedence Boost:**
   - In aerospace medicine, flight surgeon directives and operational red-lines take precedence over general textbooks. Chunks with `TrustStatus.OFFICIAL_GUIDELINE` (`MISSION_PROTOCOL`) receive an additive boost:
     $$\Delta_{\text{protocol}} = +0.20$$
4. **Hybrid Score Formulation:**
   - The final composite retrieval score balances dense semantics ($\alpha = 0.65$) and exact lexical terminology ($1 - \alpha = 0.35$):
     $$S_{\text{hybrid}} = \alpha \cdot S_{\text{dense}} + (1 - \alpha) \cdot S_{\text{lexical}} + \Delta_{\text{protocol}}$$
5. **Cross-Source Conflict Detection:**
   - Detects when retrieved passages present mutually exclusive clinical guidance (e.g., contrasting heart rate escalation thresholds). Conflicting items are flagged with `conflict_detected=True`, triggering evidentiary quarantine.

### 3.4 Personal Record Isolation Architecture
A core safety requirement is that general clinical queries must never access or reveal confidential astronaut records.
- **Isolation Filter:** The retriever analyzes all incoming queries with regex and semantic guards targeting astronaut identifiers (`\bAST-\w+\b`), vitals histories (`blood panel history`, `vitals log`), and confidential record markers.
- **Short-Circuit Enforcement:** If an isolation breach is detected:
  1. Retrieval immediately halts without querying the knowledge index.
  2. The query status is set to `RAGRetrievalStatus.ISOLATION_VIOLATION`.
  3. Zero passages are returned (`retrieved_passages = []`).
  4. An audit log security warning is emitted.
  5. The generation engine returns a safe refusal explaining that personal health records must be queried via authorized clinical review channels.

### 3.5 Grounded 5-Part Generation & Claim Validation (`generation.py`)
To prevent LLM hallucination and ensure auditability by flight surgeons, generated responses must strictly follow a 5-part structure:
1. **Retrieved Medical Facts:** Unambiguous statements extracted directly from verified source chunks.
2. **Clinical Interpretation & Operational Context:** Synthesized meaning applied to spaceflight physiology.
3. **Operational Uncertainty & Limitations:** Explicit documentation of what the evidence does not cover, physiological edge cases, and confidence boundaries.
4. **Source Citations & Provenance:** Exact document IDs, section breadcrumbs, and page references for every claim.
5. **Missing Information & Recommended Actions:** Identified data gaps and clinical telemetry needed from the astronaut.

**Automated Claim Grounding Validator (`ClaimGroundingValidator`):**
- Deconstructs generated statements into atomic clinical claims.
- Evaluates n-gram token overlap and semantic entailment against retrieved passage excerpts.
- Enforces aerospace safety rules:
  - Disallows ungrounded diagnostic assertions.
  - Disallows autonomous medication prescriptions without physician authorization.
- Computes overall grounding status: `FULLY_GROUNDED`, `PARTIALLY_GROUNDED`, or `UNGROUNDED_HALLUCINATION`.

---

## 4. LangGraph Supervisor 10-Node Workflow Integration

The TRUSTLINE central LangGraph orchestrator has been upgraded from a 9-node workflow to a 10-node linear state graph:

```
[intake]
   │
   ▼
[input_validation]
   │
   ▼
[sensor_quality] (SQA Agent)
   │
   ▼
[personal_health] (PHA Agent)
   │
   ▼
[medical_rag] (Medical Knowledge RAG Node - NEW)
   │
   ▼
[risk_assessment] (RAA Agent)
   │
   ▼
[evidence_validation] (Evidence Registry Compilation)
   │
   ▼
[final_synthesis] (Global Health Synthesis)
   │
   ▼
[persistence] (SQLite State Persistence)
   │
   ▼
[final_response] (API Delivery)
```

### Node Specification: `medical_rag_node`
- **Input State:** `SupervisorWorkflowState` containing `query`, `sensor_readings`, `astronaut_id`, and `execution_state`.
- **Execution Logic:**
  1. Starts high-resolution timer (`t_start = perf_counter()`).
  2. Formulates medical clinical query based on astronaut symptoms, active vitals alerts, or explicit query text.
  3. Executes hybrid retrieval against indexed medical protocols.
  4. Synthesizes grounded 5-part response.
  5. Computes elapsed time `medical_rag_execution_time_ms`.
  6. Returns updated state dictionary:
     - `medical_rag_result`: Complete retrieval and generation payload.
     - `workflow_timing`: Incremented with `medical_rag_execution_time_ms`.
     - `execution_state`: Retained as `SUCCESS` or set to `PARTIAL` if degraded.

### Evidence Registry Integration: `EV-KNOW-*`
In `evidence_validation_node`, `EvidenceRegistryService` indexes all retrieved medical knowledge chunks:
- **Evidence ID Format:** `EV-KNOW-{chunk_id}`
- **Source Agent:** `medical_knowledge_rag_service`
- **Domain:** `EvidenceDomain.CLINICAL_KNOWLEDGE`
- **Quarantine Logic:** If `conflict_detected=True`, evidence status is set to `ValidityStatus.CONFLICTING` and `is_quarantined=True`, preventing conflicting data from influencing automated risk scoring.
- **Provenance Chain:** Appends entry `{"agent": "medical_rag_agent", "status": "SUCCESS"}` to `final_supervisor_assessment.provenance_chain`.

---

## 5. Architectural Verification & Guarantees

| Invariant | Guarantee Description | Verification Mechanism | Status |
| :--- | :--- | :--- | :--- |
| **INV-01** | LangGraph is the sole workflow orchestrator. | StateGraph compilation inspection; zero secondary graph engines. | **VERIFIED** |
| **INV-02** | Telemetry Immutability ($\Delta\text{HR}=0.0$, $\Delta\text{Resp}=0.0$). | Test 05 in `test_medical_rag_supervisor_e2e.py`; pre/post telemetry hash match. | **VERIFIED** |
| **INV-03** | Personal Astronaut Record Isolation. | EVAL-09 & EVAL-15 benchmark tests; Test 04 in RAG supervisor suite. | **VERIFIED** |
| **INV-04** | Grounded 5-Part Generation Structure. | Section header validator; live Groq LLM verification script. | **VERIFIED** |
| **INV-05** | Conflict Detection & Evidentiary Quarantine. | Test 07 in `test_medical_rag_supervisor_e2e.py`; `is_quarantined=True`. | **VERIFIED** |
| **INV-06** | Graceful Degradation on RAG Failure. | Test 06 in `test_medical_rag_supervisor_e2e.py`; workflow completes successfully. | **VERIFIED** |
| **INV-07** | Strict Comment Hygiene (Zero `#` comments). | Python AST / line scanner over `supervisor/` and `risk_assessment/`. | **VERIFIED** |
