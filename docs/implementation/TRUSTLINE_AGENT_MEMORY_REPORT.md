# TRUSTLINE Agent Memory Architecture & Governance Report

## 1. Overview & Principles

Agent Memory in TRUSTLINE provides persistent, role-governed context across multi-agent reasoning cycles, astronaut chat sessions, and mission restarts. It bridges ephemeral sensor telemetry with long-term clinical records while enforcing strict cryptographic and role-based access control (RBAC).

---

## 2. Storage Schema & Data Lifecycle (`agent_memories`)

All agent memories reside in the local SQLite table `agent_memories`:

```sql
CREATE TABLE IF NOT EXISTS agent_memories (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    content TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'PENDING',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    expires_at TEXT,
    is_long_term INTEGER NOT NULL DEFAULT 0,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 2.1 Namespace Partitioning
1. **`SQA` (Sensor Quality Agent)**: Signal-to-noise ratios, lead impedances, baseline drift, and sensor hardware reliability indexes.
2. **`PHA` (Personal Health Agent)**: Personalized baseline heart rates, HRV norms, circadian sleep patterns, and subjective symptoms.
3. **`RAA` (Risk Assessment Agent)**: Orthostatic intolerance risk scores, decompression sickness (DCS) indices, and cardiac strain warnings.
4. **`MEDICAL_RAG` (Medical Evidence & Guidelines)**: NASA-STD-3001 clinical limits, Space Medicine flight surgeon protocols, confirmed lab results.

### 2.2 Verification Statuses
- `PENDING`: Unverified data (astronaut self-reports, preliminary AI findings).
- `CONFIRMED`: Verified by a human Flight Surgeon or Medical Officer.
- `REJECTED`: Invalidated or erroneous telemetry findings.
- `QUARANTINED`: Sensor artifact or anomalous reading under review.
- `HISTORICAL`: Archived baseline from previous missions or pre-flight training.
- `LIVE`: High-frequency operational telemetry synthesis (24h default TTL).

---

## 3. Governance & Concurrency Rules

1. **Privilege Gating**: Astronauts may create memories in `PENDING` status. Only `MEDICAL_OFFICER` and `ADMINISTRATOR` roles can promote records to `CONFIRMED`.
2. **Versioned Corrections**: Any update to memory content atomically bumps `version = version + 1` and logs an entry in `audit_events`. Concurrent edits never silently overwrite.
3. **Cross-Astronaut Boundary**: Astronauts can only read and write memories matching their authenticated `astronaut_id`. Cross-astronaut requests yield HTTP 403 Forbidden.
4. **Restart Survival**: SQLite transactional persistence ensures all memories survive application restarts and container crashes without data loss.
