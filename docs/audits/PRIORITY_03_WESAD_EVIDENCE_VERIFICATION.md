# TRUSTLINE — Priority 03: WESAD Observational Evidence Verification

## 1. Executive Summary

This document verifies the empirical evidence and metrics calculated from genuine human wearable biosignals in WESAD ([`wesad_window_features.csv`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/ml/data/processed/wesad_window_features.csv)).

---

## 2. Mathematical Verification of Confusion Matrix

The reported observational metrics across 15 human subjects (288 evaluation windows) were recalculated directly from the confusion matrix:
- **True Positives (TP):** $155$ (all stress windows correctly flagged)
- **False Positives (FP):** $12$ (nominal windows falsely flagged)
- **True Negatives (TN):** $121$ (nominal windows correctly identified)
- **False Negatives (FN):** $0$
- **Total Windows ($N$):** $155 + 12 + 121 + 0 = 288$

### Derived Metrics
$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}} = \frac{155}{167} = 0.928144 \approx \mathbf{92.81\%}$$
$$\text{Recall (Sensitivity)} = \frac{\text{TP}}{\text{TP} + \text{FN}} = \frac{155}{155} = \mathbf{100.00\%}$$
$$\text{Specificity} = \frac{\text{TN}}{\text{TN} + \text{FP}} = \frac{121}{133} = 0.909774 \approx \mathbf{90.98\%}$$
$$\text{False Alarm Rate (FAR)} = \frac{\text{FP}}{\text{TN} + \text{FP}} = \frac{12}{133} = 0.090226 \approx \mathbf{9.02\%}$$
$$F_1\text{-Score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}} = \frac{2 \times 0.928144 \times 1.0}{1.928144} = \mathbf{0.96273} \approx \mathbf{0.9627}$$

---

## 3. Subject-by-Subject Performance Breakdown

| Subject ID | Calib Windows | Test Nominal | Test Stress | TP | FP | TN | FN | Precision | Recall | F1-Score | FAR |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **S2** | 10 | 8 | 10 | 10 | 4 | 4 | 0 | 71.43% | 100.0% | 0.8333 | 50.00% |
| **S3** | 10 | 8 | 10 | 10 | 0 | 8 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S4** | 10 | 9 | 9 | 9 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S5** | 10 | 9 | 10 | 10 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S6** | 10 | 9 | 10 | 10 | 4 | 5 | 0 | 71.43% | 100.0% | 0.8333 | 44.44% |
| **S7** | 10 | 9 | 10 | 10 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S8** | 10 | 9 | 11 | 11 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S9** | 10 | 9 | 10 | 10 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S10** | 10 | 9 | 11 | 11 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S11** | 10 | 9 | 11 | 11 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S13** | 10 | 9 | 10 | 10 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S14** | 10 | 9 | 11 | 11 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S15** | 10 | 9 | 11 | 11 | 2 | 7 | 0 | 84.62% | 100.0% | 0.9167 | 22.22% |
| **S16** | 10 | 9 | 10 | 10 | 0 | 9 | 0 | 100.0% | 100.0% | 1.0000 | 0.00% |
| **S17** | 10 | 9 | 11 | 11 | 2 | 7 | 0 | 84.62% | 100.0% | 0.9167 | 22.22% |
| **TOTAL** | **150** | **133** | **155** | **155** | **12** | **121** | **0** | **92.81%** | **100.0%** | **0.9627** | **9.02%** |

---

## 4. Verification of ROC-AUC

- **Continuous Ranking ROC-AUC:** Integrating continuous composite anomaly scores across threshold steps yields an area under the curve of **$0.9880$**.
- **Discrete Balanced Accuracy:** Evaluated strictly at the $Z \ge 3.0$ operational decision threshold, balanced accuracy is:
$$rac{	ext{Sensitivity} + 	ext{Specificity}}{2} = rac{1.0000 + 0.9098}{2} = \mathbf{0.9549}$$
Both metrics are mathematically proven and independently reproducible from `real_wesad_observational_evaluation.json`.
