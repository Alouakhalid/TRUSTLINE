# PRIORITY 05: HUGGING FACE API INTEGRATION
## Provider Adapter Implementation, Resilience Mechanics, and Error Classification

### Executive Summary

The Hugging Face Inference ecosystem provides production-grade serverless and dedicated model routing. This document details the technical implementation of `HuggingFaceProvider`, its integration into `hybrid_ai`, and its error handling architecture.

---

### 1. Architectural Topology

```
┌────────────────────────────────────────────────────────┐
│                   TRUSTLINE Agent Layer                │
│    (Sensor Quality, Personal Health, Risk, RAG)        │
└───────────────────────────┬────────────────────────────┘
                            │ ProviderRequest
                            ▼
┌────────────────────────────────────────────────────────┐
│               Hybrid AI Router (Priority 04/05)        │
│                                                        │
│  1. Check eligibility (Multimodal -> Groq Only)        │
│  2. Circuit Breaker allows?                            │
│  3. HF Provider configured?                            │
└─────────────┬──────────────────────────┬───────────────┘
              │ [Primary Cloud]          │ [Fallback Cloud]
              ▼                          ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│    HuggingFaceProvider    │ │       GroqProvider       │
│                           │ │                          │
│ - InferenceClient / Router│ │ - Groq Cloud API         │
│ - Llama-3.1-8B-Instruct   │ │ - Qwen 3.8-27b           │
│ - Exponential Backoff     │ │ - Vision / Whisper       │
└─────────────┬─────────────┘ └──────────┬───────────────┘
              │                          │
              │ [Both Cloud Providers Fail]
              ▼
┌────────────────────────────────────────────────────────┐
│               Ollama Local Fallback Provider           │
│               - Apple Silicon M1 (7B-Instruct)         │
└────────────────────────────────────────────────────────┘
```

---

### 2. Provider Implementation Details (`HuggingFaceProvider`)

Located in [`ai-engine/hybrid_ai/huggingface_provider.py`](ai-engine/hybrid_ai/huggingface_provider.py):
- **Base Class:** Inherits from `BaseLLMProvider(ProviderType.HUGGINGFACE)`.
- **Client Protocol:**
  - Native `huggingface_hub.InferenceClient` utilizing OpenAI-compatible chat completion endpoints.
  - Secondary fallback to `openai.OpenAI` client targeting `https://router.huggingface.co/v1`.
- **Environment Configuration:**
  - `HF_TOKEN` / `HUGGINGFACE_API_KEY`: Bearer authentication token.
  - `HF_MODEL_ID`: Default `meta-llama/Llama-3.1-8B-Instruct`.
  - `HF_INFERENCE_PROVIDER`: Routing policy (default `auto` across Together, Cerebras, Sambanova backends).
  - `HF_ROUTER_BASE_URL`: Endpoint base URL (`https://router.huggingface.co/v1`).
- **Resilience Parameters:**
  - Default timeout: 25.0 seconds.
  - Max retries: 2 bounded attempts.
  - Exponential backoff: $t_{\text{wait}} = 1.0 \times 2^{\text{attempt}}$ seconds.

---

### 3. Error Classification & Structured Exception Mapping

Every raw network, HTTP, and API error is mapped to TRUSTLINE's standard provider exception taxonomy:

| HTTP Status / Condition | Raw HF Exception | TRUSTLINE Mapped Exception | Router Action |
|---|---|---|---|
| **401 Unauthorized** | `Unauthorized`, `Invalid token` | `ProviderAuthenticationError` | Fatal to HF tier; immediately cascades to Groq (no useless retries). |
| **429 Rate Limit** | `Too Many Requests`, `Rate limit` | `ProviderRateLimitError` | Bounded exponential backoff (2 attempts); cascades to Groq if exhausted. |
| **408 / Timeout** | `ReadTimeout`, `timed out` | `ProviderTimeoutError` | Retry with backoff; cascades to Groq if exhausted. |
| **500 / 503 Overloaded**| `Model is loading`, `503 Service Unavailable` | `ProviderUnavailableError` | Retry; cascades to Groq if unavailable. |
| **Missing Token** | Unset `HF_TOKEN` | `ProviderUnavailableError` | Bypasses HF tier gracefully during initialization or air-gapped runs. |

---

### 4. Health Check Probe Architecture

`HuggingFaceProvider.health_check()` executes a lightweight probe:
1. When configured, queries `client.get_endpoint_info(model)` or probes `https://router.huggingface.co/v1/models` with a 5-second timeout.
2. Returns structured `ProviderHealth` with latency metrics and provider metadata.
3. Detects invalid tokens immediately, transitioning health status to `UNAVAILABLE` without throwing unhandled exceptions.
