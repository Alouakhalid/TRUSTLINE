"""Unified benchmark orchestrator with sequential execution and memory profiling."""
import json
import os
import gc
import psutil
from pathlib import Path
from typing import Dict, Any

from .ml_benchmark import MLBenchmarkRunner
from .llm_benchmark import LLMBenchmarkRunner


def run_all_benchmarks(
    output_dir: str = "artifacts/audits/priority_05_5"
) -> Dict[str, Any]:
    """Execute complete ML and LLM benchmarks sequentially within Apple Silicon memory budget."""
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    proc = psutil.Process(os.getpid())
    gc.collect()
    start_ram_mb = proc.memory_info().rss / (1024.0 * 1024.0)

    print("--- [1/2] Executing Physiological ML Benchmark ---")
    ml_runner = MLBenchmarkRunner()
    ml_results = ml_runner.run_full_ml_benchmark()
    gc.collect()

    print("--- [2/2] Executing Local vs Cloud LLM Benchmark ---")
    llm_runner = LLMBenchmarkRunner()
    llm_results = llm_runner.run_full_llm_benchmark()
    gc.collect()

    end_ram_mb = proc.memory_info().rss / (1024.0 * 1024.0)

    combined_summary: Dict[str, Any] = {
        "benchmark_suite": "TRUSTLINE_P05_5_BENCHMARK",
        "system_telemetry": {
            "initial_ram_mb": round(start_ram_mb, 2),
            "final_ram_mb": round(end_ram_mb, 2),
            "net_ram_delta_mb": round(max(0.0, end_ram_mb - start_ram_mb), 2),
            "cpu_logical_cores": psutil.cpu_count(logical=True)
        },
        "ml_benchmark": ml_results,
        "llm_benchmark": llm_results
    }

    result_file = out_path / "benchmark_results.json"
    with open(result_file, "w") as f:
        json.dump(combined_summary, f, indent=2)

    print(f"Benchmark results successfully saved to {result_file}")
    return combined_summary


if __name__ == "__main__":
    run_all_benchmarks()
