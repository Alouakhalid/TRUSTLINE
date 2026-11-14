# TRUSTLINE — Mission Operations User Guide

## 1. Astronaut Persona Guide

### 1.1 Logging In
1. Navigate to `http://localhost:8000/`.
2. Select your persona or register an astronaut account (e.g. `astro_alex`, Astronaut ID `AST-001`).
3. Enter your password and log in.

### 1.2 Monitoring Your Physiological Telemetry
- **3D Digital Twin**: Observe the 3D anatomical twin. Pulsing green hotspots indicate nominal sensor contact. Clicking any beacon (e.g. Lead II ECG on the chest or SpO2 on the left hand) reveals live sensor metrics.
- **60fps Oscilloscope**: Watch real-time waveforms for cardiac rhythm, arterial pulse, and respiration.
- **Radiation HUD**: Review cumulative cosmic and solar particle radiation exposure against NASA-STD-3001 mission limits.

### 1.3 Consulting the AI Medical Companion
1. Click the **AI Companion** tab.
2. Select an existing conversation or click **+ New Chat**.
3. Type your question or symptom report (e.g., *"Experiencing mild headache and eye strain after treadmill exercise"*).
4. The system analyzes your real-time telemetry, medical history, and clinical guidelines to deliver an actionable response with clickable evidence citations.

---

## 2. Flight Surgeon / Medical Officer Guide

### 2.1 Crew Health Overview
- Log in with your `MEDICAL_OFFICER` credentials.
- The **Crew Vitals Matrix** displays real-time health indexes, heart rates, oxygenation, and SQA signal quality scores across all assigned crew members.

### 2.2 Medical Document Ingestion & Verification
1. Access the **Medical Documents** tab.
2. Upload crew laboratory reports (PDF or DOCX).
3. Click **Process Document** to trigger native text extraction and OCR parsing.
4. Review extracted laboratory panels under **Pending Review**.
5. Click **Verify & Confirm** to certify findings into the crew member's permanent long-term medical memory.

---

## 3. Mission Administrator Guide

### 3.1 Connectivity Diagnostics
- Access the **Diagnostics** panel to monitor all 8 system probes: SQLite Database, DNS Resolution, Flight Network, Local AI Runtime, Cloud AI, Deep Space Ground Link, Outbox Sync Queue, and WebSocket Broadcaster.

### 3.2 Offline Sync Management
- Monitor pending, synced, and dead-letter queue records.
- Click **Trigger Sync Worker** to execute an immediate transmission pass to Mission Control.

### 3.3 Sensor Simulator & Demo Mode
- Toggle **Demo Mode** to test extreme physiological scenarios (hypoxia, cardiac arrhythmia, heat stroke, decompression illness) with 100% data isolation from real flight data.
