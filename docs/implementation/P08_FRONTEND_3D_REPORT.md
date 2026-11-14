# TRUSTLINE P08 — Frontend Architecture & 3D Digital Twin Report

## 1. Executive Summary

TRUSTLINE P08 delivers an Awwwards-grade, local-first single page application (SPA) built for long-duration space mission monitoring. It features an interactive 3D Digital Twin with Three.js WebGL rendering, 8 anatomically verified physiological sensor hotspots, a 60fps real-time oscilloscope, and three distinct role portals for Astronauts, Flight Surgeons, and Mission Administrators.

The entire frontend is self-contained in `frontend/public/`, requires zero external build dependencies, and is directly mounted and served by the FastAPI backend at `/`.

---

## 2. Design System & Tokens (`css/tokens.css`)

The UI follows the modern aerospace dark aesthetic specified in the `frontend-atlas` and `ui-ux-pro-max` agent skills:
- **Surface Palette**: Deep space navy (`#080b12`), titanium slate panels (`#0f172a`), border framing (`#1e293b`).
- **Telemetry Accents**: Cyan (`#06b6d4`), Emerald nominal (`#10b981`), Amber warning (`#f59e0b`), Rose alert (`#f43f5e`), Electric violet (`#8b5cf6`).
- **Typography**: Clean monospace and geometric sans-serif stack (`system-ui`, `SF Mono`, `JetBrains Mono`).
- **Micro-interactions**: High-DPI hardware-accelerated CSS transitions, glowing beacons, and subdued CRT scanlines.

---

## 3. 3D Digital Twin (`js/twin3d.js`)

```
             [3D Digital Twin Anatomical Hotspots]
                           ( Head )
                              ||
         (ECG Lead II) o---[ Thorax ]---o (Respiration Belt)
                              ||
        (Skin Temp L) o---[  Trunk  ]---o (PPG Right Wrist)
                              ||
         (SpO2 Finger) o---[  Palms  ]---o (EDA Constant V)
                              ||
                          [ Legs/Feet ]
                              ||
                 [ Backpack: IMU Accel+Gyro ]
```

### 3.1 Three.js Scene Configuration
- **Rendering Engine**: Three.js WebGLRenderer with antialiasing and high pixel ratio scaling.
- **Controls**: `OrbitControls` with smooth damping, restricted polar angles (preventing disorienting underground flips), and distance clamping.
- **Lighting**: Cinematic 3-point space lighting (directional key light, subtle rim light, soft ambient fill).

### 3.2 Sensor Hotspots & Anatomical Coordinates
Hotspots are raycasted 3D interactive mesh beacons placed at anatomically authentic sites:
1. **ECG Lead II**: Left sternal border / anterior chest (`x: -0.06, y: 0.48, z: 0.23`).
2. **Respiration Belt**: Lower thoracic / diaphragmatic excursion zone (`x: 0.00, y: 0.28, z: 0.22`).
3. **Core Body Temperature**: Deep-body heat flux visceral trunk (`x: 0.00, y: 0.14, z: 0.19`).
4. **Skin Temperature**: Left inner wrist thermistor site (`x: -0.43, y: 0.02, z: 0.06`).
5. **PPG (Photoplethysmogram)**: Right wrist radial artery optical sensor (`x: 0.43, y: 0.02, z: 0.06`).
6. **SpO2 (Pulse Oximeter)**: Left index finger distal phalanx clip (`x: -0.47, y: -0.10, z: 0.07`).
7. **EDA (Electrodermal Activity)**: Right hand hypothenar palmar electrodes (`x: 0.47, y: -0.10, z: 0.07`).
8. **IMU (Biomechanical Kinematics)**: Dorsal upper thoracic spine backpack (`x: 0.00, y: 0.45, z: -0.28`).

### 3.3 Dynamic Quality Beacons
Hotspots pulse using sinusoidal emissive shaders reflecting Sensor Quality Agent (SQA) states:
- **Green (Nominal)**: Quality score > 0.85, SNR > 20dB.
- **Amber (Degraded)**: Quality score 0.50 - 0.85, minor baseline wander or motion noise.
- **Red (Critical / Artifact)**: Quality score < 0.50, electrode lead detachment, clipping, or flatline.

### 3.4 Strict Radiation Isolation Invariant
Space radiation dosimetry is **strictly barred** from the 3D anatomical twin. Radiation is environmental dosimetry measured by station sensors and is displayed exclusively in a dedicated **Space Environmental Radiation HUD** outside the human mesh.

### 3.5 2D Anatomical SVG Fallback
For low-power auxiliary displays or environments where WebGL is unavailable, the application provides an instant 2D anatomical silhouette fallback with interactive pulsing SVG beacons and live tooltip telemetry.

---

## 4. Real-Time Oscilloscope (`js/oscilloscope.js`)

- **Canvas Rendering**: 60fps hardware-accelerated 2D canvas sweeping beam.
- **Channels**: Lead II ECG, PPG arterial pulse, and thoracic respiration.
- **Visuals**: Phosphor persistence glow, grid reticle, sweep bar, and automatic voltage normalization.

---

## 5. Three Distinct Role Portals

1. **Astronaut Portal (`js/astronaut_portal.js`)**:
   - Vitals HUD with live heart rate, SpO2, core temp, and respiratory rate.
   - 3D Digital Twin with clickable sensor beacons.
   - EVA Pre-Breathing & Suit Preparation Readiness Assistant.
   - AI Medical Companion chat with session persistence and citation drawer.

2. **Flight Surgeon / Medical Officer Portal (`js/medical_portal.js`)**:
   - Station crew roster overview with real-time status badges.
   - Physiological telemetry deep-dive history and anomaly flags.
   - Clinical documents review queue (`/documents/confirm`) for lab reports and medical imagery.
   - Long-term memory governance: adding confirmed diagnoses and medication records.

3. **Administrator Portal (`js/admin_portal.js`)**:
   - 8-monitor connectivity diagnostics matrix (DNS, network, DB, AI runtimes, Ground link).
   - Sync outbox queue inspector with manual batch synchronization trigger.
   - Auditable state transition log.
   - Sensor simulator control panel with synthetic anomaly injection and Demo Mode toggle.
