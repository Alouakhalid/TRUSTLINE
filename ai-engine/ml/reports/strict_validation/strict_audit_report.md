# TRUSTLINE Independent Machine Learning Research Audit & Validation Report
**Author:** Independent Machine Learning Auditor & Biomedical Signal Processing Expert  
**Evaluation Scope:** Strict Subject-Independent Validation on Held-Out Test Subjects (S10, S4, S6, S8)  
**Execution Date:** 2026-11-05  

---

## 1. Executive Summary & Final Decision

### Final Audit Determination:
# **CONDITIONALLY APPROVED — LIMITATIONS MUST BE ACKNOWLEDGED**

### Core Findings:
1. **Model Performance Champion:** The **`HistGradientBoosting`** supervised classifier achieved extraordinary sensitivity (**Recall: 97.56%**, 40/41 stress windows detected) and specificity (**Specificity: 96.05%**, 73/76 baseline windows correctly identified) with a False Alarm Rate of only **3.95%**. It passed all provisional acceptance criteria across all 4 held-out subjects.
2. **Unsupervised Anomaly Detection:** The **`Calibrated_IsolationForest`** on the 14 core features successfully achieved **Recall: 90.24%** (37/41 detected) with a clean, training-only calibrated threshold (tau = 0.47488). However, its False Alarm Rate (**21.05%**) slightly exceeded the provisional target (<= 20%) due to 8 baseline false alarms on Subject S4, warranting a **CONDITIONAL PASS**.
3. **Critical Methodological Flaw Identified:** The previously reported **`Ensemble_Anomaly_Detector`** was audited and marked **INVALID**. Investigation revealed that its decision threshold was derived via `np.quantile(ensemble_scores, 0.65)` directly on the test set, violating independent evaluation rules.
4. **Data Leakage Check:** Models `HistGradientBoosting`, `RandomForest_Supervised`, `ExtraTrees_Supervised`, and `Calibrated_IsolationForest` are completely clean and free of data leakage. Feature scalers and imputers were fit on training subjects only.
5. **Statistical Limitation:** With only N=4 held-out subjects, subject-level bootstrap demonstrates that recall confidence intervals range from [0.829, 1.000] for `HistGradientBoosting` and [0.756, 0.976] for `Calibrated_IsolationForest`. The statistical power is constrained by subject count.

---

## 2. Reproduced Benchmark Performance Matrix

| Model Architecture | Category | Features | Accuracy | Precision | Recall | F1-Score | Specificity | False Alarm Rate | ROC-AUC | TP | FN | FP | TN | Audit Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **HistGradientBoosting** | Supervised | 14 Core | **0.9658** | **0.9302** | **0.9756** | **0.9524** | **0.9605** | **0.0395** | **0.9910** | 40 | 1 | 3 | 73 | **PASS** |
| **RandomForest_Supervised** | Supervised | 14 Core | 0.9402 | 0.9048 | 0.9268 | 0.9157 | 0.9474 | 0.0526 | 0.9868 | 38 | 3 | 4 | 72 | **PASS** |
| **ExtraTrees_Supervised** | Supervised | 14 Core | 0.8974 | 0.8537 | 0.8537 | 0.8537 | 0.9211 | 0.0789 | 0.9612 | 35 | 6 | 6 | 70 | **PASS** |
| **Calibrated_IsolationForest** | Unsupervised | 14 Core | 0.8291 | 0.6981 | 0.9024 | 0.7872 | 0.7895 | 0.2105 | 0.9040 | 37 | 4 | 16 | 60 | **CONDITIONAL PASS** |
| **LocalOutlierFactor** | Unsupervised | 14 Core | 0.8205 | 0.8333 | 0.6098 | 0.7042 | 0.9342 | 0.0658 | 0.9284 | 25 | 16 | 5 | 71 | **FAIL** |
| **OneClassSVM** | Unsupervised | 14 Core | 0.7436 | 0.6122 | 0.7317 | 0.6667 | 0.7500 | 0.2500 | 0.8479 | 30 | 11 | 19 | 57 | **FAIL** |
| **EllipticEnvelope** | Unsupervised | 6 Top | 0.6496 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.6306 | 0 | 41 | 0 | 76 | **FAIL** |
| **Personalized_Baseline_Detector** | Unsupervised | 14 Core | 0.7949 | 0.8696 | 0.4878 | 0.6250 | 0.9605 | 0.0395 | 0.6377 | 20 | 21 | 3 | 73 | **INVALID** |
| **Ensemble_Anomaly_Detector** | Unsupervised | 14 Core | 0.8632 | 0.8049 | 0.8049 | 0.8049 | 0.8947 | 0.1053 | 0.9323 | 33 | 8 | 8 | 68 | **INVALID** |
| **IsolationForest_V1** | Unsupervised | 99 Full | 0.5983 | 0.3846 | 0.2439 | 0.2985 | 0.7895 | 0.2105 | 0.6062 | 10 | 31 | 16 | 60 | **FAIL** |
| **IsolationForest_V2** | Unsupervised | 69 Reduced | 0.6496 | 0.5000 | 0.1220 | 0.1961 | 0.9342 | 0.0658 | 0.6752 | 5 | 36 | 5 | 71 | **FAIL** |

---

## 3. Answers to Required Audit Inquiries

1. **Are the reported metrics reproducible?**  
   **Yes.** Every metric has been reproduced directly from raw features and ground-truth labels. The minor discrepancy in `predictions.csv` was identified as an index sort permutation (`ordered_indices` vs `test_df.index`), while the model weights and overall benchmark tables reproduced identically.
2. **Is the evaluation free from data leakage?**  
   **Yes for primary models (`HistGradientBoosting`, `RandomForest`, `Calibrated_IsolationForest`).** No test subjects contributed to training or preprocessing. However, `Ensemble_Anomaly_Detector` leaked test labels via test-quantile thresholding, and was marked **INVALID**.
3. **Is Recall sufficiently high?**  
   **Yes.** `HistGradientBoosting` achieved **97.56% Recall** (40/41 detected) and `Calibrated_IsolationForest` achieved **90.24% Recall** (37/41 detected), both exceeding the 80% threshold.
4. **Is the false alarm rate acceptable?**  
   **Yes for HistGradientBoosting (3.95%)** and **RandomForest (5.26%)**. For `Calibrated_IsolationForest`, the false alarm rate is **21.05%**, slightly exceeding the 20% target due to high baseline variance in Subject S4.
5. **Does the model generalize across all four unseen subjects?**  
   **Yes for HistGradientBoosting** (S10: 100%, S4: 88.89%, S6: 100%, S8: 100%). All four subjects exceed the 60% floor.
6. **Is the threshold-selection methodology valid?**  
   **Yes for production models.** Calibrated Isolation Forest derived its cutoff from the 85th percentile of training inliers. HistGradientBoosting uses the canonical 0.50 cutoff.
7. **Are the results statistically reliable enough for the stated scope?**  
   **Conditionally.** While performance is excellent, having only N=4 test subjects yields wide bootstrap confidence intervals. Additional validation on extended spaceflight cohorts is recommended.
8. **Does the current ML pipeline meet the acceptance criteria?**  
   `HistGradientBoosting` passes all acceptance criteria. `Calibrated_IsolationForest` receives a Conditional Pass.
9. **Is TRUSTLINE ready to proceed to the next development stage?**  
   **Yes, with documented conditions.** The project may proceed provided that the limitations (supervised assumptions for HGB, baseline false alarms on S4 for IF, and small test cohort) are formally acknowledged.
