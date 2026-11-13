# TRUSTLINE — Priority 03: Evidence Reconciliation & Inventory

## 1. Executive Summary

This document performs a forensic claim-by-claim reconciliation comparing assertions made in previous Priority 03 reports against the verified code, database schemas, raw datasets, and test execution artifacts.

---

## 2. Complete Evidence Inventory & Claim Verification

| # | Claim in Prior Reports | Source File / Artifact | Independent Verification Findings | Audit Status |
| :---: | :--- | :--- | :--- | :---: |
| 1 | Robust baseline achieves $F_1 = 1.0000$ and $\text{FAR} = 0.00\%$ on WESAD subjects. | `baseline/evaluation/benchmark.py` | **FALSE CONFLATION.** The script evaluated synthetic Gaussian step perturbations ($+32\,\text{bpm}$ on simulated arrays), NOT real WESAD recordings. Labeled as Category B. | **CORRECTED & RECLASSIFIED** |
| 2 | Robust baseline evaluated on real human WESAD sensor features. | `ml/data/processed/wesad_window_features.csv` | **VERIFIED.** Real evaluation across 15 subjects (288 windows) achieved $F_1 = 0.9627$, Recall = $100.0\%$, Precision = $92.81\%$, FAR = $9.02\%$. | **VERIFIED FACT** |
| 3 | Baseline deviation detector threshold is $Z \ge 3.0$. | `baseline/deviation_engine.py:23` | **VERIFIED IN PRODUCTION.** Default parameter is $3.0$. However, `benchmark.py:193` overrode this to $2.5$. Production uses $3.0$. | **VERIFIED WITH RECONCILIATION** |
| 4 | Baseline readiness requires 3 cold and 7 warm sessions. | `baseline/data_pipeline.py:218-220` | **PARTIALLY INACCURATE.** Code implements 3 cold (`INSUFFICIENT_DATA`), but warm (`ESTABLISHED`) requires **5 sessions** and **$\ge 2$ distinct calendar days**, not 7 sessions. | **CORRECTED TO ACTUAL CODE** |
| 5 | Baselines older than 5 days trigger `STALE` status per `schemas.py:165`. | `baseline/schemas.py:165` | **FALSE CITATION.** `schemas.py:12` defines enum `STALE`, but lines 152-165 define `ObservationSession`. No background decay or automated staleness timer exists in code. | **UNCORRECTED SPECIFICATION** |
| 6 | Baselines apply a 30-day exponential decay half-life per `schemas.py:170`. | `baseline/schemas.py:170` | **FALSE CITATION.** Line 170 is `from_version: int`. `statistical_engine.py` computes unweighted median and MAD over all sessions; no exponential decay function exists. | **UNCORRECTED SPECIFICATION** |
| 7 | Baseline update blocks sessions with SQA score $< 0.70$. | `baseline/data_pipeline.py:56` | **PARTIALLY INACCURATE.** Default in `BaselineDataPipeline` is `min_quality_score = 0.60`. Test docstrings mentioned $0.70$, but actual threshold in code is $0.60$. | **CORRECTED TO ACTUAL CODE** |
| 8 | Monotonic rollback restores historical version without deleting history. | `baseline/repository.py:164` | **VERIFIED.** Restoring v1 when v2 is active creates v3 with restored payload. Historical snapshots and audit logs are preserved. | **VERIFIED FACT** |
| 9 | SQLite baseline audit trail is immutable. | `baseline/repository.py:119` | **TECHNICALLY MISLEADING.** Immutability is application-level append-only. There are no database-level restrictions, cryptographic hashes, or tamper-proof storage. | **RECLASSIFIED AS APPEND-ONLY** |
| 10 | Personal baseline storage at rest is encrypted. | `data/trustline_edge.db` | **FALSE.** Database is standard plaintext SQLite. No SQLCipher or AES-256 GCM encryption is present. | **CLASSIFIED AS HIGH RISK** |
| 11 | Full repository regression contains 455 tests. | Repository pytest suites | **VERIFIED.** Total core tests = 455 (SQA: 45, PHA: 211, RAA: 86, Supervisor: 113). All 455 executed and passed. | **VERIFIED FACT** |
| 12 | Discrepancy between 454 passed / 1 skipped vs 455 passed / 0 skipped. | `test_document_review_workflow.py:251` | **VERIFIED.** `test_08_live_groq_vision_real_api_call` skips if `GROQ_API_KEY` is unset (454/1). When `.env` has active key, test passes (455/0). | **VERIFIED FACT** |
| 13 | Stress test suite was executed. | `stress_test_results/regression_tests/` | **VERIFIED.** All 46 stress tests explicitly executed via pytest; all 46 passed in 62.45s. | **VERIFIED FACT** |

---

## 3. Auditable Evidence Traceability

All reconciliation entries are cross-referenced against raw evidence files in:
`artifacts/audits/priority_03/independent_verification/`
- `priority_03_evidence_manifest.json`
- `priority_03_threshold_inventory.json`
- `priority_03_test_inventory.json`
- `priority_03_benchmark_reproduction.json`
