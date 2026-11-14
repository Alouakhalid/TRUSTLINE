# PRIORITY 05.5 — TRANSPORT AND SQA INGESTION SPECIFICATION

## 1. Transmission Architecture
The simulation environment operates as an external hardware emulation service transmitting across two primary interfaces:
1. **WebSocket Streaming (`/ws/telemetry`):** Low-latency binary/JSON streaming for real-time oscilloscope rendering and continuous SQA window buffering.
2. **REST API Fallback (`/api/telemetry/packet`):** Guaranteed HTTP fallback when WebSocket connectivity is unavailable or degraded.

## 2. Packet Framing Protocol
```json
{
  "packet_id": "PKT-ECG-A1B2C3D4",
  "sequence_number": 1024,
  "astronaut_id": "AST-001",
  "session_id": "SESSION-SIM-001",
  "timestamp_epoch_ms": 1700000000000,
  "sensor_type": "ECG",
  "sample_rate_hz": 256.0,
  "channels_data": [[0.12, 0.15, 0.18], [0.85, 1.20, 0.45], [0.73, 1.05, 0.27]],
  "checksum_crc32": 3928172635,
  "hardware_metadata": {"scenario": "SCENARIO_A_REST"}
}
```

## 3. SQA Ingestion Bridge (`ingestion_bridge.py`)
- Buffers multi-sensor packets into temporal windows.
- Writes raw `.npy` signal arrays to workspace cache (`data/cache/simulated_signals/`).
- Generates standard `AstronautHealthManifest` strictly conforming to `ai-engine/agents/sensor_quality/schemas/input_schema.py`.
- **Identity Enforcement:** If `astronaut_id` is empty or missing, sets `AST-UNKNOWN`. The LangGraph Supervisor's `input_validation_node` rejects unknown subjects, halting execution before agent dispatch.
