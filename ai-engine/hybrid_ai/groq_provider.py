"""
Groq Cloud AI Provider adapter with timeout enforcement, bounded retries, and secret masking.
"""
import os
import time
import json
import logging
from typing import Optional, Dict, Any
from groq import Groq, APIError, APITimeoutError, RateLimitError, AuthenticationError

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

class GroqProvider(BaseLLMProvider):
    """Client adapter for Groq Cloud API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 2
    ):
        raw_key = api_key or os.environ.get("GROQ_API_KEY", "")
        chat_model = model or os.environ.get("GROQ_CHAT_MODEL", "qwen/qwen3.8-27b")
        super().__init__(ProviderType.GROQ, default_model=chat_model, default_timeout=timeout)
        self.api_key = raw_key
        self.max_retries = max_retries
        self._client: Optional[Groq] = None
        if self.api_key:
            self._client = Groq(api_key=self.api_key, timeout=self.default_timeout)

    def is_configured(self) -> bool:
        """Verify whether valid credentials exist."""
        return bool(self.api_key and self._client is not None)

    def health_check(self) -> ProviderHealth:
        """Verify connectivity by listing models or executing ping."""
        t0 = time.perf_counter()
        if not self.is_configured():
            return ProviderHealth(
                provider=self.provider_type,
                status=ProviderStatus.UNAVAILABLE,
                error="GROQ_API_KEY not configured",
                details={"configured": False}
            )
        try:
            assert self._client is not None
            # Light ping check
            self._client.models.list()
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return ProviderHealth(
                provider=self.provider_type,
                status=ProviderStatus.HEALTHY,
                latency_ms=elapsed_ms,
                details={"model": self.default_model, "configured": True}
            )
        except AuthenticationError as e:
            return ProviderHealth(
                provider=self.provider_type,
                status=ProviderStatus.UNAVAILABLE,
                error="Authentication failure: Invalid API Key",
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                details={"auth_error": True}
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.provider_type,
                status=ProviderStatus.DEGRADED,
                error=str(exc),
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                details={"error_type": type(exc).__name__}
            )

    async def health_check_async(self) -> ProviderHealth:
        return self.health_check()

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Execute synchronous completion with bounded retries."""
        if not self.is_configured():
            raise ProviderUnavailableError("Groq Cloud provider is not configured (missing GROQ_API_KEY).")

        prompt_text = request.prompt
        if request.format_json and "json" not in (prompt_text.lower() + (request.system_prompt or "").lower()):
            prompt_text = f"{prompt_text}\n\nRespond with a valid JSON object."

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": prompt_text})

        timeout = request.timeout_seconds or self.default_timeout
        attempt = 0
        backoff = 0.5
        t_start = time.perf_counter()

        while attempt <= self.max_retries:
            attempt += 1
            try:
                assert self._client is not None
                kwargs: Dict[str, Any] = {
                    "model": self.default_model,
                    "messages": messages,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "timeout": timeout
                }
                if request.format_json:
                    kwargs["response_format"] = {"type": "json_object"}

                resp = self._client.chat.completions.create(**kwargs)
                raw_content = resp.choices[0].message.content or ""
                elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)

                structured = None
                if request.format_json:
                    try:
                        structured = json.loads(raw_content)
                    except Exception:
                        structured = None

                return ProviderResponse(
                    request_id=request.request_id,
                    provider=self.provider_type,
                    model=self.default_model,
                    content=raw_content.strip(),
                    structured_data=structured,
                    latency_ms=elapsed_ms,
                    is_fallback=False,
                    success=True,
                    metadata={"attempt": attempt}
                )

            except AuthenticationError as e:
                # Never retry authentication errors
                logger.error("Groq authentication failure. Failing without retry.")
                raise ProviderAuthenticationError(f"Groq authentication rejected: {str(e)}") from e
            except APITimeoutError as e:
                if attempt > self.max_retries:
                    raise ProviderTimeoutError(f"Groq request timed out after {self.max_retries} retries: {str(e)}") from e
                time.sleep(backoff)
                backoff *= 2.0
            except RateLimitError as e:
                if attempt > self.max_retries:
                    raise ProviderRateLimitError(f"Groq rate limit exceeded after {self.max_retries} retries: {str(e)}") from e
                time.sleep(backoff)
                backoff *= 2.0
            except APIError as e:
                if attempt > self.max_retries:
                    raise ProviderUnavailableError(f"Groq API error: {str(e)}") from e
                time.sleep(backoff)
                backoff *= 2.0
            except Exception as e:
                raise ProviderUnavailableError(f"Unexpected Groq client error: {str(e)}") from e

        raise ProviderUnavailableError("Groq request failed after bounded retries.")

    async def generate_async(self, request: ProviderRequest) -> ProviderResponse:
        return self.generate(request)
