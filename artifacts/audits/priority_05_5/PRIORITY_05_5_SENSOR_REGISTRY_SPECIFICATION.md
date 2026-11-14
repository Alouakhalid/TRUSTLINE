# PRIORITY 05.5 — SENSOR REGISTRY SPECIFICATION

## 1. Overview
The `SensorRegistry` in `data-engineering/simulator/registry.py` provides the canonical specification for 9 clinical and biomechanical sensor channels simulating external astronaut monitoring hardware, aligned with NASA-STD-3001 Volume 1 & 2 standards.

## 2. Sensor Channel Inventory
| Sensor Type | Display Name | Unit | Sample Rate (Hz) | Nominal Range | Channels | ADC Bits | Noise Floor Std |
|---|---|---|---|---|---|---|---|
| `ECG` | Electrocardiogram (3-Lead) | mV | 256.0 | [-3.0, 3.0] | 3 (I, II, III) | 16 | 0.015 mV |
| `PPG` | Photoplethysmogram | norm | 64.0 | [0.0, 1.0] | 1 | 16 | 0.005 |
| `HR` | Instantaneous Heart Rate | bpm | 1.0 | [30.0, 220.0] | 1 | 12 | 0.10 bpm |
| `SPO2` | Peripheral Oxygen Saturation | % | 1.0 | [70.0, 100.0] | 1 | 12 | 0.20 % |
| `SKIN_TEMP` | Skin Surface Temperature | °C | 4.0 | [25.0, 42.0] | 1 | 14 | 0.02 °C |
| `CORE_TEMP` | Core Body Temperature | °C | 1.0 | [34.0, 42.0] | 1 | 16 | 0.01 °C |
| `EDA` | Electrodermal Activity (GSR) | µS | 4.0 | [0.05, 40.0] | 1 | 16 | 0.01 µS |
| `RESPIRATION`| Respiratory Effort Waveform | a.u. | 32.0 | [-5.0, 5.0] | 1 | 16 | 0.02 |
| `ACCELEROMETER`| 3-Axis Linear Accelerometer | g | 32.0 | [-16.0, 16.0] | 3 (X, Y, Z) | 16 | 0.005 g |
| `GYROSCOPE` | 3-Axis Angular Gyroscope | deg/s | 32.0 | [-2000.0, 2000.0] | 3 (X, Y, Z) | 16 | 0.05 deg/s |

## 3. Data Integrity & Verification
Each transmitted frame encapsulates:
- 32-bit sequence counter.
- Millisecond epoch timestamp.
- Multichannel floating-point payload.
- Deterministic CRC32 checksum for corruption detection.
