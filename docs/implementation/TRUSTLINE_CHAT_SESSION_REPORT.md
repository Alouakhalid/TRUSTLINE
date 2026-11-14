# TRUSTLINE Chat Session Management & AI Companion Report

## 1. Executive Summary

TRUSTLINE provides a mission-critical AI Medical Companion chat interface. It enables astronauts to report symptoms, inquire about operational medical guidelines, and review clinical action plans during long-duration space missions.

The system enforces strict astronaut identity binding, session lifecycle management, multi-agent Supervisor orchestration, and evidence citation provenance.

---

## 2. Chat Data Architecture

```sql
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    content TEXT NOT NULL,
    agent TEXT,
    processing_status TEXT,
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
```

### 2.1 Session Lifecycle
- **Create**: Initialized with astronaut binding and timestamped creation.
- **Rename & Archive**: Astronauts can customize titles and archive completed medical consultations.
- **Search & Filter**: Sessions can be queried by keyword, status (`ACTIVE` vs `ARCHIVED`), and date range.
- **Cascading Deletion**: Deleting a session permanently removes all associated chat messages in a single atomic transaction.

---

## 3. Multi-Agent Synthesis & Evidence Citations

When an astronaut submits a clinical inquiry:
1. The message is persisted in `chat_messages` with status `RECEIVED`.
2. The request routes to `backend/services/supervisor_gateway.py`.
3. The LangGraph Supervisor coordinates:
   - **SQA**: Validates current telemetry confidence.
   - **PHA**: Retrieves personalized physiological baselines.
   - **RAA**: Calculates spaceflight decompensation risk.
   - **Medical RAG**: Retrieves NASA-STD-3001 evidence.
4. An `AGENT` response is appended to the session containing structured citations:
   ```json
   {
     "sender": "AGENT",
     "agent": "supervisor",
     "processing_status": "COMPLETED",
     "citations": [
       {"evidence_id": "EVID-PHA-01", "source_agent": "personal_health_agent", "confidence": 0.92},
       {"evidence_id": "EVID-RAG-02", "source_agent": "medical_rag_agent", "confidence": 0.95}
     ]
   }
   ```
5. The frontend displays interactive inline citations that open detailed evidence inspector cards.
