"""Local vs Cloud LLM Benchmarking: Compares Ollama (Local) vs Groq/HF (Cloud) via HybridAIRouter."""
import time
import os
import psutil
import gc
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    from hybrid_ai.router import HybridAIRouter
    from hybrid_ai.schemas import ProviderRequest, TaskCategory, ProviderResponse
except ImportError:
    from agents.hybrid_ai.router import HybridAIRouter
    from agents.hybrid_ai.schemas import ProviderRequest, TaskCategory, ProviderResponse


class LLMBenchmarkRunner:
    """Rigorous evaluation comparing local Ollama models vs cloud API providers on Apple Silicon Mac."""

    def __init__(
        self,
        router: Optional[HybridAIRouter] = None,
        ollama_models: Optional[List[str]] = None
    ):
        self.router = router or HybridAIRouter()
        self.ollama_models = ollama_models or ["qwen2.5:7b-instruct", "llama3:latest"]

        # Standardized benchmark prompts covering the 4 agent capabilities
        self.benchmark_prompts = {
            "sensor_quality_briefing": {
                "category": TaskCategory.SENSOR_QUALITY_BRIEFING,
                "prompt": (
                    "Generate a clinical sensor quality briefing for flight surgeons. "
                    "Sensor status: ECG Lead II reports valid signal with SNR 24dB; "
                    "EDA shows nominal tonic level 3.2 µS; Respiration belt shows periodic chest motion. "
                    "Summarize observational reliability."
                )
            },
            "personal_health_synthesis": {
                "category": TaskCategory.PERSONAL_HEALTH_SYNTHESIS,
                "prompt": (
                    "Synthesize astronaut physiological response during 45-minute cycle ergometry. "
                    "Heart rate mean: 142 bpm, Respiration rate: 26 bpm, Skin temp: 35.8 °C. "
                    "Evaluate against baseline cardiovascular adaptation. Cite NASA-STD-3001 guidelines."
                )
            },
            "risk_assessment_explanation": {
                "category": TaskCategory.RISK_ASSESSMENT_SYNTHESIS,
                "prompt": (
                    "Explain deterministic rule evaluation for rule RR-CARDIO-TACHYCARDIA. "
                    "Observed heart rate: 145 bpm exceeding 100 bpm threshold. "
                    "State observational evidence and flight surgeon escalation rationale."
                )
            },
            "medical_rag_synthesis": {
                "category": TaskCategory.MEDICAL_RAG_SYNTHESIS,
                "prompt": (
                    "Retrieve and explain NASA-STD-3001 space radiation career and acute 30-day limits. "
                    "Explain SPE proton storm shelter operational procedures."
                )
            }
        }

    def benchmark_task(
        self,
        task_name: str,
        category: TaskCategory,
        prompt: str,
        mode: str = "HYBRID"
    ) -> Dict[str, Any]:
        """Profile a single LLM request through the HybridAIRouter."""
        proc = psutil.Process(os.getpid())
        gc.collect()
        mem_before_mb = proc.memory_info().rss / (1024.0 * 1024.0)

        original_mode = self.router.mode
        self.router.mode = mode.upper()

        req = ProviderRequest(
            task_category=category,
            prompt=prompt,
            max_tokens=256,
            temperature=0.1
        )

        t0 = time.perf_counter()
        try:
            resp: ProviderResponse = self.router.route_request(req)
            t1 = time.perf_counter()
            duration_sec = t1 - t0
            success = resp.success
            content = resp.content
            provider = resp.provider.value if hasattr(resp.provider, "value") else str(resp.provider)
            tok_per_sec = resp.tokens_per_second or (len(content.split()) / max(0.001, duration_sec))
            error_msg = resp.error_message or ""
        except Exception as e:
            t1 = time.perf_counter()
            duration_sec = t1 - t0
            success = False
            content = ""
            provider = "ERROR"
            tok_per_sec = 0.0
            error_msg = str(e)
        finally:
            self.router.mode = original_mode

        mem_after_mb = proc.memory_info().rss / (1024.0 * 1024.0)
        mem_delta_mb = max(0.0, mem_after_mb - mem_before_mb)

        # Safety policy validation
        prohibited_phrases = ["take 500mg", "prescribe", "inject", "diagnosis confirmed: you have"]
        has_prescription_violation = any(p in content.lower() for p in prohibited_phrases)

        return {
            "task_name": task_name,
            "category": category.value,
            "provider_used": provider,
            "success": success,
            "latency_seconds": round(duration_sec, 3),
            "tokens_per_second": round(tok_per_sec, 2),
            "memory_delta_mb": round(mem_delta_mb, 2),
            "safety_compliant": not has_prescription_violation,
            "error": error_msg
        }

    def run_full_llm_benchmark(self) -> Dict[str, Any]:
        """Execute benchmark across all agent capabilities for Local and Cloud configurations."""
        results: Dict[str, Any] = {
            "benchmark_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "system_hardware": {
                "cpu_count": psutil.cpu_count(logical=True),
                "total_ram_gb": round(psutil.virtual_memory().total / (1024.0 ** 3), 2),
                "available_ram_gb": round(psutil.virtual_memory().available / (1024.0 ** 3), 2)
            },
            "evaluations": {}
        }

        for task_key, task_info in self.benchmark_prompts.items():
            cat = task_info["category"]
            prompt = task_info["prompt"]

            # 1. Local execution
            local_res = self.benchmark_task(
                task_name=f"{task_key}_local",
                category=cat,
                prompt=prompt,
                mode="LOCAL_ONLY"
            )

            # 2. Hybrid / Cloud execution
            hybrid_res = self.benchmark_task(
                task_name=f"{task_key}_hybrid",
                category=cat,
                prompt=prompt,
                mode="HYBRID"
            )

            results["evaluations"][task_key] = {
                "local_ollama": local_res,
                "hybrid_cloud": hybrid_res
            }

        return results
