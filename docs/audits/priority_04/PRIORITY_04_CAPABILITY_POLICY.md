# TRUSTLINE — Priority 04: Task Capability & Clinical Safety Policy
**Subsystem:** Priority 04 — Capability Registry  
**Role:** Senior Biomedical AI Engineer & Clinical Safety Auditor  
**Date:** November 13, 2026  
**Status:** IMPLEMENTED & ENFORCED  

---

## 1. Task Capability Classification Matrix

Not every biomedical monitoring task can be delegated to a quantized local edge model. The **Capability Registry** strictly maps all TRUSTLINE tasks to one of four policy tiers:

| Task Category | Policy Tier | Primary Provider | Fallback Eligible? | Safety Rationale |
| :--- | :---: | :---: | :---: | :--- |
| `general_explanation` | `LOCAL_ELIGIBLE` | Groq | **Yes (Ollama)** | Low-risk conceptual knowledge; verified 13+ TPS on Qwen 2.5 7B. |
| `concise_summarization` | `LOCAL_ELIGIBLE` | Groq | **Yes (Ollama)** | Tested under-25-word clinical summarization; verified accurate. |
| `structured_extraction` | `LOCAL_ELIGIBLE` | Groq | **Yes (Ollama)** | Tested JSON schema extraction; 100% valid parseable syntax. |
| `agent_report_formatting` | `LOCAL_ELIGIBLE` | Groq | **Yes (Ollama)** | Markdown formatting of deterministic findings. |
| `medical_document_ocr` | `CLOUD_ONLY` | Groq Vision | **NO (Refused)** | Optical Character Recognition on medical PDFs strictly mandates Groq Vision OCR per P01 contract. Local text model cannot process vision. |
| `medical_rag_synthesis` | `LOCAL_ELIGIBLE` | Groq | **Yes (Ollama)** | Synthesizes answers strictly from retrieved passages. Falls back to deterministic passage compilation if grounding fails. |
| `personal_health_synthesis` | `LOCAL_ELIGIBLE` | Groq | **Yes (Ollama)** | Flight surgeon briefing; strictly validated by `ClinicalSynthesisValidator`. |
| `risk_assessment_synthesis` | `LOCAL_ELIGIBLE` | Groq | **Yes (Ollama)** | 3-paragraph clinical risk explanation; strictly audited by `ClaimGroundingValidator`. |
| `tool_calling` | `UNAVAILABLE` | None | **NO (Refused)** | Direct autonomous tool execution without validation is prohibited for safety. |
| `voice_interpretation` | `CLOUD_ONLY` | Groq Whisper | **NO (Refused)** | Audio transcription requires specialized Whisper large models hosted on Groq. |
| `sensor_quality_briefing` | `LOCAL_ELIGIBLE` | Groq | **Yes (Ollama)** | Executive summary of sensor health for PHA. |
| `supervisor_final_report` | `DETERMINISTIC_OFFLINE`| Rule Engine | **NO (Deterministic)**| Patient-facing communication is generated deterministically by `AstronautCommunicationService` for absolute safety. |

---

## 2. Non-Negotiable Medical Safety Invariants

1. **Anti-Hallucination Guardrail:** Local LLM outputs are never accepted without validation. If a local model invents lab values (e.g. sodium, glucose) or unmeasured parameters, upstream validators reject the synthesis and revert to deterministic safe fallbacks.
2. **Deterministic Risk Invariance:** A local model can never change an astronaut's deterministic risk score from `CRITICAL` to `LOW`, nor can it override an active `ESCALATION_REQUIRED` trigger.
3. **Telemetry Immutability:** Historical medical records retrieved during RAG or document analysis can never overwrite live streaming physiological sensor data.
4. **Quarantine Enforcement:** Pending, unreviewed, or quarantined medical documents are excluded from retrieval and cannot influence clinical synthesis.
5. **Missing Data Semantics:** The absence of telemetry or symptom reporting (`EV-SYM-UNSUBMITTED`) is never interpreted as normal health or the absence of disease.\n