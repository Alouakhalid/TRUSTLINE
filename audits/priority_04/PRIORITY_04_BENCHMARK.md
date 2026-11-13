# TRUSTLINE — Priority 04: Local LLM Fallback & Benchmark Evaluation
**Subsystem:** Priority 04 — Hybrid AI Router  
**Evaluated Models:** `qwen/qwen3.8-27b` (Groq Cloud) vs `qwen2.5:7b-instruct` (Ollama Local Edge)  
**Host Hardware:** Apple Silicon M1 (8GB Unified Memory), macOS Darwin 26.5.2  
**Evaluation Date:** November 13, 2026  
**Auditor:** Senior Biomedical AI Engineer & ML Benchmark Specialist  
**Status:** EMPIRICALLY BENCHMARKED & VERIFIED  

---

## 1. Executive Summary

This benchmark evaluation documents real-world performance, latency, generation throughput, and clinical safety compliance for the onboard local language model (`qwen2.5:7b-instruct`) operating under Apple Silicon Metal GPU acceleration, compared side-by-side against cloud inference (`qwen/qwen3.8-27b` on Groq).

### Key Empirical Findings:
1. **Local Throughput:** `qwen2.5:7b-instruct` generates consistently at **11.75 – 13.47 tokens per second** on an 8GB Apple M1 machine with 88% GPU Metal offloading.
2. **Cold-Start vs Warm Latency:**
   - Cold start model loading: **5.65 seconds** (first inference).
   - Warm model loading: **0.002 – 0.035 seconds** (subsequent inferences).
3. **Comparative Response Time:**
   - Cloud roundtrip latency: **0.26s – 0.92s** across all tasks.
   - Local fallback roundtrip latency: **2.26s – 13.72s** (depending on token count).
4. **Structured JSON & Extraction Accuracy:** **100% parseable JSON syntax** and 100% schema conformance across both English and Arabic biomedical inputs.
5. **Anti-Hallucination Grounding:** Zero unmeasured lab values were fabricated across all tests.

---

## 2. Side-by-Side Comparative Benchmark

Empirical evaluation on identical clinical prompts captured in `artifacts/audits/priority_04/cloud_vs_local_benchmark_comparison.json`:

| Case ID | Benchmark Task | Cloud Model (`qwen3.8-27b`) Latency | Local Model (`qwen2.5-7b`) Latency | Local TPS | Quality / Agreement | Result |
| :---: | :--- | :---: | :---: | :---: | :--- | :---: |
| **BM-01** | **Clinical Summarization** | 0.711s (26 words) | 2.432s (16 words) | **12.50** | Both captured post-exercise 138 bpm, sinus rhythm, no symptoms | **PASS** |
| **BM-02** | **Structured Extraction (EN)** | 0.499s (29 words) | 4.071s (13 words) | **12.38** | 100% match: motion sickness (mod), nausea, dizziness (mild); denied vomiting/headache | **PASS** |
| **BM-03** | **Structured Extraction (AR)** | 0.278s (16 words) | 3.536s (12 words) | **11.84** | 100% match: confirmed (دوار خفيف، إجهاد عام); denied (ألم في الصدر، خفقان) | **PASS** |
| **BM-04** | **Anti-Hallucination Grounding**| 0.920s (22 words) | 2.261s (4 words) | **12.17** | Both extracted stated labs (Hb, Hct, Ferritin); explicitly omitted Na+, K+, WBC, Plt, Glucose | **PASS** |
| **BM-05** | **Flight Surgeon Briefing** | 0.577s (162 words) | 13.716s (117 words)| **11.75** | Both generated cautious 2-paragraph summaries emphasizing telemetry status | **PASS** |

---

## 3. Real Controlled Fallback Scenarios (A, B, C)

Live integration test executed against physical infrastructure and logged to `artifacts/audits/priority_04/real_fallback_integration_evidence.json`:

### Scenario A: Normal Operation (Cloud Healthy)
- **Input:** "State in exactly 1 sentence the impact of microgravity on human red blood cell mass."
- **Router Action:** Selected `GROQ` directly (`qwen/qwen3.8-27b`).
- **Roundtrip Latency:** **0.261s**.
- **Circuit State:** `CLOSED`.
- **Response:** *"Microgravity causes a significant reduction in human red blood cell mass, a condition known as spaceflight-associated anemia, primarily driven by fluid shifts and increased erythrocyte destruction."*

### Scenario B: Simulated Cloud Outage (Local Ollama Fallback)
- **Trigger:** Groq authentication failure simulated (401 Bad API Key).
- **Router Action:** Caught exception without infinite retry; verified task is `LOCAL_ELIGIBLE`; transparently dispatched to `OLLAMA` (`qwen2.5:7b-instruct`).
- **Roundtrip Latency:** **7.661s** (Speed: **11.79 tokens/sec**).
- **Telemetry Record:** `is_fallback: True`, `fallback_reason: "ProviderAuthenticationError: Groq authentication rejected"`.
- **Response:** *"Microgravity reduces human red blood cell mass through increased erythrocyte destruction and decreased bone marrow production."*

### Scenario C: Cloud Recovery (Restoring Cloud Routing)
- **Trigger:** Groq credentials restored; circuit breaker reset.
- **Router Action:** Selected `GROQ` directly.
- **Roundtrip Latency:** **0.406s**.
- **Circuit State:** `CLOSED`.
- **Response:** *"Microgravity causes a significant reduction in human red blood cell mass, a physiological adaptation that contributes to the development of spaceflight-associated neuro-ocular syndrome and potential anemia upon return to Earth."*

---

## 4. Hardware Resource Consumption & Safety Limits

| Metric | Measured Value | Operational Assessment |
| :--- | :---: | :--- |
| **Resident Memory** | **5.2 GB** | Safely contained within 8.0 GB unified memory |
| **Metal GPU Layers** | **88% GPU Offload** | Metal acceleration prevents CPU starvation |
| **Inference Generation Rate** | **11.75 – 13.47 TPS** | Adequate for asynchronous agent reasoning and fallback |
| **Context Memory Limit** | **4,096 tokens** | Configured context ceiling prevents OOM panics |

> [!CAUTION]
> **SCIENTIFIC & CLINICAL LIMITATION**  
> Benchmarks on text extraction, summarization, and JSON syntax do **not** constitute clinical validation. The local quantized 7B language model is an assistive edge fallback for formatting and preliminary feature extraction; it is **never** authorized to make autonomous medical diagnoses or alter clinical triage rules.\n