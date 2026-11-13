"""
TRUSTLINE Hybrid AI Router package.
"""
from .schemas import (
    ProviderType,
    ProviderStatus,
    TaskCategory,
    RoutingPolicy,
    CircuitState,
    ProviderRequest,
    ProviderResponse,
    ProviderHealth,
    HybridAIError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    TaskNotEligibleError,
    CircuitBreakerOpenError,
    OutputValidationError
)
from .base_provider import BaseLLMProvider
from .groq_provider import GroqProvider
from .ollama_provider import OllamaProvider
from .huggingface_provider import HuggingFaceProvider
from .circuit_breaker import CircuitBreaker
from .capability_registry import CapabilityRegistry
from .telemetry import RouterTelemetry, RouterTelemetryRecord
from .router import HybridAIRouter

# Backward compatibility aliases
from .cloud_provider import CloudAIProvider
from .local_provider import LocalAIProvider
from .ai_router import AIRouter

__all__ = [
    "ProviderType",
    "ProviderStatus",
    "TaskCategory",
    "RoutingPolicy",
    "CircuitState",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderHealth",
    "HybridAIError",
    "ProviderUnavailableError",
    "ProviderTimeoutError",
    "ProviderRateLimitError",
    "ProviderAuthenticationError",
    "TaskNotEligibleError",
    "CircuitBreakerOpenError",
    "OutputValidationError",
    "BaseLLMProvider",
    "GroqProvider",
    "OllamaProvider",
    "HuggingFaceProvider",
    "CircuitBreaker",
    "CapabilityRegistry",
    "RouterTelemetry",
    "RouterTelemetryRecord",
    "HybridAIRouter",
    "CloudAIProvider",
    "LocalAIProvider",
    "AIRouter"
]
