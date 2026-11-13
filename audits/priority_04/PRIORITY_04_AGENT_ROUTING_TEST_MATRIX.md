# TRUSTLINE PRIORITY 04 — AGENT ROUTING & FAILURE RECOVERY TEST MATRIX

**Test Suite:** `ai-engine/tests/test_agent_hybrid_router_integration.py`  
**Execution Platform:** Darwin 26.5.2 (macOS M1, Python 3.10.0rc2, pytest 9.1.1)  
**Total Tests:** 9  
**Passed:** 9 (100%)  
**Failed:** 0  
**Skipped:** 0  

---

## 1. Test Matrix Overview

| Test ID | Test Name | Target Component | Scenario Simulated | Assertions Verified | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TR-01** | `test_01_normal_groq_execution_through_router` | `LLMInterpretationService`, `MedicalRAGGenerator` | Cloud provider healthy and responding | Router dispatches to Groq; provider telemetry recorded; telemetry execution mode is `HYBRID_CLOUD`; response content returned. | **PASSED** |
| **TR-02** | `test_02_cloud_auth_failure_triggers_local_fallback_for_eligible_task` | `SymptomService`, `HybridAIRouter` | Groq raises `ProviderAuthenticationError` | Router catches 401; dispatches to `OllamaProvider`; local inference executes successfully; structured JSON symptom event parsed; `selected_provider == "ollama"`. | **PASSED** |
| **TR-03** | `test_03_local_provider_failure_cleanly_defaults_to_deterministic_fallback` | `MedicalRAGGenerator`, `PersonalHealthAgent` | Cloud unavailable AND Ollama unreachable (`ProviderUnavailableError`) | Both providers fail; agent catches `ProviderUnavailableError`; executes deterministic grounded clinical fallback; no unhandled crash; safe structured output produced. | **PASSED** |
| **TR-04** | `test_04_cloud_only_tasks_strictly_reject_local_fallback` | `GroqVisionClient`, `GroqVoiceService` | Cloud failure on `IMAGE_OCR` and `AUDIO_TRANSCRIPTION` | Capability registry checks execution mode; throws `TaskNotEligibleError`; verifies local Ollama is never called; prevents corrupting text LLM with binary payloads. | **PASSED** |
| **TR-05** | `test_05_circuit_breaker_recovery_to_groq` | `CircuitBreaker`, `HybridAIRouter` | 3 consecutive cloud failures trip breaker OPEN; 30s timeout elapses; 2 successful probes in HALF_OPEN | Breaker trips to `OPEN`; bypasses cloud; routes to Ollama; after timeout enters `HALF_OPEN`; 2 consecutive successes reset breaker to `CLOSED`; restores Groq routing. | **PASSED** |
| **TR-06** | `test_06_medical_rag_citations_and_provenance_preserved_after_local_fallback` | `MedicalRAGGenerator`, `RetrievedPassage` | Cloud failure forces fallback to Ollama | Synthesis generated via local model retains exact source document citations (`NASA-STD-3001:P45`); section headers intact; citation provenance preserved. | **PASSED** |
| **TR-07** | `test_07_risk_classification_immutable_by_unsupported_llm_output` | `LLMInterpretationService`, `RiskAssessmentAgent` | Local LLM outputs contradictory or hallucinated risk classification | Deterministic `overall_risk` (e.g. `LOW`) remains unchanged; LLM explanation is sanitized; rule engine authority is immutable. | **PASSED** |
| **TR-08** | `test_08_missing_evidence_remains_unknown_or_insufficient_data` | `ClinicalSynthesisValidator`, `PersonalHealthAgent` | Telemetry with missing baseline and missing mission day | Validator rejects claims of established baseline; rejects unevidenced day claims; deterministic fallback preserves `baseline_status="not_available"`. | **PASSED** |
| **TR-09** | `test_09_static_ast_audit_no_direct_text_groq_bypasses_router` | Repository Python AST | Static repository inspection | Verifies 0 direct text-generation Groq client calls exist in application code; all route through `HybridAIRouter`. | **PASSED** |

---

## 2. Core Hybrid AI Router Unit Test Matrix (`ai-engine/tests/test_hybrid_ai_router.py`)

In addition to the 9 agent integration tests, the core router test suite contains 16 comprehensive unit tests:

| Test ID | Test Scenario | Verified Invariant | Status |
| :--- | :--- | :--- | :--- |
| **TC-01** | `test_01_groq_healthy_selects_groq` | Normal operation selects primary cloud provider | **PASSED** |
| **TC-02** | `test_02_groq_timeout_falls_back_to_local_ollama` | 20s/25s cloud timeout triggers local fallback | **PASSED** |
| **TC-03** | `test_03_groq_connection_error_falls_back_to_local_ollama` | Network disconnect immediately falls back to Ollama | **PASSED** |
| **TC-04** | `test_04_groq_rate_limit_falls_back_to_local_ollama` | HTTP 429 rate limit triggers local fallback | **PASSED** |
| **TC-05** | `test_05_groq_auth_failure_does_not_endlessly_retry` | HTTP 401 records failure without retry loop | **PASSED** |
| **TC-06** | `test_06_cloud_only_task_fails_without_local_fallback` | Cloud-only capability strictly blocks fallback | **PASSED** |
| **TC-07** | `test_07_deterministic_offline_task_routes_deterministically` | Offline tasks execute purely deterministically | **PASSED** |
| **TC-08** | `test_08_unavailable_task_raises_error` | Unregistered task category raises structured error | **PASSED** |
| **TC-09** | `test_09_ollama_healthy_direct_execution` | Direct local execution functions as expected | **PASSED** |
| **TC-10** | `test_10_ollama_unavailable_raises_structured_failure` | Ollama connection failure raises structured error | **PASSED** |
| **TC-11** | `test_11_circuit_breaker_trips_to_open_after_failure_threshold` | 3 consecutive failures transitions state to OPEN | **PASSED** |
| **TC-12** | `test_12_circuit_breaker_open_avoids_unnecessary_cloud_requests` | OPEN state immediately routes to local without probing cloud | **PASSED** |
| **TC-13** | `test_13_circuit_breaker_recovery_to_half_open_and_closed` | 30s timeout enables HALF_OPEN; 2 successes close breaker | **PASSED** |
| **TC-14** | `test_14_circuit_breaker_half_open_failure_re_trips_to_open` | Failure in HALF_OPEN immediately re-trips to OPEN | **PASSED** |
| **TC-15** | `test_15_telemetry_captures_fields_and_masks_secrets` | Telemetry logs latency, tokens/sec, and masks API keys | **PASSED** |
| **TC-16** | `test_16_local_only_mode_forces_local_execution` | Configured `LOCAL_ONLY` mode strictly prevents cloud calls | **PASSED** |

**Combined Hybrid AI Suite Total:** 25 / 25 PASSED (100%)
