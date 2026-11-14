# TRUSTLINE — Known Limitations & Operational Realities

## 1. Hardware & Edge Compute Realities

1. **Unified Memory Constraints (8GB)**:
   - On edge nodes with 8GB unified memory, loading full-precision 70B+ parameter language models locally is impossible.
   - TRUSTLINE employs an intelligent Hybrid AI Router: when cloud connectivity is severed, the system routes to optimized 4-bit quantized local models or structured rule-based clinical expert engines.

2. **Optical Sensor Motion Artifacts**:
   - Photoplethysmography (PPG) and Bioimpedance (EDA) signals are sensitive to astronaut movement during vigorous exercise or Extravehicular Activity (EVA).
   - The Sensor Quality Agent (SQA) flags artifact segments with reduced confidence scores, preventing downstream false-positive alarms.

---

## 2. Communication Latency Realities

1. **Deep-Space One-Way Light Time**:
   - Earth-to-Mars communication delays range from 4 to 22 minutes each way.
   - Synchronous cloud API calls during medical emergencies are strictly prohibited.
   - The system is architected to guarantee immediate local clinical triage, buffering reports in the sync outbox for transmission when passes occur.

2. **Radiation Environmental Invariant**:
   - Ionizing cosmic radiation causes biological damage over days and years, but does not cause millisecond fluctuations in cardiac rhythm.
   - Radiation dosimetry is strictly retained as environmental context and is never fed as an input feature to acute physiological ML classifiers.
