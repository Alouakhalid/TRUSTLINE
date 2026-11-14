# TRUSTLINE P07 — Offline-First Architecture & Ground Sync Report

## 1. Executive Summary

TRUSTLINE operates in harsh space flight environments where Earth communication is intermittently severed due to orbital mechanics, planetary occlusion, or solar events. Phase P07 establishes an offline-first transactional foundation ensuring zero data loss during blackout periods, deterministic outbox queuing, truthful connectivity probing, and human-in-the-loop conflict resolution.

All 22 automated tests covering synchronization, workers, queue semantics, and connectivity probes pass with 100% success.

---

## 2. Core Architecture

```mermaid
graph TD
    A[Telemetry / Medical Memory / Assessments] -->|Write Event| B[(Local SQLite Store)]
    B -->|Atomic Enqueue| C[Sync Outbox Queue 'sync_events']
    C -->|Polling Worker| D[SyncWorker]
    D -->|Probe Connectivity| E{Link State?}
    E -->|OFFLINE / NOT_CONFIGURED| F[Retain in Local Buffer]
    E -->|ONLINE| G[GroundHttpTransport]
    G -->|POST /sync/batch| H[Mission Control Ground Node]
    H -->|200 OK| I[Mark SYNCED]
    H -->|409 Conflict| J[Quarantine & Raise SyncConflict]
    H -->|5xx / Timeout| K[Exponential Backoff Retry]
```

### 2.1 Outbox Queue Foundation (`backend/sync/queue.py`)
- **Durable Persistence**: All outward events (telemetry summaries, confirmed clinical memories, supervisor assessments) are recorded in `sync_events` within SQLite.
- **Idempotency & Deduplication**: Every event has a unique composite key `(id, is_demo)`. Enqueueing an existing event returns `deduplicated: True` without mutating state.
- **Backoff & Dead Letter**: Retry attempts follow exponential backoff:
  $$\text{delay} = \min(3600, 2^{\min(\text{attempts}, 10)}) \text{ seconds}$$
  After 5 failed delivery attempts, records transition to `DEAD_LETTER` status, generating an auditable transition event.

### 2.2 Sync Worker & Transport (`backend/sync/worker.py`, `backend/sync/transport.py`)
- **Truthful Transport Discovery**: If `TRUSTLINE_GROUND_ENDPOINT` is unconfigured, the worker reports `TRANSPORT_NOT_READY` in its skip log rather than fabricating a successful ground sync.
- **Atomic Batches**: Records are claimed in batches of up to 50 items. Delivery confirmation updates `sync_events` and writes a checkpoint to `sync_checkpoints`.
- **Demo Mode Isolation**: The sync worker respects the `is_demo` flag. Demo events are strictly quarantined in their own partition and never transmitted over operational ground links.

### 2.3 Eight Independent Connectivity Probes (`backend/services/connectivity.py`)
The system evaluates eight decoupled monitors without circular dependencies:
1. `database`: Quick local SQLite integrity and read/write check.
2. `dns`: Low-latency name resolution probe for ground gateway FQDN.
3. `network`: TCP socket connection probe to flight telemetry router.
4. `local_ai`: Execution readiness check of local ONNX / ML model runtimes.
5. `cloud_ai`: API reachability check for remote Hugging Face / Groq providers.
6. `ground_link`: Deep Space Network (DSN) ground HTTP transport readiness.
7. `sync`: Health check of local outbox queue (degrades if dead-letter count > 0).
8. `ws`: Telemetry WebSocket broadcaster active connection tracking.

Truthful state resolution:
- **ONLINE**: DNS, network, and ground link all responding within threshold (< 500ms).
- **DEGRADED**: Core database functional, but remote AI or ground sync retries pending.
- **OFFLINE**: Network or DNS unreachable; local operations continue unhindered.
- **NOT_CONFIGURED**: Ground endpoint URL not supplied in mission environment.

---

## 3. Conflict Resolution & Clinical Safety

Under NASA-STD-3001 clinical safety standards, conflicting medical data must never be resolved via "last-write-wins" automated overwriting.

```python
def resolve_conflict(self, event_id: str, local_version: int, ground_version: int, is_demo: bool = False) -> dict[str, Any]:
    if local_version != ground_version:
        raise SyncConflict(f"version conflict for {event_id}: local={local_version}, ground={ground_version}")
    self.mark_success(event_id, is_demo=is_demo)
    return {"id": event_id, "status": "SYNCED", "resolution": "IDENTICAL_VERSION"}
```

When ground reports a different version of a clinical record:
1. The local queue raises `SyncConflict`.
2. The record is flagged for Flight Surgeon manual adjudication.
3. Both versions are retained with complete audit history in `audit_events`.

---

## 4. Verification Evidence

All 22 automated tests in `backend/tests/` verify P07 capabilities:
- `test_sync_worker.py`: 10/10 passed (delivery, backoff, dead-letter, offline buffer, checkpointing).
- `test_sync_queue.py`: 3/3 passed (idempotency, retry backoff, conflict guard).
- `test_sync_api.py`: 3/3 passed (RBAC admin gates, claim/success flow, conflict 409).
- `test_connectivity.py`: 6/6 passed (probe independence, DNS vs network failure differentiation, transition recording).
