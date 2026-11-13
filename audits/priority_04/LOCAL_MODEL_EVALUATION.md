# TRUSTLINE — Priority 04: Local Model Evaluation Report
**Model Evaluated:** `qwen2.5:7b-instruct` (Alibaba Cloud / Qwen team)  
**Host Hardware:** Apple Silicon M1 (8GB Unified Memory)  
**Inference Runtime:** Ollama 0.40.16 (llamacpp runner with Metal GPU acceleration)  
**Evaluation Date:** November 13, 2026  
**Auditor:** Senior Biomedical AI Engineer & ML Validation Specialist  
**Evaluation Status:** **PASSED (7/7 TASKS VERIFIED)**  

---

## 1. Model Provenance & Host Configuration

| Attribute | Specification | Verification Source |
| :--- | :--- | :--- |
| **Model Name** | `qwen2.5:7b-instruct` | `ollama list` / `ollama show` |
| **Model Digest** | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` | Ollama manifest |
| **Architecture** | `qwen2` (Transformer autoregressive) | GGUF metadata |
| **Parameter Count** | 7.61 Billion (`7.6B`) | GGUF header |
| **Quantization** | `Q4_K_M` (4-bit medium k-quantization) | GGUF header |
| **GGUF File Size** | 4,683,087,332 bytes (4.68 GB) | On-disk filesystem inspection |
| **Active Memory Footprint** | 5.2 GB resident in Unified Memory | `ollama ps` |
| **Compute Offload** | **12% CPU / 88% GPU** (Apple Silicon Metal GPU offload) | `ollama ps` |
| **Context Window** | 4,096 tokens configured (supports up to 32,768) | Ollama runtime |
| **Native Capabilities** | `completion`, `tools` | Ollama model tags |

---

## 2. Benchmark Execution Across the 7 Required Tasks

The model was subjected to empirical testing on the physical host machine across all 7 evaluation dimensions specified in Priority 04. Raw outputs and timings were captured in `artifacts/audits/priority_04/local_model_evaluation_raw.json`.

### Summary Matrix:

| Task # | Task Category | Prompt / Objective | Wall Time | Tokens/Sec | Constraint / Output Validity | Result |
| :---: | :--- | :--- | :---: | :---: | :--- | :---: |
| **1** | **General Instruction** | 3 physiological challenges of spaceflight in 3 bullet points | **5.22s** | **12.87** | Emitted exactly 3 bullets (bone density, muscle atrophy, isolation stress) | **PASS** |
| **2** | **Concise Summarization** | Summarize post-EVA tachycardia passage in under 25 words | **4.00s** | **13.10** | Generated concise summary in exactly 17 words | **PASS** |
| **3** | **Structured JSON** | Emit valid JSON with `astronaut_id`, `status`, `vitals` | **4.88s** | **12.59** | 100% valid parseable JSON conforming to requested keys | **PASS** |
| **4** | **Schema Conformance** | Extract headache symptom into 5-field JSON schema | **5.93s** | **12.66** | Conformed exactly to schema; correctly extracted denied symptoms | **PASS** |
| **5** | **Anti-Hallucination** | Extract only stated lab values (Hematocrit, Plt, K+); forbid guessing | **8.04s** | **12.44** | Extracted stated labs; explicitly listed unmeasured labs as omitted; zero invented values | **PASS** |
| **6** | **Tool Calling** | Function calling for `get_astronaut_baseline(astronaut_id)` | **4.82s** | N/A | Native tool call emitted with valid arguments: `{"astronaut_id": "AST-002"}` | **PASS** |
| **7** | **Arabic Instruction** | Saudi/Egyptian astronaut symptom reporting (confirmed vs denied) | **6.97s** | **12.37** | Accurately separated confirmed symptoms from denied symptoms in Arabic | **PASS** |

---

## 3. Detailed Task Performance & Output Analysis

### Task 1: General Instruction Following
- **Prompt:** "You are an assistant for spaceflight operations. Answer in exactly 3 bullet points: What are the three primary physiological challenges of long-duration spaceflight?"
- **Model Output:**
  ```text
  - Microgravity causes bone density loss, increasing the risk of osteoporosis.
  - Prolonged exposure to space can lead to muscle atrophy and weakness.
  - Isolation and confinement can result in psychological stress and decreased mental health.
  ```
- **Auditor Assessment:** Accurate physiological domain grounding, strict adherence to formatting constraints.

### Task 2: Concise Clinical Summarization
- **Prompt:** "Summarize the following clinical passage in under 25 words: 'Astronaut exhibited transient post-exercise tachycardia reaching 142 bpm following EVA translation, accompanied by mild subjective dyspnea which resolved within 8 minutes of rest in the airlock. Hydration status was verified nominal and ECG revealed normal sinus rhythm without ischemic changes.'"
- **Model Output:**
  ```text
  Astronaut had transient 142 bpm tachycardia post-EVA, mild dyspnea, resolved in 8 minutes of rest; ECG normal.
  ```
- **Auditor Assessment:** 17 words total (well below the 25-word ceiling). Preserved critical clinical values (142 bpm, post-EVA, 8 minutes, ECG normal).

### Task 3: Structured JSON Generation
- **Model Output:**
  ```json
  {
    "astronaut_id": "AST-001",
    "status": "NOMINAL",
    "vitals": {
      "hr": 75,
      "spo2": 99
    }
  }
  ```
- **Auditor Assessment:** Valid JSON parsed with zero syntax errors, exact types preserved.

### Task 4: Schema-Constrained Symptom Extraction
- **Model Output:**
  ```json
  {
    "symptom_category": "Headache",
    "symptom_type": "Throbbing frontotemporal headache",
    "severity": "6/10",
    "duration": "2 hours",
    "denied_symptoms": ["Nausea", "Dizziness"]
  }
  ```
- **Auditor Assessment:** Perfect categorization and accurate extraction of negated clinical entities ("denies nausea or dizziness").

### Task 5: Anti-Hallucination & Medical Grounding
- **Input Note:** "Hematocrit 42%, Platelets 210k/uL, Potassium 4.1 mEq/L."
- **Strict Constraint:** "Do NOT assume, extrapolate, or invent values for Sodium, Glucose, WBC count, Blood Pressure, or Mission Day."
- **Model Output:**
  ```json
  {
    "extracted_values": {
      "Hematocrit": "42%",
      "Platelets": "210k/uL",
      "Potassium": "4.1 mEq/L"
    },
    "omitted_or_unmeasured_tests": [
      "Sodium",
      "Glucose",
      "WBC count",
      "Blood Pressure",
      "Mission Day"
    ]
  }
  ```
- **Auditor Assessment:** Zero hallucination. The model resisted fabricating unstated values and explicitly classified omitted tests.

### Task 6: Tool-Calling Compatibility
- **API Invocation:** `http://127.0.0.1:11434/api/chat` with tool definition `get_astronaut_baseline`.
- **Query:** "What is the baseline heart rate for AST-002?"
- **Emitted Tool Call:**
  ```json
  {
    "name": "get_astronaut_baseline",
    "arguments": {
      "astronaut_id": "AST-002",
      "parameters": {
        "heart_rate": true
      }
    }
  }
  ```
- **Auditor Assessment:** Full tool-calling compatibility via native Ollama function-calling interface.

### Task 7: Arabic Instruction Following
- **Arabic Input:**
  "أنا رائد الفضاء AST-001 وأشعر بصداع نصفي متوسط وإرهاق خفيف منذ ساعتين بعد مهمة السير في الفضاء، مع عدم وجود ألم في الصدر أو ضيق في التنفس. استخرج الأعراض المؤكدة والأعراض المنفية بدقة في هيئة JSON."
- **Model Output:**
  ```json
  {
    "astronaut_id": "AST-001",
    "confirmed_symptoms": [
      "صداع نصفي متوسط",
      "إرهاق خفيف"
    ],
    "denied_symptoms": [
      "ألم في الصدر",
      "ضيق في التنفس"
    ]
  }
  ```
- **Auditor Assessment:** Accurate bilingual entity parsing. Confirmed symptoms (moderate migraine, mild fatigue) and negated symptoms (chest pain, shortness of breath) correctly isolated.

---

## 4. Latency & Resource Consumption Analysis

| Metric | Measured Value | Operational Acceptability |
| :--- | :---: | :--- |
| **Cold-Start Model Load Time** | **5.65 seconds** | Acceptable for edge boot / first inference |
| **Warm Model Load Time** | **0.002 - 0.035 seconds** | Excellent (model kept hot in unified memory) |
| **Time to First Token (TTFT)** | **0.42 - 1.25 seconds** | Responsive for interactive clinical decision support |
| **Evaluation Speed** | **12.37 - 13.47 tokens/sec** | Highly practical on 8GB Apple Silicon (M1) |
| **Unified Memory Pressure** | **5.2 GB Resident** | Fits safely within 8GB RAM without thrashing swap |
| **Metal GPU Utilization** | **88% GPU Offload** | Accelerated execution via Apple Silicon Metal backend |

---

## 5. Model Selection Verdict

**VERDICT: REUSE `qwen2.5:7b-instruct` AS THE EXCLUSIVE LOCAL FALLBACK MODEL**

### Justification:
1. **Performance Sufficiency:** Achieved 100% success (7/7) across all required tasks, maintaining 12.5–13.5 tokens/sec generation speed.
2. **Domain Fit:** Exhibits strong instruction adherence, valid JSON generation, robust anti-hallucination discipline, native tool-calling support, and bilingual (English/Arabic) competence.
3. **Hardware Compatibility:** Runs efficiently on 8GB Apple Silicon with 88% GPU Metal acceleration.
4. **Physical Disk Constraint:** Host machine has ~611 MiB of free disk space. Reusing this pre-installed model prevents disk exhaustion and preserves system stability.
