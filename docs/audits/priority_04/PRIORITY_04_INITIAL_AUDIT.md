# TRUSTLINE — Priority 04: Initial Architecture & Environment Audit
**Subsystem:** Priority 04 — Hybrid AI Router & Local LLM Fallback  
**Auditor:** Senior Software Architect, Biomedical AI Engineer, QA Auditor  
**Date:** November 13, 2026  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

This initial audit establishes the architectural baseline, existing provider dependencies, hardware constraints, and integration boundaries for **Priority 04: Hybrid AI Router & Local LLM Fallback** within the TRUSTLINE astronaut health monitoring platform.

The objective is to replace direct, fragmented cloud LLM calls with a resilient, centralized provider-selection layer that routes eligible inference tasks to an onboard local LLM (`qwen2.5:7b-instruct` via Ollama) during Deep Space Network (DSN) communication blackouts, cloud timeouts, rate limits, or API outages, while strictly preserving:
1. **LangGraph as the sole orchestrator** (zero secondary supervisors, zero CrewAI orchestrator replacements).
2. **Deterministic medical safety mechanisms** (claim grounding validators, telemetry immutability, zero hallucination).
3. **Multi-agent execution contracts** across Sensor Quality Agent (SQA), Personal Health Agent (PHA), Risk Assessment Agent (RAA), and the Supervisor Orchestrator.

---

## 2. Existing LLM Infrastructure Audit

An exhaustive grep and AST inspection across `ai-engine/` identified 7 distinct LLM entrypoints:

| Component | File Path | Existing Provider / Model | Task Description | Existing Fallback Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Risk Assessment Agent** | `agents/risk_assessment/services/llm_interpretation_service.py` | Groq / `llama-3.3-70b-versatile` | 3-paragraph clinical risk synthesis | Deterministic fallback template (`_build_deterministic_fallback`) |
| **Personal Health Agent** | `agents/personal_health/agent/agent.py` | Groq / `qwen/qwen3.8-27b` | Clinical synthesis flight surgeon briefing | Deterministic grounded fallback (`ClinicalSynthesisValidator`) |
| **Symptom Intelligence** | `agents/personal_health/services/symptom_service.py` | Groq / `qwen/qwen3.8-27b` | Bilingual (EN/AR) structured symptom extraction | Deterministic keyword regex extractor |
| **Medical RAG** | `agents/personal_health/rag/generation.py` | Groq / `qwen/qwen3.8-27b` | 5-section medical answer synthesis with citations | Deterministic passage concatenation |
| **Sensor Quality Agent** | `agents/sensor_quality/agent/agent.py` | Groq / `qwen/qwen3.8-27b` | Executive sensor quality briefing | Returns error string |
| **Medical Document OCR** | `ocr/groq_vision_client.py` | Groq / `qwen/qwen3.8-27b` | Optical character recognition on medical PDFs | Explicitly prohibits non-Groq OCR providers |
| **Voice Transcription** | `agents/personal_health/services/groq_voice_service.py` | Groq / `whisper-large-v3` | Audio speech-to-text | None (requires cloud Whisper) |

### Key Infrastructure Deficiencies Identified:
1. **Placeholder Hybrid Router:** `ai-engine/hybrid_ai/` contained starter stubs (`cloud_provider.py`, `local_provider.py`, `ai_router.py`) returning static hardcoded mockup strings. No actual provider abstraction, circuit breaker, or agent integration existed.
2. **Fragmented Direct API Calls:** Each agent independently instantiated `groq.Groq(api_key=...)` with divergent timeouts, retry policies, and error handling.
3. **No Local LLM Fallback:** When Groq API keys were absent or an outage occurred, agents dropped directly from cloud LLM to static deterministic text templates without attempting onboard local inference.
4. **Hardcoded Model Names:** Certain modules referenced `llama-3.3-70b-versatile` which returned HTTP 404 (model not found) on the active Groq account, whereas `qwen/qwen3.8-27b` is verified active.

---

## 3. Workflow & Orchestration Architecture Audit

1. **LangGraph Supervisor Orchestrator:**
   - Defined in `ai-engine/agents/supervisor/workflow/graph.py`.
   - 10-node sequential StateGraph: `intake` -> `input_validation` -> `sensor_quality` -> `personal_health` -> `medical_rag` -> `risk_assessment` -> `evidence_validation` -> `final_synthesis` -> `persistence` -> `final_response`.
   - State contract: `SupervisorMultiAgentState` carrying `astronaut_id`, `session_id`, `sensor_quality_result`, `personal_health_result`, `risk_assessment_result`, `evidence_registry`, and `agent_execution_status`.
   - **Architectural Guardrail:** The Hybrid AI Router must sit *underneath* the agents as an inference provider infrastructure layer. It must **not** become an orchestrator or alter node sequencing in the supervisor DAG.

2. **Deterministic Safety & Validation Layers:**
   - `ClaimGroundingValidator` in RAA enforces zero ungrounded clinical claims, no hallucinated mission days, and strict adherence to evaluated monitoring domains.
   - `ClinicalSynthesisValidator` in PHA enforces zero RMSSD hallucination, no false asymptomatic assertions, and no ungrounded fluid shift attributions.
   - `EvidenceRegistryService` in Supervisor verifies cryptographic provenance and quarantines unverified evidence items.
   - **Safety Invariant:** Local LLM fallback output must be routed through these exact same validators. If local inference generates an ungrounded claim, the validator must catch it and safely trigger deterministic fallback.

---

## 4. Hardware & Local Environment Audit

Direct inspection of the host system yielded the following verified specifications:

- **Host Architecture:** Apple Silicon M1 (arm64), 8-core CPU, 8-core GPU.
- **Unified System Memory:** 8,589,934,592 bytes (8.00 GB Unified Memory).
- **Operating System:** macOS Darwin 26.5.2 (macOS 15/Sequoia base).
- **Python Runtime:** Python 3.10.0rc2 (`/Library/Frameworks/Python.framework/Versions/3.10/bin/python3`).
- **Ollama Version:** Client version 0.40.16; HTTP Daemon running on `http://127.0.0.1:11434`.
- **Installed Local Models:**
  1. `qwen2.5:7b-instruct` (Size: 4.68 GB, Q4_K_M GGUF quantization, 7.6B parameters, 32k context, tools + completion capabilities, 88% GPU Metal offloading).
  2. `llama3:latest` (Size: 4.66 GB, Q4_0 GGUF quantization, 8.0B parameters).
- **Storage Constraints:** Total filesystem size 228 GiB, available disk space ~611 MiB (96% utilization).
  > [!WARNING]
  > **Physical Disk Limitation:** With only ~611 MiB of free disk space, downloading additional large models would exhaust disk storage. Reusing the pre-installed `qwen2.5:7b-instruct` (4.68 GB) is physically mandatory and architecturally sound.

---

## 5. Scope of Proposed Implementation & Modifications

### New Components in `ai-engine/hybrid_ai/`:
1. `base_provider.py`: Abstract provider interface (`BaseLLMProvider`), request/response schemas (`ProviderRequest`, `ProviderResponse`), health models, and structured exception hierarchy.
2. `groq_provider.py`: Production Groq adapter wrapping `groq.Groq`, managing timeouts, connection retries with exponential backoff, rate limit handling, and API key masking.
3. `ollama_provider.py`: Production Ollama adapter interfacing with `http://127.0.0.1:11434`, managing `qwen2.5:7b-instruct`, Metal GPU monitoring, schema enforcement (`format="json"`), and token throughput calculation.
4. `circuit_breaker.py`: Three-state circuit breaker (`CLOSED`, `OPEN`, `HALF_OPEN`) preventing cloud request storms during outages and executing smooth, flappless recovery.
5. `capability_registry.py`: Task capability matrix classifying tasks as `LOCAL_ELIGIBLE`, `CLOUD_ONLY`, `DETERMINISTIC_OFFLINE`, or `UNAVAILABLE`.
6. `telemetry.py`: Privacy-preserving, structured inference audit logger recording request IDs, latencies, tokens/sec, provider choice, fallback reasons, and memory statistics.
7. `router.py`: Central `HybridAIRouter` coordinating capability gating, circuit breaking, cloud dispatch, transparent local fallback, and telemetry generation.

### Integration Boundaries:
- `LLMInterpretationService` (RAA)
- `MedicalRAGGenerator` (PHA RAG)
- `ClinicalSynthesisService` (PHA)
- `SymptomService` (PHA)
- `SensorQualityAgent` (SQA)

All agent changes will operate through narrow, backward-compatible adapters preserving 100% of existing unit and E2E test contracts.
