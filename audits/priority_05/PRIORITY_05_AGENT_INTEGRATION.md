# PRIORITY 05: MULTI-AGENT RLHF INTEGRATION
## Single Shared Model Architecture Across Biomedical Agents

### Executive Summary

Priority 05 establishes a single shared pretrained RLHF model (`meta-llama/Llama-3.1-8B-Instruct`) to serve all four core text-generation agents in TRUSTLINE. This document proves that agent behavioral boundaries, schemas, evidence requirements, and safety policies are strictly preserved.

---

### 1. Architecture: Shared Model with Strict Agent Encapsulation

```
                  ┌──────────────────────────────────────────────┐
                  │    Shared Pretrained RLHF Language Model     │
                  │        meta-llama/Llama-3.1-8B-Instruct      │
                  └──────────────────────▲───────────────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   │           Hybrid AI Router                │
                   └──────▲───────────▲───────────▲───────────▲┘
                          │           │           │           │
           ┌──────────────┴─┐   ┌─────┴────────┐  │  ┌────────┴────────┐
           │ Sensor Quality │   │   Personal   │  │  │   Medical RAG   │
           │     Agent      │   │ Health Agent │  │  │      Agent      │
           └────────────────┘   └──────────────┘  │  └─────────────────┘
                                                  │
                                       ┌──────────┴────────┐
                                       │  Risk Assessment  │
                                       │       Agent       │
                                       └───────────────────┘
```

The four agents share compute resources and model weights, but maintain completely isolated execution contexts:
1. Distinct System Prompts.
2. Distinct Task Categories.
3. Distinct Input/Output Contracts (Pydantic models).
4. Distinct Validation Layers.

---

### 2. Agent-by-Agent Integration Analysis

#### A. Sensor Quality Agent (SQA)
- **Task Category:** `TaskCategory.SENSOR_QUALITY_BRIEFING`.
- **System Prompt:** Specialized biomedical instrumentation and sensor artifact interpretation.
- **Payload:** Empirical Signal-to-Noise Ratio (SNR), baseline drift percentages, clipping indices.
- **Invariant:** LLM provides textual briefing for telemetry dashboards; raw sensor quality indices are strictly computed by deterministic digital signal processing (DSP) filters.

#### B. Personal Health Agent (PHA)
- **Task Category:** `TaskCategory.PERSONAL_HEALTH_SYNTHESIS`.
- **System Prompt:** Aerospace clinical decision-support and crew baseline synthesis.
- **Validation Layer:** `ClinicalSynthesisValidator`:
  - Enforces physiological limits (heart rate, SpO2, respiratory rate).
  - Blocks unsupported causal claims (e.g., asserting cephalad fluid shift without diagnostic proof).
  - Flags direct vagus nerve measurement overclaims.
- **Invariant:** Synthesis must align with deterministic ground-truth telemetry dictionary.

#### C. Risk Assessment Agent (RAA)
- **Task Category:** `TaskCategory.RISK_ASSESSMENT_SYNTHESIS`.
- **System Prompt:** Multi-domain clinical risk summarization and flight surgeon briefing.
- **Immutable Rule Invariant:** Deterministic risk tiers (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`) and escalation states (`ESCALATION_REQUIRED`, etc.) are computed by deterministic rules prior to LLM invocation. The LLM explains the clinical rationale but **cannot modify or override the calculated risk tier**.
- **Grounding Layer:** `ClaimGroundingValidator` verifies that every factual sentence maps to an empirical evidence item.

#### D. Medical Knowledge RAG Agent
- **Task Category:** `TaskCategory.MEDICAL_RAG_SYNTHESIS`.
- **System Prompt:** Grounded aerospace medicine knowledge synthesis adhering to NASA Spaceflight Human-System Standards.
- **Safety Layer:** `GroundedMedicalGenerator.audit_response`:
  - Rejects forbidden autonomous diagnoses (e.g., definitive myocardial infarction).
  - Rejects unauthorized medication prescriptions.
  - Verifies mandatory 5-part structure: Retrieved Facts, Clinical Interpretation, Uncertainties, Citations, Missing Info.
  - Validates citation tags (e.g., `[NASA-STD-3001:P42]`) against retrieved chunks.

---

### 3. Multimodal Isolation Guarantee

Tasks requiring non-text modalities remain strictly isolated:
- `MEDICAL_DOCUMENT_OCR`: Routed exclusively to Groq Vision (`llama-3.2-11b-vision-preview`).
- `VOICE_INTERPRETATION`: Routed exclusively to Groq Whisper (`whisper-large-v3`).
- **Policy Enforcement:** If Groq fails on multimodal tasks, `CapabilityRegistry` marks them non-eligible for local fallback, raising `TaskNotEligibleError`. Multimodal payloads are **never routed to text-only Hugging Face or Ollama models**.
