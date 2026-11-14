# TRUSTLINE API Reference

**Service:** `TRUSTLINE Mission API` — `backend/api/app.py` (FastAPI), **version 0.2.0**
Generated from the live `openapi.json` of the unified application. Every endpoint below is exercised by the backend test suite (`backend/tests/`, 44 passing tests as of this revision).

---

## 1. Conventions

### 1.1 Authentication

All protected routes use **Bearer tokens** from `POST /auth/login`:

```
Authorization: Bearer <access_token>
```

Tokens are signed (HMAC) and carry `sub` (user id), `role`, and (for astronauts) `astronaut_id`. Unauthenticated calls return `401 {"detail": "Bearer token required"}`.

### 1.2 Demo / operational mode

A request header selects the data partition:

```
X-Trustline-Mode: operational   # default
X-Trustline-Mode: demo          # isolated demo partition
```

Anything other than `operational`/`demo` → `400`. Demo rows are stored with `is_demo=1` and **never** appear in operational reads (enforced in every SQL statement, proven per area in tests). One documented exception: **medical document operations are refused in demo mode with `403`** — the underlying ai-engine document store does not yet have a demo partition, and refusing is safer than silently writing operational records (see §5.4).

### 1.3 Role-based access

| Role | Scope |
|---|---|
| `ASTRONAUT` | Own identity only: own telemetry, own memories, own documents, own assessments, own chat sessions |
| `MEDICAL_OFFICER` | Privileged clinical workflows for any astronaut; cannot administer users/sync |
| `ADMINISTRATOR` | Everything, including user administration, audit log, and sync operations |

Violations return `403` with an explicit detail message. Role is taken from the signed token, never from the request body (verified for document review, where a client-supplied `reviewer_id` is ignored).

### 1.4 Errors

- `400` bad filter/value, `401` missing/invalid token, `403` RBAC or demo refusal, `404` unknown resource, `409` sync conflict, `422` Pydantic validation (FastAPI standard body), `500`/`503` truthful failure states.
- Error payloads **never leak stack traces or exception internals**; connectivity probes report `error_type` only (test-asserted).

---

## 2. System & Health

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | — | Liveness. Returns `{"status": "ok"}` + service metadata |
| GET | `/` | — | API index |
| GET | `/admin/connectivity` | ADMIN | Independent probes: `database`, `dns`, `network`, `local_ai` each with own `status`/`latency_ms`/`error_type`; summary flags `offline` truthfully. DNS failure ≠ network failure (test-asserted) |

---

## 3. Identity (`/auth`)

| Method | Path | Auth | Body / Query | Success |
|---|---|---|---|---|
| POST | `/auth/register` | — | `{username, password, role, astronaut_id?}` (`role` ∈ ASTRONAUT / MEDICAL_OFFICER / ADMINISTRATOR) | `201` user record; **`password_hash` is never serialized** |
| POST | `/auth/login` | — | `{username, password}` | `200` `{access_token, token_type, user}` |
| GET | `/auth/me` | Bearer | — | `200` current identity from the token |

---

## 4. Chat (`/chat`)

Sessions are astronaut-bound for `ASTRONAUT` users; privileged roles manage any session.

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/chat/sessions` | Bearer | `201` `{id, title, session_status, …}` |
| GET | `/chat/sessions` | Bearer | Query `q` (search title), `session_status` (`ACTIVE`/`ARCHIVED`; archived hidden by default), `limit`. Enriched rows: `message_count`, `latest_message_preview`, `updated_at` |
| GET | `/chat/sessions/{session_id}` | Bearer | `200` session + ownership enforced |
| PATCH | `/chat/sessions/{session_id}` | Bearer | Rename (`title`), archive/restore (`session_status`) |
| DELETE | `/chat/sessions/{session_id}` | Bearer | `204`; removes the session and its messages |
| GET | `/chat/sessions/{session_id}/messages` | Bearer | Ordered messages; each carries `citations[]` (evidence refs on AGENT messages) |
| POST | `/chat/sessions/{session_id}/messages` | Bearer | `{content}` → `201` persisted USER message. Persistence-first: no model invocation on this route (see `/assessments` for the real workflow run) |

---

## 5. Agent Memory (`/memory`)

Namespaces: `SQA`, `PHA`, `RAA`, `MEDICAL_RAG` (anything else → `400`).

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/memory` | Bearer | `201` `{astronaut_id, namespace, content, verification_status, provenance, long_term, ttl_hours?}`. `verification_status` ∈ CONFIRMED / PENDING / REJECTED / QUARANTINED / HISTORICAL / LIVE. TTL sets `expires_at`; expired entries are hidden unless `include_expired=true` |
| GET | `/memory/{astronaut_id}/{namespace}` | Bearer | Filters: `verification_status` (unknown → `400`), `long_term`, `include_expired`, `limit` (`<1` → `422`) |
| PATCH | `/memory/{memory_id}` | Bearer | Versioned correction: bumps `version`, keeps audit history. `CONFIRMED` status changes require a privileged role |
| DELETE | `/memory/{memory_id}` | Bearer | `204`; retention delete, audit recorded |

Isolation: astronauts read/write **their own** memories only (cross-astronaut → `403`). Concurrent updates are safe (last-write-wins with version increments; 10 concurrent writers → version 11, test-verified).

---

## 6. Physiological Telemetry (`/telemetry`)

Packets mirror the simulator's `TelemetryPacket` framing. CRC32 verification uses the **same algorithm as the simulator** (`sensor_type:seq:ts:channels`). Allowed sensors: `ECG, PPG, HR, SPO2, SKIN_TEMP, CORE_TEMP, EDA, RESPIRATION, ACCELEROMETER, GYROSCOPE`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/telemetry/packets` | Bearer | `{astronaut_id, packets[1..500]}` → `202` report: `accepted`, `duplicates`, `checksum_failures`, `gaps`, `out_of_order`, `results[].state` ∈ OK / GAP / DUPLICATE / OUT_OF_ORDER. Corrupted frames are stored and **flagged** (`checksum_ok=false`), timestamps preserved verbatim. All-all-invalid batch → `422` |
| GET | `/telemetry/latest/{astronaut_id}` | Bearer | Latest packet per sensor; `sensor_type` filter (unknown → `400`) |
| GET | `/telemetry/history/{astronaut_id}` | Bearer | `sensor_type`, `limit` (1–1000, else `422`) |

`WS /ws/telemetry/{astronaut_id}?token=<access_token>`
Browsers cannot set headers on WebSocket opens, so the signed token is a **query parameter**. No/invalid token → close `4401`; astronaut subscribing to another astronaut's feed → close `4403`. Client frames: `"ping"` → `{"type":"pong"}`; JSON command `{"command":"ingest","packets":[…],"mode":"demo"|"operational"}` → `{"type":"ingest_report", …}` followed by one `{"type":"telemetry_packet", …}` broadcast per stored packet. Slow/dead subscribers are dropped by timeout, never block ingestion.

---

## 7. Environmental Radiation (`/radiation`)

**Architectural rule:** radiation is environmental instrumentation with its own table and routes — it is *never* merged into physiological telemetry or ML feature vectors.

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/radiation/packets` | Privileged | `201`. Fields: `packet_id`, `timestamp_epoch_ms`, `dose_rate_microgy_h`, `equivalent_dose_rate_msv_h`, `cumulative_mission_dose_msv`, `spe_active`, `spe_flux_pfu`, `shielding_thickness_g_cm2`, `alert_level` ∈ NOMINAL / ADVISORY / WARNING / ALARM. Negative doses → `422`. Duplicate `packet_id` → reported `{"stored": false, "duplicate": true}` (never silently overwritten) |
| GET | `/radiation/latest` | Bearer | Latest packet + NASA limit table |
| GET | `/radiation/history` | Bearer | `limit` (1–1000) |
| GET | `/radiation/limits` | — | NASA-STD-3001 Vol 1 Rev C dose limits, **imported from the existing `nasa_standards.py` module** (never restated) |

---

## 8. Supervisor Assessments (`/assessments`)

Runs the **real existing LangGraph Supervisor workflow** (the sole orchestrator) via `backend/services/supervisor_gateway.py`. Provider routing at the API boundary defaults to `AI_ROUTER_MODE=LOCAL_ONLY` (override with `TRUSTLINE_AI_ROUTER_MODE`); the response reports the actual `router_mode` used.

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/assessments` | Bearer | `201` payload: `assessment_id`, `provider_status` (`SUPERVISOR_COMPLETED` or truthful `SUPERVISOR_FAILED` + error), `completion_status`, `overall_risk`, `overall_confidence`, `astronaut_facing_response`, `agent_statuses` (real per-agent status/warnings), `evidence_references[]` (`evidence_id`, `source_agent`, `domain`, `metric_name`, `validity_status`, `is_quarantined`, `provenance`), `missing_information`, `recommended_actions`, `escalation_required`, `authorized_memories_used`, `duration_ms`. Workflow C/D wiring: recent CONFIRMED/LIVE PHA+RAA memories are injected into the mission context; the AGENT reply (with evidence citations) is appended to the referenced chat session; a **24h LIVE PHA memory** with assessment provenance is recorded. Astronauts may only run assessments for themselves (`403` otherwise). If the supervisor stack is unavailable → `503` with the real import error |
| GET | `/assessments` | Bearer | Astronauts are force-scoped to their own identity; privileged roles must pass `astronaut_id` (`400` otherwise); `limit` 1–500 |
| GET | `/assessments/{assessment_id}` | Bearer | Astronauts receive a **summary view** (no internal workflow payload, cross-astronaut → `403`); privileged roles receive the full record including the complete `result` |

> Chat `POST /chat/sessions/{id}/messages` stays persistence-first and reports `provider_status: NOT_INVOKED`-style behavior — the model invocation happens **here**, so a chat reply never stalls on the ~10 s workflow.

---

## 9. Medical Document Intelligence (`/documents`)

Gateway over the **existing ai-engine pipeline** (PyMuPDF native text for PDFs, python-docx for DOCX, cloud-OCR only where the pipeline itself decides; text PDFs need no OCR and no network). Extraction produces records that enter a human review queue.

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/documents/upload` | Bearer | Multipart `file` + `astronaut_id`. `201` `{document_id, file_hash_sha256, file_type, …}`. Astronauts may upload **only their own** documents (`403`). Malicious/unsupported files → `400` (security validator) |
| POST | `/documents/{document_id}/process` | Privileged | Runs extraction. `force_ocr` query flag. Unknown → `404` |
| GET | `/documents/{document_id}` | Bearer | Status + extraction summary; identity-isolated (`403` for other astronauts) |
| GET | `/documents/{document_id}/records` | Bearer | Extracted records: `test_name`, `extracted_value`, `normalized_value`, `original_unit`, `extraction_confidence`, `validation_status`, `review_status` |
| GET | `/documents/pending/{astronaut_id}` | Privileged | Records awaiting human verification |
| POST | `/documents/records/{record_id}/review` | Privileged | `{action: CONFIRMED|REJECTED|EDITED, review_notes?, edited_*?}`. **`reviewer_id` is overwritten with the token identity** — a client-supplied value is ignored (test-verified) |
| POST | `/documents/{document_id}/retry` | Privileged | Re-run a failed extraction |
| GET | `/documents/confirmed/{astronaut_id}` | Bearer | Confirmed findings; owner or privileged only |

### 5.4 Demo-mode refusal (documented limitation)

`X-Trustline-Mode: demo` on any document route → `403 "Demo-mode medical document operations are disabled: the document pipeline currently persists to the operational medical store only, and demo isolation there is not implemented."` This is an explicit refusal, not a silent bypass.

---

## 10. Administration (`/admin`, ADMIN only)

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/users` | `role` filter; password hashes never serialized |
| GET | `/admin/audit` | `limit`, `action` filters; demo and operational events both recorded with their partition flag |
| GET | `/admin/sync/status` | Queue counters |
| GET | `/admin/sync/events` | `status_filter`, `limit` |
| POST | `/admin/sync/claim` | Claim next due event for a worker |
| POST | `/admin/sync/{event_id}/success` | Mark delivered |
| POST | `/admin/sync/{event_id}/failure` | Record failure (retries/dead-letter per queue policy) |
| POST | `/admin/sync/{event_id}/resolve` | `local_version`/`ground_version` conflict resolution; `409` when versions mismatch — conflicts are never silently overwritten |

---

## 11. Verification

| Suite | Tests | Runtime |
|---|---|---|
| `backend/tests/test_application_api.py` | 3 | — |
| `backend/tests/test_rbac.py` | 3 | — |
| `backend/tests/test_chat_sessions.py` | 5 | — |
| `backend/tests/test_memory_governance.py` | 6 | — |
| `backend/tests/test_memory_persistence.py` | 1 | — |
| `backend/tests/test_sync_api.py` | 3 | — |
| `backend/tests/test_connectivity.py` | 4 | — |
| `backend/tests/test_telemetry.py` | 5 | — |
| `backend/tests/test_radiation_api.py` | 4 | — |
| `backend/tests/test_documents_gateway.py` | 4 | 10.7 s |
| `backend/tests/test_assessments_supervisor.py` | 3 | 12.1 s (one real LOCAL_ONLY Supervisor run) |
| **Total** | **44 passed** | **17.5 s** (full suite, single real workflow invocation) |

Baseline regression before this batch (ai-engine + backend, all suites): **510 passed, 4 failed in 27:48** — the 4 failures were the backend batch-1 DB-seam bug since fixed; all 510 ai-engine tests passed unchanged.
