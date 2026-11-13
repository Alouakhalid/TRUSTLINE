# TRUSTLINE — Priority 03: Performance & Latency Profile Verification

## 1. Executive Summary

This document verifies the performance profiling metrics reported for Priority 03, inspecting the benchmark harness, dataset volumes, I/O boundaries, and memory footprints.

---

## 2. Microbenchmark Timing Profile

From [`artifacts/audits/priority_03/performance_profile.json`](file:///Users/alikhalidalikhalid/TRUSTLINE/artifacts/audits/priority_03/performance_profile.json):

| Operation | Mean Latency | Median Latency | P95 Latency | P99 Latency | I/O & Execution Boundary |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Baseline Profile Construction** | 2.372 ms | 2.301 ms | 2.740 ms | 3.329 ms | In-memory numpy median, MAD, and IQR calculation over observation sessions. Zero database I/O. |
| **Baseline Profile Retrieval** | 0.261 ms | 0.249 ms | 0.318 ms | 0.411 ms | SQLite indexed query (`SELECT FROM astronaut_personal_baselines WHERE astronaut_id=?`) and JSON deserialization. |
| **Personal Deviation Evaluation** | 0.027 ms | 0.026 ms | 0.028 ms | 0.040 ms | In-memory closed-form robust Z-score calculation: $0.6745 \times (x - \tilde{x}) / \text{MAD}$. Zero database I/O. |
| **Safe Baseline Update & Audit** | 5.084 ms | 5.006 ms | 6.320 ms | 6.636 ms | Full transaction: deviation evaluation + anti-contamination guard + active profile update + history snapshot + audit log commit. |

---

## 3. Footprint & Resource Metrics

- **Edge Database Disk Footprint:** $30,982,144\,\text{bytes}$ ($30.98\,\text{MB}$) in `./data/trustline_edge.db`.
- **Host Process Resident Set Size (RSS):** $388.22\,\text{MB}$.
  - *Audit Clarification:* This represents the complete Python process footprint, including the Python runtime, PyTorch C-libraries, Scikit-learn extensions, SQLAlchemy ORM pools, and SQLite caches. It does not reflect the memory consumption of the baseline data structure alone.
- **End-to-End Workflow Latency:** Across the full 10-node LangGraph Supervisor pipeline (including SQA, PHA, RAA, and LLM synthesis), total workflow latency averages $1.8$ to $3.5$ seconds when Groq LLM calls are active, and $< 120\,\text{ms}$ under deterministic fallback mode.
