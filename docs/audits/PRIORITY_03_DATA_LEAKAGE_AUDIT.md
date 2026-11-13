# TRUSTLINE — Priority 03: Data Leakage & Partitioning Audit

## 1. Executive Summary

This audit assesses the data partitioning, normalization, and evaluation protocols across the Personal Health Baseline subsystem against 6 recognized data leakage vectors.

### Overall Assessment
**LOW RISK IN CORE ENGINE / LEAKAGE-FREE IN RUNTIME PIPELINE**

The runtime baseline engine enforces strict identity isolation and temporal ordering. However, synthetic benchmark generation scripts contained distributional leakage due to shared Gaussian parameter generators.

---

## 2. Analysis Across 6 Data Leakage Vectors

| Leakage Vector | Description | Subsystem Implementation | Audit Finding | Risk Level |
| :--- | :--- | :--- | :--- | :--- |
| **1. Subject / Astronaut Leakage** | Telemetry or baseline parameters from Astronaut A leaking into Astronaut B's profile. | `BaselineDataPipeline.audit_and_filter_session` and `SafeBaselineUpdateManager` enforce `sess_astro == target_astro`. Cross-astronaut updates are rejected with `CROSS_ASTRONAUT_VIOLATION`. | **ZERO LEAKAGE** — Enforced at ingestion, repository, and LangGraph node boundaries. | **NONE** |
| **2. Session / Temporal Leakage** | Future observations leaking into past baseline calibration (lookahead bias). | `prepare_dataset` sorts sessions chronologically (`valid_sessions.sort(key=lambda x: x.timestamp)`). Baseline updates only absorb sessions with $t_{\text{session}} \ge t_{\text{baseline}}$. | **ZERO LEAKAGE** — Strict causal temporal ordering maintained. | **NONE** |
| **3. Normalization Leakage** | Computing global statistics (mean, median, MAD) across train and test partitions simultaneously. | Statistics are computed per-astronaut strictly from historical calibration sets. No global population centering is applied during deviation scoring. | **ZERO LEAKAGE** — Scale parameters derived exclusively from calibration history. | **NONE** |
| **4. Threshold Tuning Leakage** | Tuning deviation thresholds ($Z \ge 3.0$) on evaluation data to artificially optimize metrics. | Threshold ($Z = 3.0$) was established a priori from standard three-sigma Chebyshev/Gaussian outlier theory, not fitted to test sets. | **LOW RISK** — Constant fixed threshold; no empirical over-optimization. | **LOW** |
| **5. Synthetic Perturbation Artifacts** | Generating synthetic test sets using identical variance parameters as baseline calibration sets. | `benchmark.py` generated calibration and test data using identical $\sigma = 2.0\,\text{bpm}$ Gaussian noise. | **DISTRIBUTIONAL LEAKAGE IN BENCHMARK** — Artificially high benchmark score ($F_1 = 1.0$); mitigated by real WESAD validation. | **MEDIUM (Benchmark Only)** |
| **6. Overlapping Sliding Windows** | Autocorrelated feature leakage between adjacent overlapping sliding windows. | `wesad_window_features.csv` contains consecutive temporal windows. In real evaluation, adjacent windows exhibit autonomic autocorrelation. | **IDENTIFIED IN REAL EVALUATION** — Autocorrelation explains slight false alarm rate ($9.02\%$). Window shuffling avoided. | **LOW** |

---

## 3. Auditable Evidence

The complete machine-readable audit matrix is documented in:
`artifacts/audits/priority_03/independent_verification/data_leakage_audit_results.json`
