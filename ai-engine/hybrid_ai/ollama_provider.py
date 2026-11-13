"""
Ollama Local AI Provider adapter interfacing with qwen2.5:7b-instruct on Apple Silicon.
"""
import os
import time
import json
import urllib.request
import urllib.error
import logging
from typing import Optional, Dict, Any

from .base_provider import BaseLLMProvider
from .schemas import (
    ProviderType,
    ProviderStatus,
    ProviderRequest,
    ProviderResponse,
    ProviderHealth,
    ProviderUnavailableError,
    ProviderTimeoutError
)

logger = logging.getLogger(__name__)

class OllamaProvider(BaseLLMProvider):
    """Client adapter for Ollama local inference on edge hardware."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 45.0
    ):
        endpoint = base_url or os.environ.get("LOCAL_AI_ENDPOINT", "http://127.0.0.1:11434")
        local_model = model or os.environ.get("LOCAL_AI_MODEL", "qwen2.5:7b-instruct")
        super().__init__(ProviderType.OLLAMA, default_model=local_model, default_timeout=timeout)
        self.base_url = endpoint.rstrip("/")

    def health_check(self) -> ProviderHealth:
        """Verify Ollama server status and model availability via /api/tags."""
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            models = [m.get("name") for m in data.get("models", [])]
            is_model_present = any(self.default_model in m for m in models)
            
            if not is_model_present:
                return ProviderHealth(
                    provider=self.provider_type,
                    status=ProviderStatus.DEGRADED,
                    latency_ms=elapsed_ms,
                    error=f"Model {self.default_model} not found in Ollama tags",
                    details={"available_models": models}
                )

            return ProviderHealth(
                provider=self.provider_type,
                status=ProviderStatus.HEALTHY,
                latency_ms=elapsed_ms,
                details={"model": self.default_model, "installed_models": len(models)}
            )
        except urllib.error.URLError as e:
            return ProviderHealth(
                provider=self.provider_type,
                status=ProviderStatus.UNAVAILABLE,
                error=f"Ollama server unreachable at {self.base_url}: {str(e)}",
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )
        except Exception as e:
            return ProviderHealth(
                provider=self.provider_type,
                status=ProviderStatus.UNAVAILABLE,
                error=str(e),
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )

    async def health_check_async(self) -> ProviderHealth:
        return self.health_check()

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Execute local inference using Ollama /api/generate."""
        timeout = request.timeout_seconds or self.default_timeout
        t0 = time.perf_counter()

        payload = {
            "model": self.default_model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_ctx": 4096,
                "num_thread": 4
            }
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        if request.format_json:
            payload["format"] = "json"

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                raise ProviderTimeoutError(f"Ollama local inference timed out after {timeout}s") from e
            raise ProviderUnavailableError(f"Ollama service unreachable at {self.base_url}: {str(e)}") from e
        except TimeoutError as e:
            raise ProviderTimeoutError(f"Ollama local inference timed out after {timeout}s") from e
        except Exception as e:
            raise ProviderUnavailableError(f"Ollama inference error: {str(e)}") from e

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        raw_text = data.get("response", "").strip()

        eval_dur_s = (data.get("eval_duration") or 0) / 1e9
        eval_cnt = data.get("eval_count") or 0
        tps = round(eval_cnt / eval_dur_s, 2) if eval_dur_s > 0 else None

        structured = None
        if request.format_json:
            try:
                structured = json.loads(raw_text)
            except Exception:
                structured = None

        return ProviderResponse(
            request_id=request.request_id,
            provider=self.provider_type,
            model=self.default_model,
            content=raw_text,
            structured_data=structured,
            latency_ms=elapsed_ms,
            tokens_per_second=tps,
            is_fallback=True,
            success=True,
            metadata={
                "load_duration_s": round((data.get("load_duration") or 0) / 1e9, 3),
                "prompt_eval_duration_s": round((data.get("prompt_eval_duration") or 0) / 1e9, 3),
                "eval_count": eval_cnt
            }
        )

    async def generate_async(self, request: ProviderRequest) -> ProviderResponse:
        return self.generate(request)
