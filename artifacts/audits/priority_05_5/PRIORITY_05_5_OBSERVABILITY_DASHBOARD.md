# PRIORITY 05.5 — OBSERVABILITY DASHBOARD ARCHITECTURE & USER GUIDE

## 1. Overview
The TRUSTLINE Observability Dashboard is implemented in `data-engineering/simulator/dashboard/dashboard_app.py` and exposed via `frontend/dashboard/simulator_dashboard.py`. Built with Dash and Plotly, it renders live physiological telemetry and environmental dosimetry.

## 2. Dashboard Layout
1. **Mission Scenario Control Panel (Left):**
   - Scenario selector: Scenarios A through F.
   - Fault injection controls: Flatline, baseline wander, powerline hum, clipping, packet drops.
   - Target sensor selector: ECG, PPG, EDA, Resp, Accel, etc.
2. **Real-time Waveform Display (Center):**
   - ECG Lead II oscilloscope (256 Hz).
   - PPG Plethysmogram & Respiration effort overlay (64 Hz / 32 Hz).
   - Electrodermal conductance trace (4 Hz).
3. **Sensor Quality Status (Top Right):**
   - Signal quality indicators: VALID (SNR 24dB), DEGRADED, INVALID / FLATLINE.
4. **Space Environment Dosimetry Panel (Bottom Right — STRICTLY SEPARATE):**
   - Ambient dose rate gauge (µGy/h).
   - Equivalent biological dose rate (mSv/h).
   - Cumulative mission exposure (mSv).
   - Solar Particle Event (SPE) alert state (NOMINAL, ADVISORY, WARNING, ALARM).
   - Spacecraft aluminum shielding thickness ($10\text{ g/cm}^2$).

## 3. Launch Instructions
```bash
PYTHONPATH=.:ai-agents:ai-engine/agents:ai-engine:data-engineering python3 frontend/dashboard/simulator_dashboard.py
```
Access at `http://127.0.0.1:8050`.
