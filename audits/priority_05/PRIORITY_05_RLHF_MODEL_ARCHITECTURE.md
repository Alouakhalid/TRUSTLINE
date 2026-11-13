# PRIORITY 05: PRETRAINED RLHF MODEL ARCHITECTURE
## Structural Specifications, Alignment Dynamics, and Safety Envelope

### Executive Summary

This specification documents the architectural layout, parameter allocation, tokenization dynamics, and post-training alignment mechanisms of `meta-llama/Llama-3.1-8B-Instruct`, the primary hosted RLHF model integrated into TRUSTLINE.

---

### 1. Model Structural Architecture

`meta-llama/Llama-3.1-8B-Instruct` is an autoregressive decoder-only dense transformer:

| Hyperparameter | Specification |
|---|---|
| **Total Parameters** | 8.03 Billion |
| **Hidden Dimension ($d_{\text{model}}$)** | 4,096 |
| **Number of Transformer Layers** | 32 |
| **Attention Query Heads ($h_q$)** | 32 (head dim = 128) |
| **Key/Value Heads ($h_{kv}$)** | 8 (Grouped-Query Attention, 4:1 ratio) |
| **Feed-Forward Dimension ($d_{ff}$)** | 14,336 (SwiGLU activation) |
| **Vocabulary Size** | 128,256 tokens (tiktoken BPE) |
| **Positional Embeddings** | Rotary Position Embeddings (RoPE) with scaled theta ($500,000$) |
| **Maximum Sequence Length** | 131,072 tokens (128k effective) |
| **Precision** | Bfloat16 / FP8 hosted quantization |

Grouped-Query Attention (GQA) dramatically reduces Key-Value cache memory overhead during inference, enabling low-latency multi-turn agent conversations without degrading long-context retrieval fidelity.

---

### 2. Multi-Stage RLHF Alignment Pipeline

```
Pretrained Base Model (Llama 3.1 8B)
          │
          ▼
┌──────────────────────────────────────────────┐
│ Round 1-2: SFT + Synthetic Data Bootstrapping │
└──────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────┐
│ Round 3-4: Rejection Sampling Filtering      │
│ (Scored via Pairwise Reward Model)           │
└──────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────┐
│ Round 5-6: Direct Preference Optimization    │
│ (Helpfulness vs Harmlessness Objective)      │
└──────────────────────────────────────────────┘
          │
          ▼
Deployable Aligned Policy (Llama-3.1-8B-Instruct)
```

#### Dual Preference Objective
Meta aligned Llama 3.1 using distinct reward heads for **Helpfulness** and **Safety**:
1. **Helpfulness Objective:** Promotes precision, clinical diagnostic clarity, thorough explanation of physiological phenomena (e.g. cephalad fluid shift, spaceflight osteopenia), and structured formatting.
2. **Safety Objective:** Suppresses hazardous behaviors, unverified prescriptive advice, autonomous medication changes, and hallucinations contrary to user-supplied context.

---

### 3. Alignment Tax & Aerospace Operational Mitigation

The "alignment tax" refers to potential performance degradation in raw technical reasoning resulting from overly conservative safety fine-tuning (e.g. refusal to discuss medical pathology out of caution).

In TRUSTLINE, this is mitigated by:
1. **Pre-Engineered System Prompts:** Structured system prompts clarify the agent's authorized role as an NASA Flight Surgeon decision-support tool.
2. **Deterministic Pre-Computation:** Physiological anomaly detection, signal-to-noise calculation, and escalation tiers are computed deterministically before reaching the LLM.
3. **Clinical Output Validators:** `ClinicalSynthesisValidator` and `ClaimGroundingValidator` audit the model's outputs post-generation, ensuring facts remain grounded without relying solely on the model's internal self-censorship.
