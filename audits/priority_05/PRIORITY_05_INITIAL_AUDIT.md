# PRIORITY 05: PRETRAINED RLHF MODEL INTEGRATION VIA HUGGING FACE API
## Initial Architecture Audit & Baseline Verification Report

### Executive Summary

Priority 05 (P05) transitions TRUSTLINE from general-purpose foundation models to human-aligned, instruction-tuned reasoning models. Operating in extreme aerospace medicine environments requires models whose behavioral envelope has been rigorously bounded by human preference optimization (Helpfulness, Truthfulness, and Harmlessness).

This initial audit establishes the pre-P05 system baseline, details the operational and hardware constraints governing this integration, and formally rules out on-device reinforcement learning from human feedback (RLHF) training.

---

### 1. Pre-P05 System Baseline & Architectural Starting Point

At the closure of Priority 04 (Hybrid AI Router & Local Fallback), TRUSTLINE established:
1. **LangGraph Supervisor Orchestration:** A deterministic stategraph coordinating three specialized biomedical agents:
   - **Sensor Quality Agent (SQA):** Real-time signal-to-noise ratio (SNR) assessment, motion artifact detection, and sensor status briefing.
   - **Personal Health Agent (PHA):** Clinical synthesis of astronaut telemetry, baseline comparison, and symptom classification.
   - **Risk Assessment Agent (RAA):** Deterministic risk rule evaluation, multi-domain escalation logic, and clinical interpretation.
   - **Medical Knowledge RAG:** Grounded vector search and citation-backed synthesis over aerospace clinical guidelines.
2. **Hybrid AI Router (`HybridAIRouter`):**
   - Cloud tier: Groq Cloud API (`qwen/qwen3.8-27b`).
   - Local fallback tier: Ollama local runtime (`qwen2.5:7b-instruct`) on Apple Silicon.
   - Circuit Breaker: 3-strike failure threshold, 60s recovery window, half-open probe testing.
   - Capability Registry: Strict policy taxonomy distinguishing `LOCAL_ELIGIBLE` from `CLOUD_ONLY` multimodal tasks.
3. **Verified Test Suite Baseline:** 480 test items (479 passed, 1 skipped live fixture, 0 failures, 0 errors).
4. **AST Comment Hygiene:** Zero `#` comments in `supervisor/` and `risk_assessment/`.

---

### 2. Operational & Hardware Constraints

A foundational engineering assessment was conducted on the development and target operational environment:
- **Host Architecture:** Apple Silicon Mac (M1).
- **Physical Memory:** 8 GB Unified Memory.
- **Compute Limitation:** 8 GB unified memory is insufficient to execute multi-billion parameter model training, full parameter fine-tuning, Low-Rank Adaptation (LoRA) backpropagation, Reward Model training, or Proximal Policy Optimization (PPO). Running PPO on even a 7B parameter model requires 40GB–80GB VRAM to hold actor, critic, reference model, and reward model weights simultaneously.
- **Mission Realism:** Spacecraft compute architectures (e.g., RAD750, Vorago ARM, or low-power embedded flight computers) have severe power and thermal constraints and cannot train RLHF models in-flight. Real-world mission architectures utilize flight-certified, ground-aligned models served via secure communications or preloaded frozen checkpoints.

---

### 3. Explicit Rejection of Local GPU Training

**ARCHITECTURAL DIRECTIVE:**
In accordance with mission requirements and physical hardware limitations:
- **NO PPO Training:** Proximal Policy Optimization training pipelines are strictly rejected.
- **NO Reward Model Training:** Pairwise Bradley-Terry reward model training is strictly rejected.
- **NO Direct Preference Optimization (DPO) Training:** Offline reference policy contrastive loss optimization is strictly rejected.
- **NO Supervised Fine-Tuning (SFT) GPU Pipeline:** Backpropagation and gradient updates are strictly rejected.

**SELECTED APPROACH:**
Inference integration with an existing, authoritative, open-weights foundation model that has undergone documented industrial-scale RLHF alignment, hosted via Hugging Face Serverless / Provider Inference APIs.

---

### 4. Integration Scope & Verification Gates

The scope of Priority 05 encompasses:
1. **Model Selection & Alignment Audit:** Rigorous trade study documenting the RLHF methodology of the candidate model.
2. **Provider Adapter Implementation:** `HuggingFaceProvider` implementing `BaseLLMProvider` with resilience, retries, and token security.
3. **Router Enhancement:** Dynamic primary routing to Hugging Face RLHF model with automatic multi-tier cascade (HF -> Groq -> Ollama -> Deterministic).
4. **Multi-Agent Shared Model Integration:** One model serving SQA, PHA, RAA, and Medical RAG while strictly preserving agent prompt boundaries, schemas, and validators.
5. **Runtime Feedback Collection Subsystem:** Out-of-band capture of expert flight surgeon evaluations (`APPROVED`, `REJECTED`, `EDITED`, `FLAGGED`) without online weight mutation.
6. **Unified Regression & AST Hygiene:** Maintaining 100% active test pass rate and strictly 0 comments in protected modules.
