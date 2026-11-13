"""
Hugging Face Inference API / Providers adapter for TRUSTLINE.
Provides hosted inference with pretrained RLHF-aligned language models.
"""
import os
import time
import json
import logging
from typing import Optional, Dict, Any, List

from .base_provider import BaseLLMProvider
from .schemas import (
    ProviderType,
    ProviderStatus,
    ProviderRequest,
    ProviderResponse,
    ProviderHealth,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError
)

logger = logging.getLogger(__name__)

class HuggingFaceProvider(BaseLLMProvider):
    """
    Hosted inference client adapter for Hugging Face Inference Providers.
    Connects to pretrained RLHF-aligned models (default: meta-llama/Llama-3.1-8B-Instruct).
    """

    DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 25.0,
        max_retries: int = 2
    ):
        raw_token = api_key or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY", "")
        chosen_model = model or os.environ.get("HF_MODEL_ID") or self.DEFAULT_MODEL
        super().__init__(ProviderType.HUGGINGFACE, default_model=chosen_model, default_timeout=timeout)
        self.api_key = raw_token.strip()
        self.provider = provider or os.environ.get("HF_INFERENCE_PROVIDER", "auto")
        self.base_url = base_url or os.environ.get("HF_ROUTER_BASE_URL", "https://router.huggingface.co/v1")
        self.max_retries = max_retries
        self.model_revision = os.environ.get("HF_MODEL_REVISION", "main")
        self._client: Optional[Any] = None

        if self.api_key:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize Hugging Face InferenceClient."""
        try:
            from huggingface_hub import InferenceClient
            self._client = InferenceClient(
                token=self.api_key,
                timeout=self.default_timeout
            )
        except Exception as e:
            logger.warning(f"Could not initialize native InferenceClient: {e}. Falling back to standard interface.")
            self._client = None

    def is_configured(self) -> bool:
        """Verify whether an API token is configured."""
        return bool(self.api_key)

    def health_check(self) -> ProviderHealth:
        """Verify endpoint connectivity and token validity."""
        t0 = time.perf_counter()
        if not self.is_configured():
            return ProviderHealth(
                provider=self.provider_type,
                status=ProviderStatus.UNAVAILABLE,
                error="HF_TOKEN not configured",
                details={"configured": False, "model": self.default_model}
            )

        try:
            # Probe model endpoint info
            if self._client is not None and hasattr(self._client, "get_endpoint_info"):
                self._client.get_endpoint_info(self.default_model)
            else:
                import urllib.request
                req = urllib.request.Request(
                    f"{self.base_url}/models",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "User-Agent": "TRUSTLINE-HFProvider-HealthCheck"
                    }
                )
                with urllib.request.urlopen(req, timeout=min(5.0, self.default_timeout)) as resp:
                    assert resp.status == 200

            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return ProviderHealth(
                provider=self.provider_type,
                status=ProviderStatus.HEALTHY,
                latency_ms=elapsed_ms,
                details={
                    "model": self.default_model,
                    "provider": self.provider,
                    "configured": True,
                    "revision": self.model_revision
                }
            )
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            err_msg = str(exc)
            status = ProviderStatus.DEGRADED
            if "401" in err_msg or "unauthorized" in err_msg.lower():
                status = ProviderStatus.UNAVAILABLE
                return ProviderHealth(
                    provider=self.provider_type,
                    status=status,
                    error="Authentication failure: Invalid or expired HF_TOKEN",
                    latency_ms=elapsed_ms,
                    details={"auth_error": True}
                )
            return ProviderHealth(
                provider=self.provider_type,
                status=status,
                error=err_msg,
                latency_ms=elapsed_ms,
                details={"error_type": type(exc).__name__}
            )

    async def health_check_async(self) -> ProviderHealth:
        """Asynchronous health check."""
        return self.health_check()

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """
        Execute synchronous chat completion with timeout enforcement and bounded retries.
        """
        if not self.is_configured():
            raise ProviderUnavailableError("Hugging Face provider is not configured (missing HF_TOKEN).")

        prompt_text = request.prompt
        if request.format_json and "json" not in (prompt_text.lower() + (request.system_prompt or "").lower()):
            prompt_text = f"{prompt_text}\n\nRespond strictly with a valid JSON object."

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": prompt_text})

        timeout_sec = request.timeout_seconds or self.default_timeout
        attempt = 0
        last_error = None

        while attempt <= self.max_retries:
            t_start = time.perf_counter()
            try:
                raw_content = ""
                completion_tokens = None
                prompt_tokens = None

                if self._client is not None and hasattr(self._client, "chat_completion"):
                    chat_kwargs: Dict[str, Any] = {
                        "messages": messages,
                        "model": self.default_model,
                        "max_tokens": request.max_tokens,
                        "temperature": request.temperature,
                    }
                    if request.format_json:
                        chat_kwargs["response_format"] = {"type": "json_object"}

                    hf_resp = self._client.chat_completion(**chat_kwargs)
                    if hasattr(hf_resp, "choices") and hf_resp.choices:
                        raw_content = hf_resp.choices[0].message.content or ""
                    elif isinstance(hf_resp, dict) and "choices" in hf_resp:
                        raw_content = hf_resp["choices"][0]["message"]["content"] or ""

                    if hasattr(hf_resp, "usage") and hf_resp.usage:
                        prompt_tokens = getattr(hf_resp.usage, "prompt_tokens", None)
                        completion_tokens = getattr(hf_resp.usage, "completion_tokens", None)
                    elif isinstance(hf_resp, dict) and "usage" in hf_resp:
                        prompt_tokens = hf_resp["usage"].get("prompt_tokens")
                        completion_tokens = hf_resp["usage"].get("completion_tokens")
                else:
                    # Fallback via OpenAI client pointing to HF router endpoint
                    from openai import OpenAI
                    oai = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=timeout_sec)
                    kwargs: Dict[str, Any] = {
                        "model": self.default_model,
                        "messages": messages,
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens,
                    }
                    if request.format_json:
                        kwargs["response_format"] = {"type": "json_object"}

                    completion = oai.chat.completions.create(**kwargs)
                    raw_content = completion.choices[0].message.content or ""
                    if completion.usage:
                        prompt_tokens = completion.usage.prompt_tokens
                        completion_tokens = completion.usage.completion_tokens

                elapsed_sec = time.perf_counter() - t_start
                latency_ms = round(elapsed_sec * 1000.0, 2)
                tps = None
                if completion_tokens and elapsed_sec > 0:
                    tps = round(completion_tokens / elapsed_sec, 2)
                elif raw_content and elapsed_sec > 0:
                    approx_tokens = len(raw_content.split()) * 1.33
                    tps = round(approx_tokens / elapsed_sec, 2)

                structured_json = None
                if request.format_json:
                    try:
                        structured_json = json.loads(raw_content)
                    except Exception:
                        pass

                return ProviderResponse(
                    request_id=request.request_id,
                    provider=self.provider_type,
                    model=self.default_model,
                    content=raw_content,
                    structured_data=structured_json,
                    latency_ms=latency_ms,
                    tokens_per_second=tps,
                    is_fallback=False,
                    success=True,
                    metadata={
                        "inference_provider": self.provider,
                        "model_revision": self.model_revision,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens
                    }
                )

            except Exception as exc:
                err_str = str(exc).lower()
                status_code = getattr(exc, "status_code", None) or getattr(exc, "response", None) and getattr(exc.response, "status_code", None)

                # Classify error
                if status_code == 401 or "401" in err_str or "unauthorized" in err_str:
                    raise ProviderAuthenticationError(f"Hugging Face API Authentication failed: {exc}") from exc

                if status_code == 429 or "429" in err_str or "rate limit" in err_str:
                    logger.warning(f"HF rate limit (attempt {attempt + 1}/{self.max_retries + 1}): {exc}")
                    if attempt < self.max_retries:
                        time.sleep(1.0 * (2 ** attempt))
                        attempt += 1
                        continue
                    raise ProviderRateLimitError(f"Hugging Face rate limit exceeded: {exc}") from exc

                if "timeout" in err_str or "timed out" in err_str:
                    logger.warning(f"HF timeout (attempt {attempt + 1}/{self.max_retries + 1}): {exc}")
                    if attempt < self.max_retries:
                        time.sleep(0.5 * (2 ** attempt))
                        attempt += 1
                        continue
                    raise ProviderTimeoutError(f"Hugging Face inference timed out after {timeout_sec}s: {exc}") from exc

                logger.warning(f"HF API error (attempt {attempt + 1}/{self.max_retries + 1}): {exc}")
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** attempt))
                    attempt += 1
                    continue
                break

        raise ProviderUnavailableError(f"Hugging Face provider error: {last_error}") from last_error

    async def generate_async(self, request: ProviderRequest) -> ProviderResponse:
        """Asynchronous generation fallback."""
        return self.generate(request)
