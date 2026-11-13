# TRUSTLINE — Priority 03: Context Validation & Microgravity Limitations

## 1. Executive Summary

This document evaluates the physiological context classification engine (`baseline/context_engine.py`). It specifically investigates the physical assumptions underlying kinetic accelerometry and assesses the system's operational viability in orbital microgravity ($0\,g$).

---

## 2. Gravitational Vector Physics & Spaceflight Discrepancy

### Earth 1-g Physics vs Orbital Microgravity
In terrestrial environments:
$$\mathbf{a}_{\text{measured}} = \mathbf{a}_{\text{linear}} + \mathbf{g}$$
At rest on Earth, $|\mathbf{a}_{\text{measured}}| = 1.0\,g_0 \approx 9.81\,\text{m/s}^2$.

In low Earth orbit (ISS / Gateway):
$$\mathbf{g}_{\text{apparent}} = 0\,g$$
At rest in free-float microgravity:
$$|\mathbf{a}_{\text{measured}}| \approx 0.0\,g$$

### Implementation Inspection in `context_engine.py`
```python
# Low motion rest state
if acc_mag <= 1.05 and (acc_std is not None and acc_std <= 0.04):
    if hr is not None and hr <= 78.0:
        return BaselineContextType.REST

# High physical locomotion / exercise
if acc_mag > 1.15 or (acc_std is not None and acc_std > 0.10):
    return BaselineContextType.ACTIVITY
```

### Critical Spaceflight Defects
1. **Free-Float Invalidation:** In orbit, an astronaut translationally coasting through a module experiences $|\mathbf{a}| \approx 0.02\,g$. Because $0.02 \le 1.05$, the system will classify this state as `REST` even if the astronaut is actively working with tools or moving translationally.
2. **Exercise Misclassification:** Zero-g exercise devices (CEVIS cycle ergometer, T2 treadmill, ARED resistive exercise) require vibration isolation and harness bungee cords. Acceleration signals do not center around $1.0\,g$. An astronaut exercising vigorously without harness pre-load could fail to trigger `acc_mag > 1.15\,g`.
3. **Flight Surrender Recommendation:** For spaceflight deployment, context inference must rely on:
   - Dynamic acceleration norm: $\Delta a = \|\mathbf{a}(t) - \bar{\mathbf{a}}\|$
   - Gyroscopic angular velocity: $\omega_{\text{gyro}}$
   - Crew timeline / mission schedule telemetry (e.g. ISS daily summary schedule / sleep windows).

---

## 3. Population Hardcoding in Personalized Rest Inference

The condition:
```python
if hr is not None and hr <= 78.0:
    return BaselineContextType.REST
```
embeds an arbitrary population boundary into an individualized baseline engine.

- **False Negatives:** An astronaut experiencing mild orthostatic stress or fluid shift with resting heart rate of $80\,\text{bpm}$ will never be assigned `REST` context, even while deeply asleep.
- **Remediation:** Context engine should infer rest by comparing incoming heart rate to the astronaut's own $P_{25}$ historical distribution ($HR < P_{25,\text{personal}}$), preserving the personalized baseline paradigm.

---

## 4. Auditable Evidence

The full test case results and evaluation metrics are recorded in:
`artifacts/audits/priority_03/independent_verification/context_evaluation_results.json`
