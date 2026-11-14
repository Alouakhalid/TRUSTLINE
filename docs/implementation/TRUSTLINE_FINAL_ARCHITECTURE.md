# TRUSTLINE — Final End-to-End System Architecture

## 1. Architectural Vision

TRUSTLINE is an autonomous, hybrid, offline-first spaceflight physiological monitoring and clinical decision-support platform. It protects astronaut health during deep-space exploration missions (Moon, Mars, Deep Space Gateway) where real-time Earth support is impossible.

---

## 2. System Architecture Diagram

```mermaid
graph TB
    subgraph Spacecraft Hardware & Simulator
        BIO[Bio-Sensors / Simulator] -->|CRC32 Telemetry Packets| API_INGEST[/telemetry/packets/]
        RAD[Environmental Dosimeters] -->|NASA-STD-3001 Dosimetry| API_RAD[/radiation/ingest/]
    end

    subgraph Edge Service Boundary [FastAPI Local Server :8000]
        API_INGEST --> TELEM_SRV[Telemetry Ingestion Service]
        API_RAD --> RAD_GATE[Radiation Gateway Service]
        AUTH[RBAC Auth & JWT Guard] --> ME[Astronaut / Medic / Admin APIs]
        
        TELEM_SRV --> BROADCASTER[WebSocket Broadcaster]
        TELEM_SRV --> DB[(Local SQLite Store)]
        RAD_GATE --> DB
        
        SUPER_GATE[Supervisor Gateway] --> AGENTS
        MEM_SRV[Memory Governance] --> DB
        CHAT_SRV[Chat Session Service] --> DB
        SYNC_QUEUE[Sync Outbox Queue] --> DB
    end

    subgraph Multi-Agent AI Core [ai-engine / LangGraph]
        AGENTS[LangGraph Supervisor]
        AGENTS --> SQA[Sensor Quality Agent]
        AGENTS --> PHA[Personal Health Agent]
        AGENTS --> RAA[Risk Assessment Agent]
        AGENTS --> RAG[Medical RAG Agent]
        
        SQA --> ML_MODELS[RF / Isolation Forest / XGBoost]
        RAG --> DOC_EXTRACT[PyMuPDF / docx / Vision OCR]
    end

    subgraph Client Presentation Tier [frontend/public]
        SPA[FastAPI Static Mount /]
        SPA --> TWIN[3D Digital Twin Three.js]
        SPA --> SCOPE[60fps Oscilloscope Canvas]
        SPA --> PORTALS[Astronaut / Medical / Admin Portals]
        BROADCASTER -->|WS Telemetry Stream| SPA
    end

    subgraph Ground Synchronization Tier [backend/sync]
        SYNC_WORKER[SyncWorker] --> SYNC_QUEUE
        SYNC_WORKER --> PROBES[8 Connectivity Probes]
        PROBES -->|OFFLINE| BUFFER[Local Buffer Retained]
        PROBES -->|ONLINE| DSN[Ground HTTP Transport]
    end
```

---

## 3. Strict System Invariants

1. **LangGraph Sole Orchestrator**: LangGraph Supervisor coordinates all agent interactions. No secondary orchestrators (such as CrewAI) exist.
2. **Zero `#` Python Comments**: Exact comment hygiene invariant in `ai-engine/agents/supervisor/` and `ai-engine/agents/risk_assessment/` verified by AST tokenization.
3. **Environmental Radiation Isolation**: Space radiation dosimetry is environmental context only (NASA-STD-3001 Vol 1 Rev C Table 2) and is **never** included in physiological ML feature vectors.
4. **Local-First & Offline Resilience**: Mission operations, triage, and multi-agent clinical synthesis execute 100% locally on edge compute without cloud dependencies.
5. **Strict Demo Isolation**: `is_demo = 1` vs `is_demo = 0` database partitioning guarantees zero leakage between synthetic simulations and actual flight crew medical records.
