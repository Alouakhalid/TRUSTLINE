# TRUSTLINE — Priority 03: Threshold Justification Audit

## 1. Executive Summary

This document reviews every hardcoded parameter, clinical boundary, readiness criterion, and anomaly threshold implemented in Priority 03. Each threshold is classified by its justification type, clinical rationale, and operational flight risk.

---

## 2. Threshold Catalog & Justification Matrix

| Parameter | Value | Source Location | Category | Justification Type | Clinical / Operational Rationale | Flight Readiness & Research Limitations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `rest_accel_max` | $1.05\,g$ | `context_engine.py:28` | Context Inference | Engineering Safety Bound | Calibrated for 1-g Earth gravity where resting body experiences $1.0\,g$ gravitational force plus minor postural sway $< 0.05\,g$. | **FLIGHT BLOCKER:** Invalid in microgravity ($0\,g$). In orbit, resting astronaut experiences $\sim 0\,g$. |
| `rest_accel_jitter` | $0.04\,g$ | `context_engine.py:28` | Context Inference | Empirical / Biomedical | Maximum standard deviation of torso acceleration observed during quiet reclining in WESAD human studies. | Valid for torso sensor; wrist-worn sensors exhibit higher fidget noise. |
| `rest_hr_ceiling` | $78.0\,\text{bpm}$ | `context_engine.py:29` | Context Inference | Population Limit | Standard resting tachycardia clinical boundary. | **PHILOSOPHICAL VIOLATION:** Hardcoded population threshold violates individualized baseline philosophy. |
| `active_accel_min` | $1.15\,g$ | `context_engine.py:24` | Context Inference | Engineering Safety Bound | Locomotion threshold on Earth where walking/running dynamics generate sustained $> 0.15\,g$ net inertial acceleration. | Invalid in orbit without tether force integration (e.g. T2 treadmill bungee loading). |
| `active_accel_jitter` | $0.10\,g$ | `context_engine.py:24` | Context Inference | Empirical / Biomedical | Standard deviation indicating rhythmic bodily locomotion. | May produce false alarms during spacecraft thruster burns or docking vibrations. |
| `MIN_SESSIONS_PROVISIONAL` | $3\,\text{sessions}$ | `data_pipeline.py:218` | Readiness Assessment | Mathematical / Statistical | Minimum mathematical sample size required to compute non-trivial Median and IQR without pure interpolation. | High statistical uncertainty; profile marked PROVISIONAL. |
| `MIN_SESSIONS_ESTABLISHED` | $5\,\text{sessions}$ | `data_pipeline.py:220` | Readiness Assessment | Engineering Safety Bound | Requires at least 5 sessions across $\ge 2$ distinct calendar days to capture diurnal circadian variability. | Recommended 14 days pre-launch for actual astronaut flight operations. |
| `STALE_THRESHOLD_DAYS` | $5.0\,\text{days}$ | `schemas.py:165` | Readiness Assessment | Biomedical Mission Rule | Acute microgravity adaptation (cephalic fluid shift, space motion sickness) occurs rapidly during flight days 1-5. | Generates audit warning in health report, prompting recalibration. |
| `RECENCY_DECAY_HALF_LIFE` | $30.0\,\text{days}$ | `schemas.py:170` | Readiness Assessment | Biomedical Mission Rule | Long-duration spaceflight remodeling (cardiovascular deconditioning, plasma volume loss) operates on 30-day half-life. | Assumes monotonic adaptation; acute illness requires profile branching. |
| `UNUSUAL_Z_THRESHOLD` | $3.0\,\text{MAD}$ | `deviation_engine.py:23` | Deviation Detection | Statistical Standard | Under normal distribution, $|Z| \ge 3.0$ corresponds to $p < 0.0027$ ($99.73\%$ specificity), suppressing false alarms. | Low sensitivity to subtle, insidious physiological degradation. |
| `IQR_SCALE_FACTOR` | $1.349$ | `statistical_engine.py:68` | Deviation Detection | Mathematical Constant | Normal distribution equivalence: $\text{MAD} = \text{IQR} / 1.34898$. Used when raw $\text{MAD} = 0$. | Exact for Gaussian distributions; slightly underestimates heavy-tailed scale. |
| `MIN_SQA_SCORE` | $0.60 / 0.70$ | `data_pipeline.py:56` | Anti-Contamination | Engineering Safety Bound | Prevents degraded, noisy sensor telemetry from contaminating longitudinal baseline statistics. | High gating drops data during sensor malfunction; correctly flags MISSING. |
| `MAX_COMPOSITE_ANOMALY` | $3.0$ | `update_manager.py:28` | Anti-Contamination | Engineering Safety Bound | Prevents baseline updating during acute physiological crisis or anomalous episodes. | May block recalibration during persistent physiological adaptation. |

---

## 3. Auditable Evidence

The machine-readable threshold inventory is persisted in:
`artifacts/audits/priority_03/independent_verification/threshold_inventory.json`
