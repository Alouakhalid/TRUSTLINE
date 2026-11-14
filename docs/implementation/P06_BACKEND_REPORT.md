# P06 Backend Report — Mission API Boundary

**Status:** COMPLETE (P06 scope)
**Verified:** 2026-11-14
**Final suite:** 44/44 backend tests passing in 17.47 s (single real LOCAL_ONLY Supervisor invocation)
**Baseline regression:** 510 passed / 4 failed in 27:48 (`/tmp/trustline_baseline_p06.log`, `BASELINE_EXIT=1`) — the 4 failures were the batch-1 DB-seam bug, fixed; all 510 ai-engine stack tests passed unchanged.

---

## 1. Progression

| Slice | Delivered | Evidence |
|---|---|---|
| Initial application boundary | SQLite store, scrypt hashing, expiring HMAC bearer tokens, role-bearing identities, Demo Mode `is_demo` partition, persistent chat, scoped agent memory, audit events | `test_application_api.py`, `test_memory_persistence.py` |
| Batch 1 (governance) | RBAC dependencies, additive migrations, chat session management, memory governance (versioned corrections, delete, filtering, concurrency), admin APIs, sync API exposure, connectivity monitors | 28/28 tests in 4.02 s |
| Batch 2 (real-time + real workflows) | Telemetry ingestion + WebSocket, radiation gateway, medical document gateway, Supervisor gateway, assessments endpoint with Workflow C/D wiring, shared audit/mode modules | 44/44 tests in 17.47 s |

## 2. What was built

### 2.1 Persistence (`backend/database/store.py`)
Dependency-light SQLite store used at spacecraft edge and in tests. Every domain record carries `is_demo`; queries always filter on it. This phase added an additive migration (`telemetry_packets`, `radiation_packets`, `assessments` + scope indexes) and a `configure(path)` seam that closes/recreates the in-memory keeper connection — the correct way for tests and restarts to re-point the store. (Rebinding `store.path` directly was the root cause of 4 baseline failures: a `:memory:` keeper left every new connection on an empty database, and stale keepers leaked `UNIQUE` collisions across tests.)

### 2.2 Identity & RBAC (`backend/auth/*`)
`current_user`, `require_privileged` (officer+admin), `require_administrator`, and a shared `demo_mode` header dependency (`X-Trustline-Mode`). Roles come only from signed tokens. `backend/services/audit.py` records events with actor id/role for both partitions; `app.audit()` delegates to it so mounted routers and core routes share one recorder.

### 2.3 Real-time telemetry (`backend/services/telemetry.py`)
Packet framing mirrors the simulator's `TelemetryPacket`; CRC32 is computed with the **same algorithm as the simulator**. Ingestion enforces checksum verification (tampered frames stored and flagged `checksum_ok=false`, timestamps preserved verbatim), duplicate rejection by `packet_id`, and per-astronaut/per-session/per-sensor sequence states `OK / GAP / DUPLICATE / OUT_OF_ORDER`. `TelemetryBroadcaster` fans out accepted packets to authorized WebSocket subscribers with a timeout-drop backpressure policy (slow consumers are dropped and counted, never stall ingestion).

### 2.4 Environmental radiation (`backend/services/radiation_gateway.py`)
Separate table, separate routes, NASA-STD-3001 Vol 1 Rev C limits **imported from the existing `nasa_standards.py`** (never restated). Privileged-only ingest; duplicate packets are reported, not overwritten; non-negative dose validation; demo isolation. Radiation is never merged into physiological telemetry or ML feature vectors.

### 2.5 Medical document gateway (`backend/api/documents.py`)
RBAC boundary over the **existing ai-engine pipeline** (PyMuPDF native text extraction for PDFs, python-docx for DOCX — no Tesseract/PaddleOCR/EasyOCR anywhere). Astronauts upload/read only their own documents; process/retry/review/pending are privileged; the reviewer identity on every review is overwritten with the token identity (a client-supplied `reviewer_id` is ignored — test-verified). A deployment seam (`configure_document_stack`) rebinds the ai-engine SQLAlchemy engine in place (`reconfigure_engine()` + `SessionFactory.configure(bind=…)`, identity preserved) and re-creates services against temporary directories for tests. Text PDFs extract with **no OCR call and no network access** in tests.

### 2.6 Supervisor gateway (`backend/services/supervisor_gateway.py`)
Converts an authorized request into a real `SupervisorRequest` for the existing `SupervisorWorkflowRunner` (LangGraph, the sole orchestrator — no CrewAI, no duplicated orchestration logic). The API boundary defaults `AI_ROUTER_MODE` to `LOCAL_ONLY` (override: `TRUSTLINE_AI_ROUTER_MODE`), so a reply never stalls on misconfigured or unbillable cloud providers and **no credentials are consumed in tests**. All reported provider/agent statuses are exactly what the workflow produced; import or invocation failures return truthful error states, never invented text. Measured: ~10–12 s per LOCAL_ONLY run (first call includes model warm-up) vs 78 s with live cloud retries.

### 2.7 Assessments endpoint (Workflow C/D wiring)
`POST /assessments` runs the real workflow and: injects recent CONFIRMED/LIVE PHA+RAA memories into the mission context (`authorized_memories_used`), persists the assessment with evidence count, appends an AGENT message with evidence citations to the referenced chat session, and writes a 24-hour LIVE PHA memory with assessment provenance. Chat message posting stays persistence-first (no model invocation on the chat route) — the deliberate split keeps replies non-blocking and keeps the Supervisor as the single point of AI synthesis.

### 2.8 Connectivity, sync, administration
Independent connectivity probes (database/DNS/network/local-AI each judged separately; `error_type` only, no internals leaked). Sync queue API with claim/success/failure/resolve and explicit `409` conflicts (never silently overwritten). Admin users list (password hashes never serialized) and audit log query.

## 3. Test evidence (all passing, this working tree)

| Suite | # | Covers |
|---|---|---|
| `test_application_api.py` | 3 | health/auth, chat persistence + identity isolation, demo separation |
| `test_rbac.py` | 3 | deny-by-default roles, officer-privileged memory, admin-only user list |
| `test_chat_sessions.py` | 5 | enrichment, rename/archive/search, delete cascade, ownership 404s, restart survival |
| `test_memory_governance.py` | 6 | version bumps, CONFIRMED privilege rule, filtering, delete, cross-astro 403, 10 concurrent writers → version 11 |
| `test_memory_persistence.py` | 1 | restart persistence, namespace + astronaut scoping |
| `test_sync_api.py` | 3 | admin-only, claim→success/failure, 409 conflict |
| `test_connectivity.py` | 4 | DB failure distinct, DNS≠network both directions, admin endpoint |
| `test_telemetry.py` | 5 | CRC32/tamper, dup/gap/out-of-order, isolation, demo isolation, WS auth/broadcast/ingest |
| `test_radiation_api.py` | 4 | NASA limits, privileged ingest, duplicate reporting, demo isolation |
| `test_documents_gateway.py` | 4 | real PDF+DOCX upload→extract→review→confirm, RBAC, demo refusal 403 |
| `test_assessments_supervisor.py` | 3 | one real Supervisor run (5 agent statuses, 6 evidence refs, citations, 24h LIVE memory), RBAC, demo isolation |
| **Total** | **44** | **17.47 s** |

## 4. Design decisions of record

1. **`store.configure()` instead of `store.path` rebinding** — closes/recreates the `:memory:` keeper; eliminates cross-test contamination without weakening any test.
2. **`AI_ROUTER_MODE=LOCAL_ONLY` at the API boundary** — deterministic default; cloud paths exist behind an explicit operator override (`TRUSTLINE_AI_ROUTER_MODE=HYBRID`). Never flipped to cloud in tests.
3. **Chat = persistence-first; `/assessments` = real workflow** — the Supervisor is invoked exactly where a run is requested, and its reply lands back in chat with evidence citations.
4. **Demo document operations refused (`403`), not faked** — the ai-engine edge DB has no demo partition; refusal is honest and documented rather than a silent bypass.
5. **WS token via query parameter** — browsers cannot set headers on WebSocket opens; documented and test-covered (4401/4403 close codes).
6. **Additive-only schema changes** — three new tables + indexes; no column drops or type changes anywhere.
7. **Supervisor availability is truthful** — `is_available()`/`unavailability_reason()` drive a `503` with the real import error instead of a stubbed success.

## 5. Known limitations (honest)

- Document store demo partition absent → demo-mode document operations are refused (§2.5); operational records are never written from demo requests.
- WebSocket broadcast between **separate** HTTP requests (different event loops in `TestClient`) is not observable in-process; the WS `ingest` command exists so subscribe→ingest→broadcast is exercised in one loop. Production deployment uses a single running loop, where cross-request broadcasts work.
- Assessment runs are synchronous (~10–12 s LOCAL_ONLY first call); no background job/queue yet — acceptable for mission-edge single-user flows, noted for P09.
- Auth still needs production secret management and refresh/revocation policy before deployment (unchanged from the initial slice report).
- One real Supervisor invocation per `POST /assessments` means the endpoint requires the local model stack present; otherwise `503` with the true reason.

## 6. Files created / modified this phase

| File | Change |
|---|---|
| `backend/api/app.py` | MODIFIED — telemetry REST+WS, radiation, assessments, documents mount; shared audit/mode |
| `backend/services/telemetry.py` | CREATED |
| `backend/services/supervisor_gateway.py` | CREATED |
| `backend/services/radiation_gateway.py` | CREATED |
| `backend/services/audit.py` | CREATED |
| `backend/services/integrations.py` | CREATED |
| `backend/services/connectivity.py` | CREATED (batch 1) |
| `backend/services/mission_services.py` | MODIFIED (chat + memory governance) |
| `backend/auth/rbac.py`, `backend/auth/modes.py` | CREATED |
| `backend/database/store.py` | MODIFIED — additive tables + `configure()` seam |
| `backend/api/documents.py` | CREATED |
| `ai-engine/agents/personal_health/repositories/base.py` | MODIFIED — additive `reconfigure_engine()`/`get_engine_for_url()` |
| `backend/tests/*` | 11 suites, 44 tests |
| `docs/implementation/TRUSTLINE_API_REFERENCE.md` | CREATED |
| `docs/implementation/TRUSTLINE_MASTER_TASK_TRACKER.md` | UPDATED — 6.1–6.12 VERIFIED with evidence; baseline recorded |

Pre-existing modified tracked files (41) were preserved untouched; nothing was committed during this phase.
