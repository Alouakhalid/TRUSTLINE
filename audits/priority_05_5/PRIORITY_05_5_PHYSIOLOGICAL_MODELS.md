# PRIORITY 05.5 — COUPLED PHYSIOLOGICAL SIGNAL GENERATION MODELS

## 1. Mathematical Formulations

### 1.1 Cardiac Depolarization Wavelet Synthesis
Lead II ECG is synthesized using a sum of five Gaussian wavelets over centered phase $\theta \in [-\pi, \pi]$:
$$V_{ECG}(\theta) = \sum_{i \in \{P, Q, R, S, T\}} a_i \exp\left(-\frac{1}{2}\left(\frac{\theta - \theta_i}{b_i}\right)^2\right)$$
Leads I and III are derived via Einthoven's triangle projection vectors:
$$V_{Lead\ I} = 0.65 V_{Lead\ II} + \Delta_{atrial}, \quad V_{Lead\ III} = V_{Lead\ II} - V_{Lead\ I}$$

### 1.2 Respiratory Sinus Arrhythmia (RSA) Coupling
The instantaneous cardiac frequency $f_c(t)$ is coupled to the instantaneous respiratory phase signal $\theta_{resp}(t)$ and Mayer blood pressure waves (0.1 Hz):
$$f_c(t) = f_{base} \cdot \left(1 + w_{RSA} \sin(\theta_{resp}(t)) + 0.03 \sin(2\pi \cdot 0.1 \cdot t)\right)$$
where $w_{RSA}$ is proportional to target HRV RMSSD.

### 1.3 Bi-Component Electrodermal Activity (EDA)
$$G_{EDA}(t) = SCL(t) + \sum_k SCR_k(t - t_k)$$
where the phasic burst response follows the bi-exponential Bateman impulse function:
$$SCR(t) = A \left(\exp\left(-\frac{t}{\tau_{decay}}\right) - \exp\left(-\frac{t}{\tau_{rise}}\right)\right)$$
with $\tau_{rise} = 1.0\text{ s}$ and $\tau_{decay} = 3.5\text{ s}$.

### 1.4 Thermal Inertia
Two-compartment differential thermal equilibration:
$$\tau_{core} \frac{dT_{core}}{dt} = T_{eq}(MET) - T_{core}(t), \quad \tau_{skin} \frac{dT_{skin}}{dt} = T_{eq,skin}(MET) - T_{skin}(t)$$

## 2. Standardized Mission Operational Scenarios (A–F)
- **Scenario A (Baseline Rest):** HR ~ 68 bpm, RMSSD ~ 55 ms, Resp ~ 14 bpm, EDA ~ 2.5 µS, Temp ~ 36.8 °C, quiet motion.
- **Scenario B (EVA / High Physical Activity):** HR ~ 150 bpm, tachypnea Resp ~ 28 bpm, core temp ~ 37.9 °C, 2.0 Hz locomotion acceleration.
- **Scenario C (Acute Psychophysiological Stress):** Sympathetic surge: HR ~ 102 bpm, depressed RMSSD ~ 18 ms, frequent SCR bursts (>0.25/s).
- **Scenario D (Sleep / Deep Recovery):** Parasympathetic dominance: bradycardia HR ~ 52 bpm, elevated RMSSD ~ 75 ms, slow deep breathing ~ 11 bpm, quiescent EDA.
- **Scenario E (Hardware & Sensor Faults):** Injected flatline on ECG Lead II, EDA electrode peeling clipping, and 15% transmission packet drops.
- **Scenario F (Multi-Factor SPE Mission Composite):** Solar Particle Event alert (650 µGy/h) + acute astronaut stress response + EVA suit rotation.
