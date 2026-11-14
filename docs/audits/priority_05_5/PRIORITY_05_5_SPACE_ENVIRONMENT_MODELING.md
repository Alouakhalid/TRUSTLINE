# PRIORITY 05.5 — SPACE ENVIRONMENT & RADIATION DOSIMETRY MODELING

## 1. Space Radiation Physics

### 1.1 Galactic Cosmic Rays (GCR) & Solar Particle Events (SPE)
Ambient deep space radiation comprises:
1. **GCR Background:** Omnidirectional flux of relativistic protons and heavy HZE nuclei producing a baseline absorbed dose rate of 20–25 µGy/h.
2. **SPE Events:** High-energy coronal mass ejection proton surges increasing absorbed dose rates up to 500–2,000 µGy/h.

### 1.2 Spacecraft Shielding Attenuation
Attenuation through aluminum equivalent structural shielding ($x = 10\text{ g/cm}^2$) follows exponential slab absorption:
$$D_{shielded} = D_{unshielded} \cdot \exp(-\mu_{Al} \cdot x)$$
where $\mu_{Al} \approx 0.035\text{ (g/cm}^2)^{-1}$.

### 1.3 Equivalent Dose Conversion
Biological equivalent dose rate $H$ (mSv/h) is calculated using radiation quality factors ($Q = 3.5$ for GCR ions, $Q = 2.0$ for SPE protons):
$$H\text{ (mSv/h)} = D_{shielded}\text{ (µGy/h)} \cdot Q \cdot 10^{-3}$$

## 2. NASA-STD-3001 Operational Guidelines
- **Acute Action Threshold:** Absorbed dose rate $> 500\text{ µGy/h}$ triggers immediate storm shelter ingress.
- **30-Day Exposure Limit:** 250 mSv to blood-forming organs.
- **1-Year Exposure Limit:** 500 mSv.

## 3. Strict Architectural Isolation ("RADIATION IS NOT ML")
A fundamental safety guarantee of TRUSTLINE:
- **Zero Radiation Features in ML:** Radiation parameters are strictly environmental metadata (`MISSION_CONTEXT`). They NEVER enter the 14-feature physiological ML feature vector (WESAD).
- **Independent Clinical Assessment:** The `SpaceAssessmentBridge` translates radiation packets directly into `NormalizedEvidenceItem` records in `EvidenceRegistry`.
- **Deterministic Rules in RuleRegistry:**
  - `RR-ENV-RADIATION-ACUTE`: Triggers when `radiation_dose_rate_microgy_h > 500.0`.
  - `RR-ENV-RADIATION-CUMULATIVE`: Triggers when `radiation_cumulative_dose_msv > 250.0`.
