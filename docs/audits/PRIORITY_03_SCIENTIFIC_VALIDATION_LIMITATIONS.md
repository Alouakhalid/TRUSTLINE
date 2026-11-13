# TRUSTLINE — Priority 03: Scientific Validation, Benchmarks & Limitations

## 1. Executive Summary

This document establishes the scientific boundaries of the evaluations conducted for Priority 03, resolving the conflation between synthetic perturbation benchmarks and human biosignal evaluations, and documenting the statistical limitations of the WESAD observational evaluation.

---

## 2. Evaluation Suite 1: Synthetic Controlled Evaluation

### Benchmark Specification
- **Label:** **Synthetic Controlled Evaluation — Not Real-World Medical Validation**
- **Script Location:** [`ai-engine/agents/personal_health/baseline/evaluation/benchmark.py`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/agents/personal_health/baseline/evaluation/benchmark.py)
- **Cohort:** 5 simulated subjects (`SUBJ_S2` .. `SUBJ_S6`).
- **Data Volume:** 250 total sessions (50 calibration sessions, 200 evaluation sessions).
- **Perturbation Mechanics:** Injected a step shift of $+32.0\,\text{bpm}$ into `hr_mean_bpm` with Gaussian noise $\sigma = 2.0\,\text{bpm}$.

### Mathematical Deconstruction
$$\text{Separation} = \frac{100.0 - 68.0}{2.0} = 16.0\,\sigma$$
- Under a $16\,\sigma$ separation, any threshold between $3.0\,\sigma$ and $15.0\,\sigma$ achieves $F_1 = 1.0000$ and $\text{FAR} = 0.00\%$.
- **Scientific Conclusion:** This benchmark proves the internal mathematical mechanics of the robust MAD scale under extreme step perturbations. It does **NOT** validate astronaut anomaly detection or clinical diagnostic utility.
- **EWMA Breakdown:** EWMA failed catastrophically ($F_1 = 0.1176$, $\text{Recall} = 0.0625$) because its recursive weighting ($\mu_t = \alpha x_t + (1 - \alpha) \mu_{t-1}$) assimilated the $+32\,\text{bpm}$ spike after the initial window, blinding it to sustained tachycardia.

---

## 3. Evaluation Suite 2: Real Human Biosignal Observational Validation

### Observational Specification
- **Label:** **Exploratory within-subject laboratory stress-versus-baseline evaluation**
- **Dataset:** Real human multi-modal recordings from WESAD ([`wesad_window_features.csv`](file:///Users/alikhalidalikhalid/TRUSTLINE/ai-engine/ml/data/processed/wesad_window_features.csv)).
- **Cohort:** 15 real human subjects (S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S13, S14, S15, S16, S17).
- **Protocol:**
  - Initial 10 baseline windows ($10 \times 60\,\text{s} = 600\,\text{s}$) per subject used for calibration.
  - Remaining baseline windows used as nominal test windows ($133$ windows total).
  - Stress condition windows used as anomaly test windows ($155$ windows total).
  - Total evaluation windows: $288$ windows across 15 subjects.

### Aggregate Performance Results
- **True Positives (TP):** $155$
- **False Positives (FP):** $12$ (4 in S2, 4 in S6, 2 in S15, 2 in S17)
- **True Negatives (TN):** $121$
- **False Negatives (FN):** $0$
- **Sensitivity / Recall:** **$100.00\%$** ($155 / 155$)
- **Precision:** **$92.81\%$** ($155 / 167$)
- **False Alarm Rate (FAR):** **$9.02\%$** ($12 / 133$)
- **Specificity:** **$90.98\%$** ($121 / 133$)
- **$F_1$ Score:** **$0.9627$**
- **ROC-AUC:** **$0.9880$**

---

## 4. Methodological & Statistical Limitations

### 4.1 Sliding Window Overlap & Temporal Autocorrelation
- In WESAD feature extraction, 60-second windows were shifted with substantial temporal overlap.
- Adjacent windows share 50% to 80% of raw physiological samples.
- **Statistical Implication:** Consecutive windows are **temporally autocorrelated** and cannot be treated as statistically independent identically distributed (i.i.d.) observations. When autonomic arousal fluctuates near the decision boundary, false positives cluster in contiguous blocks (observed in S2 and S6).

### 4.2 Laboratory Stress vs Astronaut Pathophysiology
- WESAD induces laboratory acute social/cognitive stress (Trier Social Stress Test).
- Spaceflight medical events (decompression sickness, intracranial hypertension, orthostatic intolerance, space motion sickness) exhibit distinct physiological dynamics.
- WESAD validates within-subject autonomic deviation detection under terrestrial conditions, but does **NOT** validate spaceflight clinical safety.

### 4.3 Peripheral vs Core Temperature
- Telemetry captures peripheral skin temperature (chest/wrist thermistors), not core body temperature. Peripheral vasoconstriction during stress or ambient thermal changes induces temperature shifts that must not be interpreted as core hypothermia or fever.
