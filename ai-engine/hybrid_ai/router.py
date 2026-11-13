"""
Central Hybrid AI Router coordinating cloud dispatch, circuit breaking, local fallback, and safety.
"""
import os
import time
import logging
from typing import Optional, Dict, Any

from .schemas import (
    ProviderType,
    ProviderRequest,
    ProviderResponse,
    TaskCategory,
    RoutingPolicy,
    CircuitState,
    TaskNotEligibleError,
    ProviderUnavailableError
)
from .groq_provider import GroqProvider
from .ollama_provider import OllamaProvider
from .huggingface_provider import HuggingFaceProvider
from .circuit_breaker import CircuitBreaker
from .capability_registry import CapabilityRegistry
from .telemetry import RouterTelemetry, RouterTelemetryRecord

logger = logging.getLogger(__name__)

class HybridAIRouter:
    """Central provider-routing and fallback engine for TRUSTLINE."""

    def __init__(
        self,
        groq_provider: Optional[GroqProvider] = None,
        ollama_provider: Optional[OllamaProvider] = None,
        hf_provider: Optional[HuggingFaceProvider] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        mode: Optional[str] = None
    ):
        self.mode = (mode or os.environ.get("AI_ROUTER_MODE", "HYBRID")).upper()
        self.groq_provider = groq_provider or GroqProvider()
        self.ollama_provider = ollama_provider or OllamaProvider()
        self.hf_provider = hf_provider
        if self.hf_provider is None and os.environ.get("HF_TOKEN"):
            self.hf_provider = HuggingFaceProvider()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.telemetry = RouterTelemetry()

    def route_request(self, request: ProviderRequest) -> ProviderResponse:
        """
        Execute deterministic request routing based on capability policy and provider health.
        """
        t0 = time.perf_counter()
        policy = CapabilityRegistry.get_policy(request.task_category)

        # 1. Check Deterministic Offline policy
        if policy == RoutingPolicy.DETERMINISTIC_OFFLINE:
            rec = RouterTelemetryRecord(
                request_id=request.request_id,
                task_category=request.task_category.value,
                provider_selected=ProviderType.DETERMINISTIC.value,
                model_selected="deterministic_rule_engine",
                routing_decision="OFFLINE_DETERMINISTIC",
                latency_ms=0.1,
                final_status="SUCCESS"
            )
            self.telemetry.record(rec)
            return ProviderResponse(
                request_id=request.request_id,
                provider=ProviderType.DETERMINISTIC,
                model="deterministic_rule_engine",
                content="[Deterministic Offline Execution Required]",
                latency_ms=0.1,
                is_fallback=False,
                success=True
            )

        # 2. Check Unavailable tasks
        if policy == RoutingPolicy.UNAVAILABLE:
            raise TaskNotEligibleError(f"Task {request.task_category.value} is marked UNAVAILABLE for automated LLM routing.")

        cloud_error_summary = None

        # 3. Attempt Cloud inference if eligible and circuit allows
        if self.mode != "LOCAL_ONLY" and self.circuit_breaker.can_attempt_cloud():
            is_multimodal = request.task_category in (TaskCategory.MEDICAL_DOCUMENT_OCR, TaskCategory.VOICE_INTERPRETATION)

            # Route eligible text tasks to Hugging Face RLHF model if configured
            if not is_multimodal and self.hf_provider is not None and self.hf_provider.is_configured():
                try:
                    resp = self.hf_provider.generate(request)
                    self.circuit_breaker.record_success()
                    rec = RouterTelemetryRecord(
                        request_id=request.request_id,
                        task_category=request.task_category.value,
                        provider_selected=ProviderType.HUGGINGFACE.value,
                        model_selected=resp.model,
                        routing_decision="HF_RLHF_DIRECT",
                        latency_ms=resp.latency_ms,
                        tokens_per_second=resp.tokens_per_second,
                        circuit_breaker_state=self.circuit_breaker.state.value,
                        final_status="SUCCESS"
                    )
                    self.telemetry.record(rec)
                    return resp
                except Exception as hf_err:
                    hf_err_summary = f"{type(hf_err).__name__}: {str(hf_err)}"
                    logger.warning(f"Hugging Face RLHF attempt failed: {hf_err_summary}. Cascading to secondary cloud provider.")
                    cloud_error_summary = hf_err_summary

            # Attempt Groq Cloud provider
            try:
                resp = self.groq_provider.generate(request)
                self.circuit_breaker.record_success()
                rec = RouterTelemetryRecord(
                    request_id=request.request_id,
                    task_category=request.task_category.value,
                    provider_selected=ProviderType.GROQ.value,
                    model_selected=resp.model,
                    routing_decision="CLOUD_DIRECT",
                    latency_ms=resp.latency_ms,
                    tokens_per_second=resp.tokens_per_second,
                    circuit_breaker_state=self.circuit_breaker.state.value,
                    final_status="SUCCESS"
                )
                self.telemetry.record(rec)
                return resp
            except Exception as e:
                groq_err_summary = f"{type(e).__name__}: {str(e)}"
                cloud_error_summary = f"{cloud_error_summary} | {groq_err_summary}" if cloud_error_summary else groq_err_summary
                logger.warning(f"Cloud provider attempt failed: {cloud_error_summary}. Evaluating local fallback.")
                self.circuit_breaker.record_failure(e)
        else:
            if self.mode == "LOCAL_ONLY":
                cloud_error_summary = "LOCAL_ONLY mode forced by configuration"
            else:
                cloud_error_summary = f"Circuit breaker OPEN ({self.circuit_breaker.state.value}); Cloud bypassed"

        # 4. Check if task is eligible for Local Fallback
        if not CapabilityRegistry.is_local_eligible(request.task_category):
            err_msg = f"Task {request.task_category.value} is {policy.value}; cannot fallback to local inference."
            rec = RouterTelemetryRecord(
                request_id=request.request_id,
                task_category=request.task_category.value,
                provider_selected="NONE",
                model_selected="NONE",
                routing_decision="FALLBACK_REJECTED_INELIGIBLE",
                fallback_reason=cloud_error_summary,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                circuit_breaker_state=self.circuit_breaker.state.value,
                final_status="FAILED",
                error_summary=err_msg
            )
            self.telemetry.record(rec)
            raise TaskNotEligibleError(err_msg)

        # 5. Execute Local Fallback via Ollama (qwen2.5:7b-instruct)
        try:
            local_resp = self.ollama_provider.generate(request)
            local_resp.is_fallback = True
            local_resp.fallback_reason = cloud_error_summary

            rec = RouterTelemetryRecord(
                request_id=request.request_id,
                task_category=request.task_category.value,
                provider_selected=ProviderType.OLLAMA.value,
                model_selected=local_resp.model,
                routing_decision="LOCAL_FALLBACK",
                fallback_reason=cloud_error_summary,
                latency_ms=local_resp.latency_ms,
                tokens_per_second=local_resp.tokens_per_second,
                circuit_breaker_state=self.circuit_breaker.state.value,
                final_status="FALLBACK_SUCCESS"
            )
            self.telemetry.record(rec)
            return local_resp
        except Exception as local_err:
            total_err = f"Both cloud ({cloud_error_summary}) and local ({type(local_err).__name__}: {str(local_err)}) failed."
            logger.error(total_err)
            rec = RouterTelemetryRecord(
                request_id=request.request_id,
                task_category=request.task_category.value,
                provider_selected="NONE",
                model_selected="NONE",
                routing_decision="TOTAL_FAILURE",
                fallback_reason=cloud_error_summary,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                circuit_breaker_state=self.circuit_breaker.state.value,
                final_status="FAILED",
                error_summary=total_err
            )
            self.telemetry.record(rec)
            raise ProviderUnavailableError(total_err) from local_err

    async def route_request_async(self, request: ProviderRequest) -> ProviderResponse:
        return self.route_request(request)
