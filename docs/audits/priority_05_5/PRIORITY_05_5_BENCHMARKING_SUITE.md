# PRIORITY 05.5 — LOCAL VS CLOUD AI BENCHMARKING SUITE

## 1. Methodology & Evaluation Framework
The benchmarking suite in `data-engineering/simulator/benchmarks/` provides reproducible comparative evaluation between local on-device inference and cloud AI providers:
- **ML Models:** Random Forest, HistGradientBoosting, Isolation Forest.
- **Datasets:** Real WESAD dataset (694 windows, 14 selected features) vs Synthetic Simulator dataset (694 windows matching WESAD schema).
- **LLM Models:** Local Ollama (`qwen2.5:7b-instruct`, `llama3:latest`) vs Cloud Groq / Hugging Face via `HybridAIRouter`.

## 2. Standardized Metrics
- **Latency (ms/window or sec/prompt):** Mean, median, p95, min, max.
- **Throughput:** Windows/sec (ML) and Tokens/sec (LLM).
- **Memory Footprint (MB):** Peak RAM delta measured via `psutil`.
- **Classification Performance:** Accuracy, macro F1, weighted F1, precision, recall.
- **Safety Adherence:** Detection of prohibited clinical prescriptions or ungrounded diagnoses.
- **Radiation Isolation:** Verification that radiation features are strictly excluded from ML inputs.
