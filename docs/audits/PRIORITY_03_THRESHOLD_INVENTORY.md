# TRUSTLINE — Priority 03: Threshold Inventory & Reconciliation

## 1. Executive Summary

This document provides an exhaustive inventory of every parameter, boundary, threshold, and readiness constant across Priority 03, identifying discrepancies between previous documentation and actual code implementation.

---

## 2. Reconciled Threshold Matrix

| Parameter Name | Value in Code | Source File & Line | Documented Values | Status & Technical Analysis |
| :--- | :---: | :--- | :---: | :--- |
| **Detector Unusual Z** | `3.0` | `deviation_engine.py:23` | `2.5 and 3.0` | **RECONCILED:** Production default is $3.0$ robust Z (MAD). `benchmark.py:193` overrode this to $2.5$ for synthetic evaluation. Production engine and supervisor use $3.0$. |
| **Update Anomaly Guard** | `3.0` | `update_manager.py:28` | `3.0` | **CONSISTENT:** Blocks baseline update if composite anomaly $\ge 3.0$ or unusual signals $\ge 2$. |
| **MIN_SESSIONS_COLD** | `3` | `data_pipeline.py:218` | `3` | **CONSISTENT:** Fewer than 3 sessions assigns `INSUFFICIENT_DATA`. 3 sessions is mathematical minimum for non-trivial median and IQR. |
| **MIN_SESSIONS_WARM** | `5` | `data_pipeline.py:220` | `5 or 7` | **RECONCILED:** Code implements $5$ sessions across $\ge 2$ distinct calendar days for `ESTABLISHED` state. Draft documentation suggested 7, but 5 was implemented. |
| **Min Distinct Calendar Days** | `2` | `data_pipeline.py:220` | `2 or 5` | **RECONCILED:** Code enforces `distinct_days >= 2` to capture diurnal variation. |
| **STALE_THRESHOLD_DAYS** | `None` | `schemas.py:12` (enum only) | `5 or 30 days` | **DOCUMENTATION DISCREPANCY:** `BaselineReadinessState.STALE` exists in `schemas.py:12`, but there is **no code** calculating elapsed days or triggering staleness transitions. |
| **RECENCY_DECAY_HALF_LIFE** | `None` | `schemas.py:170` (cited in error) | `30 days` | **DOCUMENTATION DISCREPANCY:** Line 170 of `schemas.py` is `from_version: int`. `statistical_engine.py` computes standard unweighted sample median and MAD. Exponential half-life decay is not implemented. |
| **MIN_SQA_SCORE** | `0.60` | `data_pipeline.py:56` | `0.60 or 0.70` | **RECONCILED:** Code default in `BaselineDataPipeline` is `0.60`. Test docstrings cited $0.70$ from general SQA specifications, but actual gate is $0.60$. |
| **IQR_SCALE_FACTOR** | `1.349` | `statistical_engine.py:68` | `1.349` | **CONSISTENT:** Used when raw $\text{MAD} = 0.0$ (`effective_mad = iqr / 1.349`). Asymptotically exact for normal distributions. |
| **MAX_COMPOSITE_ANOMALY** | `3.0` | `update_manager.py:28` | `3.0` | **CONSISTENT:** Upper boundary for composite anomaly score beyond which session is quarantined from baseline learning. |
| **Rest Accelerometry Ceiling** | `1.05 g` | `context_engine.py:28` | `1.05 g` | **CONSISTENT BUT FLAWED:** Calibrated for Earth 1-g; invalid in spaceflight microgravity ($0\,g$). |
| **Rest Accelerometry Jitter** | `0.04 g` | `context_engine.py:28` | `0.04 g` | **CONSISTENT:** Standard deviation ceiling for quiet sitting/reclining. |
| **Rest Heart Rate Ceiling** | `78.0 bpm` | `context_engine.py:29` | `78.0 bpm` | **CONSISTENT BUT FLAWED:** Hardcodes population clinical limit into personalized baseline engine. |
| **Active Accelerometry Floor** | `1.15 g` | `context_engine.py:24` | `1.15 g` | **CONSISTENT BUT FLAWED:** Calibrated for Earth locomotion dynamics; invalid in orbital free-float. |

---

## 3. Statistical Interpretation Clarification

Previous reports claimed that a robust deviation score of $3.0\,\text{MAD}$ automatically implies a Gaussian probability of $p = 0.0027$.
- **Audit Clarification:** The robust Z-score is defined as:
$$Z_{\text{robust}} = \frac{0.6745 \times (x - \tilde{x})}{\text{MAD}}$$
The multiplier $0.6745$ ($1 / 1.4826$) ensures that $Z_{\text{robust}} \approx Z_{\text{standard}}$ **only if the underlying data distribution is Gaussian**. Physiological biosignals (such as HRV RMSSD and skin conductance) frequently exhibit heavy-tailed, skewed, or log-normal distributions. Therefore, a robust score of $3.0$ does **not** guarantee a theoretical $p = 0.0027$ across arbitrary autonomic telemetry.
