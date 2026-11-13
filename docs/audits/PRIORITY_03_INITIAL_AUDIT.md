# TRUSTLINE Priority 03: Personal Health Baseline — Initial Reconnaissance & Audit Report

**Subsystem:** Priority 03: Personal Health Baseline  
**Project:** TRUSTLINE Astronaut Health Monitoring & Decision Support Platform  
**Date:** November 13, 2026  
**Auditor:** Senior Biomedical AI Engineer, Machine Learning Engineer & QA Auditor  
**Status:** **PHASE 0 RECONNAISSANCE COMPLETED — ENGINEERING ROADMAP ESTABLISHED**  

---

## 1. Executive Summary & Context

TRUSTLINE is a research prototype designed for astronaut health monitoring and autonomous clinical decision-support during spaceflight operations. In prior phases:
- **Priority 01 (Medical Document Integration):** Formalized human-in-the-loop document ingestion, OCR, and laboratory test extraction, operating under review lifecycle states (`PENDING_REVIEW`, `CONFIRMED`, `REJECTED`, `QUARANTINED`). Closed as `ACCEPTED WITH LIMITATIONS — RESEARCH PROTOTYPE ONLY`.
- **Priority 02 (Medical Knowledge RAG):** Implemented hybrid dense/sparse retrieval and grounded generation over aerospace clinical guidelines with strict astronaut identity scoping, Evidence Registry compilation (`EV-KNOW-*`), and complete telemetry immutability ($\Delta \text{HR} = 0.0\,\text{bpm}$). Closed as `ACCEPTED WITH LIMITATIONS — RESEARCH PROTOTYPE ONLY`.

**Priority 03** addresses **Personal Health Baseline**: establishing an individual astronaut's physiological normal patterns across spaceflight missions and comparing incoming telemetry against individualized reference envelopes.

---

## 2. Repository Reconnaissance & Architectural State

A thorough, repository-wide reconnaissance of code, schemas, databases, and pipelines reveals the following current state:

### 2.1 Existing Architecture & Components
1. **`PersonalBaselineInterface` (`ai-engine/agents/personal_health/services/baseline_interface.py`):**
   - Currently exists as an interface stub.
   - Contains methods: `get_baseline_status()`, `set_baseline_status()`, `is_baseline_available()`, `validate_session_as_baseline()`, `get_baseline_provenance()`, `evaluate_deviation()`.
   - Returns static/mock dictionary structures without actual statistical calculations, persistence, or data pipelines.
2. **`BaselineStatus` Enum (`ai-engine/agents/personal_health/schemas/assessment.py`):**
   - Defines states: `NOT_AVAILABLE`, `INSUFFICIENT_DATA`, `AVAILABLE`, `INVALID`.
3. **Core-14 Feature Pipeline (`feature_extraction_service.py` & `physiological_features.py`):**
   - Standardizes 14 core physiological metrics extracted from sensor telemetry:
     - Cardiac: `hr_mean_bpm`, `hr_std_bpm`, `hrv_rmssd_ms`, `hrv_sdnn_ms`
     - Electrodermal: `eda_mean`, `eda_std`, `eda_iqr`
     - Respiratory: `resp_rate_bpm`, `resp_std`
     - Thermal: `temp_mean`, `temp_std` (peripheral skin temperature)
     - Muscular & Inertial: `emg_rms`, `acc_magnitude_mean`, `acc_magnitude_std`
4. **Sensor Quality Ingestion & Gating (SQA):**
   - Evaluates sensor signals and produces `SensorQualityReport` with `can_proceed` gating and per-channel quality status (`VALID`, `DEGRADED`, `INVALID`).
5. **Multi-Agent Orchestrator (LangGraph Supervisor):**
   - Orchestrates the 10-node DAG: `intake` -> `input_validation` -> `sensor_quality` -> `personal_health` -> `medical_rag` -> `risk_assessment` -> `evidence_validation` -> `final_synthesis` -> `persistence` -> `final_response`.
   - Sole orchestrator; strictly zero `#` comments in `supervisor/` and `risk_assessment/`.
6. **Evidence Registry (`EvidenceRegistryService`):**
   - Cross-agent evidence aggregation compiling `EV-SQ-*`, `EV-PHY-*`, `EV-MED-*`, and `EV-KNOW-*` items with cryptographic provenance and quarantine tracking.
7. **Database Infrastructure (`repositories/base.py`):**
   - SQLAlchemy SQLite engine with `Base`, `SessionFactory`, and thread-safe session pooling.
   - Stores `astronaut_health_profiles` and `medical_documents`.
8. **ML Experimental Artifacts (`ai-engine/ml/artifacts/configurations/baseline_statistics.json`):**
   - Contains reference population statistics (mean, std, median, mad) calculated across laboratory WESAD sessions.

---

## 3. Gap Analysis & Deficiencies Identified

| Component | Existing State | Required Engineering Target for Priority 03 |
|:---|:---|:---|
| **Data Eligibility Pipeline** | Missing. No ingestion pipeline validates historical observation sessions for baseline inclusion. | Build `BaselineDataPipeline` validating sensor quality, timestamp monotonicity, sampling consistency, and astronaut identity. |
| **Statistical Baseline Engine** | Stub returning fixed defaults. | Build `RobustBaselineEngine` calculating median, MAD, IQR, quantiles, and handling zero-variance ($MAD=0$) safely. |
| **Readiness State Machine** | 4 basic enum values in assessment schema. | Formalize lifecycle: `INSUFFICIENT_DATA`, `PROVISIONAL`, `ESTABLISHED`, `STALE`, `SUSPENDED`, `INVALID` with strict transition thresholds. |
| **Context Awareness** | None. Single generic profile. | Implement context partitioning (`REST`, `ACTIVITY`, `NOMINAL`, `UNKNOWN`) based on accelerometer and activity metrics. |
| **Deviation Detection Engine** | Stub returning `{}`. | Build `PersonalDeviationEngine` computing robust Z-scores, quantile deviations, and persistence tracking (EWMA / CUSUM). |
| **Baseline Update Manager** | None. No mechanism to update baselines. | Build `SafeBaselineUpdateManager` with anomaly filtering, versioned snapshots, rollback support, and audit trails. |
| **Persistence Layer** | No baseline table in SQLite. | Create `AstronautBaselineModel` and `BaselineHistoryModel` in SQLAlchemy for persistent, versioned storage. |
| **Evidence Registry Integration** | No `EV-BASE-*` items registered. | Integrate baseline deviation items (`EV-BASE-*`) into `EvidenceRegistryService` with provenance and quarantine guards. |
| **PHA & Supervisor Integration** | PHA passes static `NOT_AVAILABLE`. | Integrate baseline retrieval and deviation evaluation into `PersonalHealthAdapter` and LangGraph state. |

---

## 4. Non-Negotiable Safety & Data Invariants

1. **Sole Orchestrator Invariant:** LangGraph remains the only workflow orchestrator.
2. **Comment Hygiene Invariant:** Strictly **ZERO `#` comments** in `ai-engine/agents/supervisor/` and `ai-engine/agents/risk_assessment/`.
3. **Identity Isolation:** Baselines are strictly scoped to one `astronaut_id`. Queries or updates without a verified identity must immediately fail with safe abstention. Never default to `AST-001`.
4. **Historical vs. Live Separation:** Historical sessions used for baseline calibration must never overwrite or collide with current live telemetry ($\Delta \text{HR} = 0.0, \Delta \text{Resp} = 0.0$).
5. **P01 Medical Document Isolation:** Medical document lab findings are distinct historical clinical evidence and must never be converted into sensor baseline observations.
6. **Sensor Quality Invariant:** Observations flagged as `INVALID` or from compromised sensors by SQA must be rejected from baseline construction and baseline updates.
7. **WESAD Laboratory Context:** WESAD is an experimental laboratory dataset, not astronaut clinical ground truth. WESAD labels must never be presented as spaceflight medical diagnoses.
8. **Temperature Semantic Invariant:** Skin temperature (`temp_mean`) is peripheral, never core body temperature.
9. **Zero Fabrication:** Missing baseline data must trigger explicit `INSUFFICIENT_DATA` or `NOT_AVAILABLE` abstention, never fabricated normal values.

---

## 5. Architectural Blueprint for Priority 03

```
ai-engine/agents/personal_health/baseline/
├── __init__.py
├── schemas.py              # BaselineProfile, DeviationResult, BaselineUpdateLog, ContextType
├── data_pipeline.py        # Ingestion, validation, SQA gating, and readiness metrics
├── statistical_engine.py   # Robust statistics (Median, MAD, IQR, Quantiles, Zero-MAD handling)
├── context_engine.py       # Context segregation (REST, ACTIVITY, NOMINAL) & fallback
├── deviation_engine.py     # Robust Z-score, quantile deviations, persistence & trends
├── update_manager.py       # Controlled updates, anomaly contamination rejection, rollback
└── repository.py           # SQLAlchemy SQLite models, versioning, and transaction isolation
```

### Integration Points:
- `personal_health/services/baseline_interface.py`: Rewritten to wrap the new modular baseline engine while preserving 100% backward compatibility with existing tests.
- `supervisor/adapters/personal_health_adapter.py`: Evaluates personal baseline deviation when available and records baseline metrics into `PersonalHealthAssessment`.
- `supervisor/services/evidence_registry_service.py`: Emits `EV-BASE-*` evidence items into the cross-agent Evidence Registry.
- `risk_assessment/`: Receives structured baseline deviation evidence without altering existing nominal behaviors when baselines are unestablished.

---

## 6. Implementation & Verification Roadmap

- **Step 1:** Implement `baseline/schemas.py` and `baseline/repository.py` (SQLAlchemy models).
- **Step 2:** Implement `baseline/data_pipeline.py` (eligibility, SQA quality validation, identity isolation, readiness).
- **Step 3:** Implement `baseline/statistical_engine.py` (robust statistics, MAD fallback, multi-feature profiles).
- **Step 4:** Implement `baseline/context_engine.py` (REST vs ACTIVITY partitioning, safe fallback).
- **Step 5:** Implement `baseline/deviation_engine.py` (robust Z-scores, multi-signal deviation, persistence).
- **Step 6:** Implement `baseline/update_manager.py` (safe update policy, contamination protection, versioning).
- **Step 7:** Connect to `baseline_interface.py`, `personal_health_adapter.py`, and `evidence_registry_service.py`.
- **Step 8:** Build comprehensive Priority 03 test suite across all 8 test areas (A through H).
- **Step 9:** Execute full regression suite (SQA, PHA, RAA, Supervisor baseline, Supervisor stress, P01, P02, P03).
- **Step 10:** Execute ML evaluation benchmark & performance audit, and author remaining audit reports.
